from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uuid
import os
import subprocess
import shutil
from dotenv import load_dotenv
import asyncio

load_dotenv()

app = FastAPI(title="Video-to-Doc")

# Store job status in memory (fine for local POC)
jobs = {}

# Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 500))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

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

@app.get("/")
async def root():
    return FileResponse("static/index.html")

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
    """Background task that runs the full pipeline"""
    from processor import extract_frames
    from analyzer import analyze_frames
    from pdf_generator import generate_pdf
    from cleanup import cleanup_frames_immediately, cleanup_failed_job, record_file_creation
    
    try:
        job = jobs[job_id]
        
        # Step 1: Extract frames
        jobs[job_id]["status"] = "extracting_frames"
        frame_paths = extract_frames(job["video_path"])
        jobs[job_id]["frame_paths"] = frame_paths
        
        # Step 2: Analyze with GPT-4o
        jobs[job_id]["status"] = "analyzing"
        markdown_content = analyze_frames(frame_paths)
        
        # Step 3: Generate PDF
        jobs[job_id]["status"] = "generating_pdf"
        pdf_filename = f"{os.path.splitext(job['filename'])[0]}_guide.pdf"
        pdf_path = f"temp/output/{job_id}_{pdf_filename}"
        os.makedirs("temp/output", exist_ok=True)
        generate_pdf(markdown_content, pdf_path)
        
        # Record PDF creation for cleanup
        record_file_creation(pdf_path)
        
        # Clean up frames immediately after PDF generation
        cleanup_frames_immediately(frame_paths)
        
        jobs[job_id]["status"] = "complete"
        jobs[job_id]["pdf_path"] = pdf_path
        jobs[job_id]["pdf_filename"] = pdf_filename
        
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        # Clean up failed job immediately
        cleanup_failed_job(jobs[job_id])

async def cleanup_scheduler():
    """Background cleanup task"""
    from cleanup import cleanup_old_files
    while True:
        await asyncio.sleep(600)  # Run every 10 minutes
        cleanup_old_files()

