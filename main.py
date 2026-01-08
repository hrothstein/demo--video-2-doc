from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import uuid
import os
import subprocess
import shutil
from dotenv import load_dotenv
import asyncio
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Video-to-Doc")

# Store job status in memory (fine for local POC)
jobs = {}

# Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 500))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_KEY_FRAMES = int(os.getenv("MAX_KEY_FRAMES", 18))
REDACTION_MODE = os.getenv("REDACTION_MODE", "blur")
ENABLE_NAME_DETECTION = os.getenv("ENABLE_NAME_DETECTION", "false").lower() == "true"
OCR_GPU = os.getenv("OCR_GPU", "false").lower() == "true"

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

def check_ffmpeg():
    """Check if ffmpeg is available"""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        return False, "ffmpeg not found in PATH. Please install ffmpeg:\n  - macOS: brew install ffmpeg\n  - Ubuntu/Debian: sudo apt-get install ffmpeg\n  - Windows: Download from https://ffmpeg.org/download.html"
    return True, None

def validate_env_vars():
    """Validate required environment variables"""
    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT_NAME"
    ]
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        return False, f"Missing required environment variables: {', '.join(missing)}"
    return True, None

@app.on_event("startup")
async def startup_event():
    """Check prerequisites on startup"""
    # Check ffmpeg
    ffmpeg_ok, ffmpeg_error = check_ffmpeg()
    if not ffmpeg_ok:
        print(f"ERROR: {ffmpeg_error}")
        print("Server will start but video processing will fail. Please install ffmpeg.")
    
    # Validate environment variables
    env_ok, env_error = validate_env_vars()
    if not env_ok:
        print(f"ERROR: {env_error}")
        print("Server will start but Azure OpenAI calls will fail. Please configure .env file.")
    
    # Start cleanup scheduler
    asyncio.create_task(cleanup_scheduler())
    
    # Create temp directories
    os.makedirs("temp/uploads", exist_ok=True)
    os.makedirs("temp/frames", exist_ok=True)
    os.makedirs("temp/output", exist_ok=True)
    os.makedirs("temp/redacted", exist_ok=True)  # v2.0

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/review.html")
async def review_page():
    return FileResponse("static/review.html")

@app.get("/review/{job_id}")
async def get_review(job_id: str):
    """Get frames with PII annotations for review"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job.get("status") != "ready_for_review":
        raise HTTPException(status_code=400, detail="Job not ready for review")
    
    frames_data = []
    for i, frame_info in enumerate(job.get("key_frame_data", [])):
        frames_data.append({
            "id": i + 1,
            "path": frame_info["path"],
            "pii": [
                {
                    "type": match.pii_type,
                    "text": match.matched_text,
                    "confidence": match.confidence
                }
                for match in frame_info.get("pii_matches", [])
            ]
        })
    
    return {
        "frames": frames_data,
        "ocr_results": job.get("ocr_results", {})  # Cache for re-detection
    }

@app.put("/redactions/{job_id}")
async def update_redactions(job_id: str, redaction_data: dict):
    """Update redaction decisions"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    jobs[job_id]["redaction_decisions"] = redaction_data.get("decisions", {})
    jobs[job_id]["redaction_mode"] = redaction_data.get("mode", REDACTION_MODE)
    
    return {"status": "updated"}

@app.post("/generate/{job_id}")
async def generate_pdf(job_id: str, background_tasks: BackgroundTasks):
    """Generate final PDF with approved redactions"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    background_tasks.add_task(generate_final_pdf, job_id)
    return {"status": "generating"}

@app.get("/frame/{job_id}/{frame_id}")
async def get_frame(job_id: str, frame_id: int, preview: bool = Query(False)):
    """Get individual frame image (original or redacted preview)"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    key_frame_data = job.get("key_frame_data", [])
    
    if frame_id < 1 or frame_id > len(key_frame_data):
        raise HTTPException(status_code=404, detail="Frame not found")
    
    frame_info = key_frame_data[frame_id - 1]
    
    if preview:
        # Return preview with red boxes
        preview_path = frame_info.get("preview_path")
        if preview_path and os.path.exists(preview_path):
            return FileResponse(preview_path, media_type="image/jpeg")
    
    # Return original frame
    if os.path.exists(frame_info["path"]):
        return FileResponse(frame_info["path"], media_type="image/jpeg")
    
    raise HTTPException(status_code=404, detail="Frame file not found")

@app.post("/upload")
async def upload_video(file: UploadFile):
    # Validate file type
    valid_types = ["video/mp4", "video/quicktime", "video/webm"]
    if file.content_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Supported: MP4, MOV, WebM")
    
    # Read file to check size
    content = await file.read()
    file_size = len(content)
    
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400, 
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB"
        )
    
    job_id = str(uuid.uuid4())
    upload_path = f"temp/uploads/{job_id}_{file.filename}"
    
    # Save file
    with open(upload_path, "wb") as f:
        f.write(content)
    
    jobs[job_id] = {
        "status": "uploaded",
        "video_path": upload_path,
        "filename": file.filename
    }
    
    # Record file creation for cleanup
    from cleanup import record_file_creation
    record_file_creation(upload_path)
    
    return {"job_id": job_id}

@app.post("/process/{job_id}")
async def process_video(job_id: str, background_tasks: BackgroundTasks):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check ffmpeg before processing
    ffmpeg_ok, ffmpeg_error = check_ffmpeg()
    if not ffmpeg_ok:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = ffmpeg_error
        raise HTTPException(status_code=500, detail=ffmpeg_error)
    
    background_tasks.add_task(run_pipeline, job_id)
    jobs[job_id]["status"] = "processing"
    
    return {"status": "processing"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/download/{job_id}")
async def download_pdf(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    if jobs[job_id]["status"] != "complete":
        raise HTTPException(status_code=400, detail="Processing not complete")
    
    return FileResponse(
        jobs[job_id]["pdf_path"],
        media_type="application/pdf",
        filename=jobs[job_id]["pdf_filename"]
    )

async def run_pipeline(job_id: str):
    """Background task that runs the full pipeline (v2.0)"""
    from processor import extract_frames
    from analyzer import analyze_frames_v2
    from frame_selector import select_key_frames
    from ocr_engine import extract_text_regions
    from pii_detector import detect_pii, detect_names_ner
    from redactor import generate_preview
    from cleanup import cleanup_frames_immediately, cleanup_failed_job, record_file_creation
    
    try:
        job = jobs[job_id]
        
        # Step 1: Extract frames
        jobs[job_id]["status"] = "extracting_frames"
        frame_paths = extract_frames(job["video_path"])
        jobs[job_id]["frame_paths"] = frame_paths
        
        # Step 2: Select key frames for embedding
        jobs[job_id]["status"] = "selecting_key_frames"
        key_frame_paths = select_key_frames(frame_paths, max_embed=MAX_KEY_FRAMES)
        jobs[job_id]["key_frame_paths"] = key_frame_paths
        
        # Step 3: OCR and PII detection on key frames only
        jobs[job_id]["status"] = "detecting_pii"
        key_frame_data = []
        ocr_results = {}  # Cache for re-detection
        
        try:
            for i, frame_path in enumerate(key_frame_paths):
                # OCR
                text_regions = extract_text_regions(frame_path, gpu=OCR_GPU)
                ocr_results[frame_path] = text_regions
                
                # PII detection
                enable_optional = []
                if ENABLE_NAME_DETECTION:
                    enable_optional.append("person_name")
                
                pii_matches = detect_pii(text_regions, enable_optional=enable_optional)
                
                # Name detection (if enabled)
                if ENABLE_NAME_DETECTION:
                    name_matches = detect_names_ner(text_regions)
                    pii_matches.extend(name_matches)
                
                # Generate preview
                preview_path = f"temp/redacted/{job_id}_frame_{i+1}_preview.jpg"
                if pii_matches:
                    generate_preview(frame_path, preview_path, pii_matches)
                else:
                    # No PII, just copy original
                    shutil.copy2(frame_path, preview_path)
                
                key_frame_data.append({
                    "path": frame_path,
                    "pii_matches": pii_matches,
                    "preview_path": preview_path
                })
            
            jobs[job_id]["key_frame_data"] = key_frame_data
            jobs[job_id]["ocr_results"] = ocr_results
            
        except Exception as e:
            logger.error(f"PII detection failed: {e}")
            # Graceful degradation - continue without PII detection
            key_frame_data = [{"path": path, "pii_matches": [], "preview_path": path} 
                            for path in key_frame_paths]
            jobs[job_id]["key_frame_data"] = key_frame_data
            jobs[job_id]["ocr_results"] = {}
        
        # Step 4: Analyze with GPT-4o (all frames, key frames marked)
        jobs[job_id]["status"] = "analyzing"
        markdown_content = analyze_frames_v2(frame_paths, key_frame_paths)
        jobs[job_id]["markdown_content"] = markdown_content
        
        # Step 5: Ready for review
        jobs[job_id]["status"] = "ready_for_review"
        jobs[job_id]["has_pii_detections"] = any(
            frame.get("pii_matches", []) for frame in key_frame_data
        )
        jobs[job_id]["key_frame_count"] = len(key_frame_paths)
        
    except Exception as e:
        logger.error(f"Pipeline failed for job {job_id}: {e}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        # Clean up failed job immediately
        cleanup_failed_job(jobs[job_id])

async def generate_final_pdf(job_id: str):
    """Generate final PDF with approved redactions"""
    from pdf_generator import generate_pdf_v2
    from redactor import apply_redactions
    from cleanup import record_file_creation
    
    try:
        job = jobs[job_id]
        
        if job.get("status") != "ready_for_review":
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = "Job not ready for PDF generation"
            return
        
        jobs[job_id]["status"] = "generating_pdf"
        
        # Apply redactions based on decisions
        redaction_decisions = job.get("redaction_decisions", {})
        redaction_mode = job.get("redaction_mode", REDACTION_MODE)
        key_frame_data = job.get("key_frame_data", [])
        
        redacted_frames = {}  # {frame_number: redacted_image_path}
        
        for i, frame_info in enumerate(key_frame_data):
            frame_id = str(i + 1)
            frame_pii = frame_info.get("pii_matches", [])
            
            # Filter PII matches based on decisions
            if frame_id in redaction_decisions:
                decisions = redaction_decisions[frame_id]
                # decisions is list of {index, redact}
                pii_to_redact = [
                    frame_pii[dec["index"]] 
                    for dec in decisions 
                    if dec.get("redact", True) and dec["index"] < len(frame_pii)
                ]
            else:
                # Default: redact all detected PII
                pii_to_redact = frame_pii
            
            if pii_to_redact:
                # Apply redactions
                redacted_path = f"temp/redacted/{job_id}_frame_{i+1}_redacted.jpg"
                apply_redactions(
                    frame_info["path"],
                    redacted_path,
                    pii_to_redact,
                    mode=redaction_mode
                )
                redacted_frames[i + 1] = redacted_path
            else:
                # No redactions needed, use original
                redacted_frames[i + 1] = frame_info["path"]
        
        # Generate PDF
        pdf_filename = f"{os.path.splitext(job['filename'])[0]}_guide.pdf"
        pdf_path = f"temp/output/{job_id}_{pdf_filename}"
        os.makedirs("temp/output", exist_ok=True)
        
        markdown_content = job.get("markdown_content", "")
        generate_pdf_v2(markdown_content, pdf_path, redacted_frames)
        
        # Record PDF creation for cleanup
        record_file_creation(pdf_path)
        
        # Clean up frames immediately after PDF generation
        frame_paths = job.get("frame_paths", [])
        from cleanup import cleanup_frames_immediately
        cleanup_frames_immediately(frame_paths)
        
        jobs[job_id]["status"] = "complete"
        jobs[job_id]["pdf_path"] = pdf_path
        jobs[job_id]["pdf_filename"] = pdf_filename
        
    except Exception as e:
        logger.error(f"PDF generation failed for job {job_id}: {e}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)

async def cleanup_scheduler():
    """Background cleanup task"""
    from cleanup import cleanup_old_files
    while True:
        await asyncio.sleep(600)  # Run every 10 minutes
        cleanup_old_files()

