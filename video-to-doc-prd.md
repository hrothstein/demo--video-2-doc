# Video-to-Doc Agent PRD (Local POC)

## Overview

A local web application that converts screen recording videos into step-by-step how-to documentation in PDF format. Upload a video of yourself performing a task (like installing an app), and the agent extracts frames, analyzes them with GPT-4o, and generates a downloadable PDF guide.

## Goals

- Prove the concept works locally before any deployment considerations
- Minimal viable UI — functional, not pretty
- Output as professional PDF that can be shared or printed
- Fast iteration cycle for testing different video types

## Tech Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Backend | Python + FastAPI | Simple, good ecosystem for video/AI |
| Frontend | HTML + vanilla JS | No build step, just serve static files |
| Frame Extraction | ffmpeg | Industry standard, already on most dev machines |
| Audio Transcription | OpenAI Whisper API | Optional enhancement, same billing as GPT-4o |
| Documentation Generation | GPT-4o | Best vision model for this use case |
| PDF Generation | reportlab | Python native, no external dependencies |

## Core Features (MVP)

### 1. Video Upload
- Drag-drop or file picker
- Support mp4, mov, webm
- Display upload progress
- Max file size: 500MB (configurable)

### 2. Processing Pipeline
- Extract frames at configurable interval (default: 1 frame every 2 seconds)
- Cap frames at MAX_FRAMES to control token costs
- Send frames to GPT-4o vision API
- Receive structured markdown response
- Convert markdown to formatted PDF

### 3. PDF Output
- Professional formatting with title, steps, and frame references
- Numbered steps with clear action descriptions
- Download button for the generated PDF
- Optional: embed key frames as images in the PDF

## User Flow

```
1. User opens localhost:8000
2. User drags video file onto upload zone
3. Click "Generate Documentation"
4. Progress indicator shows:
   - "Uploading video..."
   - "Extracting frames..."
   - "Analyzing with GPT-4o..."
   - "Generating PDF..."
5. PDF preview appears (or download starts automatically)
6. User clicks "Download PDF"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve frontend |
| `/upload` | POST | Upload video, returns job_id |
| `/process/{job_id}` | POST | Start processing |
| `/status/{job_id}` | GET | Check processing status |
| `/download/{job_id}` | GET | Download generated PDF |

## File Structure

```
video-to-doc/
├── main.py                 # FastAPI app, routes
├── processor.py            # Frame extraction logic
├── analyzer.py             # OpenAI GPT-4o integration
├── pdf_generator.py        # Markdown to PDF conversion
├── static/
│   ├── index.html          # Frontend UI
│   └── style.css           # Minimal styling
├── temp/                   # Temp storage (gitignored)
│   ├── uploads/            # Uploaded videos
│   ├── frames/             # Extracted frames
│   └── output/             # Generated PDFs
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

Environment variables (`.env` file):

```
OPENAI_API_KEY=sk-...
FRAME_INTERVAL=2          # Seconds between frame captures
MAX_FRAMES=50             # Cap to control token costs
OUTPUT_DIR=./temp/output
INCLUDE_FRAMES_IN_PDF=false  # Whether to embed frame images
```

## Implementation Details

### main.py - FastAPI Application

```python
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uuid
import os

app = FastAPI(title="Video-to-Doc")

# Store job status in memory (fine for local POC)
jobs = {}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/upload")
async def upload_video(file: UploadFile):
    job_id = str(uuid.uuid4())
    upload_path = f"temp/uploads/{job_id}_{file.filename}"
    
    os.makedirs("temp/uploads", exist_ok=True)
    
    with open(upload_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    jobs[job_id] = {
        "status": "uploaded",
        "video_path": upload_path,
        "filename": file.filename
    }
    
    return {"job_id": job_id}

@app.post("/process/{job_id}")
async def process_video(job_id: str, background_tasks: BackgroundTasks):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
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
    
    try:
        job = jobs[job_id]
        
        # Step 1: Extract frames
        jobs[job_id]["status"] = "extracting_frames"
        frame_paths = extract_frames(job["video_path"])
        
        # Step 2: Analyze with GPT-4o
        jobs[job_id]["status"] = "analyzing"
        markdown_content = analyze_frames(frame_paths)
        
        # Step 3: Generate PDF
        jobs[job_id]["status"] = "generating_pdf"
        pdf_filename = f"{os.path.splitext(job['filename'])[0]}_guide.pdf"
        pdf_path = f"temp/output/{job_id}_{pdf_filename}"
        os.makedirs("temp/output", exist_ok=True)
        generate_pdf(markdown_content, pdf_path)
        
        jobs[job_id]["status"] = "complete"
        jobs[job_id]["pdf_path"] = pdf_path
        jobs[job_id]["pdf_filename"] = pdf_filename
        
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
```

### processor.py - Frame Extraction

```python
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL", 2))
MAX_FRAMES = int(os.getenv("MAX_FRAMES", 50))

def extract_frames(video_path: str) -> list[str]:
    """Extract frames from video at specified interval"""
    
    # Create output directory
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = f"temp/frames/{video_name}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Run ffmpeg
    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-vf", f"fps=1/{FRAME_INTERVAL}",
        "-q:v", "2",  # High quality JPEG
        f"{output_dir}/frame_%04d.jpg",
        "-y"  # Overwrite
    ], capture_output=True)
    
    # Get list of frames
    frames = sorted([
        os.path.join(output_dir, f) 
        for f in os.listdir(output_dir) 
        if f.endswith('.jpg')
    ])
    
    # Cap at MAX_FRAMES by sampling evenly
    if len(frames) > MAX_FRAMES:
        step = len(frames) / MAX_FRAMES
        sampled = [frames[int(i * step)] for i in range(MAX_FRAMES)]
        
        # Delete non-sampled frames
        for f in frames:
            if f not in sampled:
                os.remove(f)
        
        frames = sampled
    
    return frames
```

### analyzer.py - GPT-4o Integration

```python
import base64
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

SYSTEM_PROMPT = """You are a technical documentation writer creating a step-by-step how-to guide.

You will receive sequential screenshots from a screen recording of someone performing a task on their computer. Analyze them in order and produce clear documentation.

## Output Format

Return your response in this exact markdown structure:

# [Task Title - infer from what you see]

## Prerequisites
- [Any requirements visible or implied]

## Steps

### Step 1: [Action Title]
**Action:** [Click/Type/Select/etc.]
**Location:** [Where in the UI]
**Details:** [Specific values, text to enter, options to select]

### Step 2: [Action Title]
...continue for all steps...

## Notes
- [Any warnings, tips, or troubleshooting observed]

## Rules
- Be concise but thorough
- Use exact text shown in UI for button names, menu items, field labels
- If you see error messages, include troubleshooting steps
- Reference frame numbers when helpful (e.g., "as shown in frame 5")
- Assume reader is technical but unfamiliar with this specific process
"""

def encode_image(image_path: str) -> str:
    """Convert image to base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def analyze_frames(frame_paths: list[str]) -> str:
    """Send frames to GPT-4o and get documentation"""
    
    # Build image content
    image_content = []
    for i, path in enumerate(frame_paths):
        image_content.append({
            "type": "text",
            "text": f"Frame {i + 1}:"
        })
        image_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{encode_image(path)}",
                "detail": "high"
            }
        })
    
    # Call GPT-4o
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": image_content}
        ],
        max_tokens=4096
    )
    
    return response.choices[0].message.content
```

### pdf_generator.py - PDF Creation

```python
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.colors import HexColor
import re

def generate_pdf(markdown_content: str, output_path: str):
    """Convert markdown documentation to PDF"""
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='DocTitle',
        parent=styles['Title'],
        fontSize=20,
        spaceAfter=20,
        textColor=HexColor('#1a1a1a')
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHead',
        parent=styles['Heading1'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=8,
        textColor=HexColor('#2563eb')
    ))
    
    styles.add(ParagraphStyle(
        name='StepHead',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=HexColor('#1e40af')
    ))
    
    styles.add(ParagraphStyle(
        name='BodyText',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        leading=14
    ))
    
    styles.add(ParagraphStyle(
        name='BoldLabel',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=4,
        leading=14
    ))
    
    story = []
    
    # Parse markdown and build PDF
    lines = markdown_content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Title (# )
        if line.startswith('# ') and not line.startswith('## '):
            story.append(Paragraph(line[2:], styles['DocTitle']))
        
        # Section (## )
        elif line.startswith('## '):
            story.append(Paragraph(line[3:], styles['SectionHead']))
        
        # Step (### )
        elif line.startswith('### '):
            story.append(Paragraph(line[4:], styles['StepHead']))
        
        # Bold labels (**Action:** etc)
        elif line.startswith('**') and ':**' in line:
            # Convert **Label:** text to formatted
            match = re.match(r'\*\*(.+?):\*\*\s*(.*)', line)
            if match:
                label, text = match.groups()
                story.append(Paragraph(f"<b>{label}:</b> {text}", styles['BoldLabel']))
        
        # Bullet points
        elif line.startswith('- '):
            story.append(Paragraph(f"• {line[2:]}", styles['BodyText']))
        
        # Regular text
        else:
            story.append(Paragraph(line, styles['BodyText']))
    
    doc.build(story)
```

### static/index.html - Frontend

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video to Doc</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 700px;
            margin: 0 auto;
            padding: 2rem;
            background: #f9fafb;
            color: #1a1a1a;
        }
        h1 { margin-bottom: 0.5rem; }
        .subtitle { color: #6b7280; margin-bottom: 2rem; }
        
        .dropzone {
            border: 2px dashed #d1d5db;
            border-radius: 12px;
            padding: 3rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            background: white;
        }
        .dropzone:hover, .dropzone.dragover {
            border-color: #2563eb;
            background: #eff6ff;
        }
        .dropzone p { margin: 0.5rem 0; }
        .dropzone .icon { font-size: 3rem; margin-bottom: 1rem; }
        .dropzone small { color: #9ca3af; }
        
        .file-info {
            display: none;
            background: white;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
            border: 1px solid #e5e7eb;
        }
        .file-info.visible { display: flex; align-items: center; gap: 1rem; }
        .file-info .name { flex: 1; font-weight: 500; }
        .file-info .remove { 
            color: #ef4444; 
            cursor: pointer; 
            background: none; 
            border: none;
            font-size: 1.2rem;
        }
        
        .progress-section {
            display: none;
            margin-top: 1.5rem;
        }
        .progress-section.visible { display: block; }
        .status-text { 
            color: #6b7280; 
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid #e5e7eb;
            border-top-color: #2563eb;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .progress-bar {
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: #2563eb;
            width: 0%;
            transition: width 0.3s;
        }
        
        button.primary {
            background: #2563eb;
            color: white;
            border: none;
            padding: 0.875rem 1.5rem;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            margin-top: 1.5rem;
            width: 100%;
            transition: background 0.2s;
        }
        button.primary:hover { background: #1d4ed8; }
        button.primary:disabled { 
            background: #9ca3af; 
            cursor: not-allowed; 
        }
        
        .download-section {
            display: none;
            margin-top: 1.5rem;
            padding: 1.5rem;
            background: #ecfdf5;
            border-radius: 8px;
            text-align: center;
        }
        .download-section.visible { display: block; }
        .download-section .success { 
            color: #059669; 
            font-weight: 500;
            margin-bottom: 1rem;
        }
        .download-section a {
            display: inline-block;
            background: #059669;
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
        }
        .download-section a:hover { background: #047857; }
        
        .error {
            display: none;
            margin-top: 1rem;
            padding: 1rem;
            background: #fef2f2;
            border-radius: 8px;
            color: #dc2626;
        }
        .error.visible { display: block; }
    </style>
</head>
<body>
    <h1>Video to Documentation</h1>
    <p class="subtitle">Upload a screen recording and get a PDF how-to guide.</p>
    
    <div class="dropzone" id="dropzone">
        <div class="icon">📹</div>
        <p>Drag & drop video here</p>
        <p>or click to select</p>
        <small>Supports: MP4, MOV, WebM (max 500MB)</small>
    </div>
    <input type="file" id="fileInput" accept=".mp4,.mov,.webm" hidden>
    
    <div class="file-info" id="fileInfo">
        <span class="name" id="fileName"></span>
        <button class="remove" id="removeFile">×</button>
    </div>
    
    <button class="primary" id="processBtn" disabled>Generate Documentation</button>
    
    <div class="progress-section" id="progressSection">
        <div class="status-text">
            <div class="spinner"></div>
            <span id="statusText">Processing...</span>
        </div>
        <div class="progress-bar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
    </div>
    
    <div class="download-section" id="downloadSection">
        <p class="success">✓ Documentation generated successfully!</p>
        <a id="downloadLink" href="#">Download PDF</a>
    </div>
    
    <div class="error" id="errorSection"></div>

    <script>
        const dropzone = document.getElementById('dropzone');
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const removeFile = document.getElementById('removeFile');
        const processBtn = document.getElementById('processBtn');
        const progressSection = document.getElementById('progressSection');
        const statusText = document.getElementById('statusText');
        const progressFill = document.getElementById('progressFill');
        const downloadSection = document.getElementById('downloadSection');
        const downloadLink = document.getElementById('downloadLink');
        const errorSection = document.getElementById('errorSection');
        
        let selectedFile = null;
        let currentJobId = null;
        
        // Drag and drop
        dropzone.addEventListener('click', () => fileInput.click());
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover');
        });
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && isValidVideo(file)) {
                selectFile(file);
            }
        });
        
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) selectFile(file);
        });
        
        removeFile.addEventListener('click', () => {
            selectedFile = null;
            fileInfo.classList.remove('visible');
            processBtn.disabled = true;
            fileInput.value = '';
        });
        
        function isValidVideo(file) {
            const validTypes = ['video/mp4', 'video/quicktime', 'video/webm'];
            return validTypes.includes(file.type);
        }
        
        function selectFile(file) {
            selectedFile = file;
            fileName.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
            fileInfo.classList.add('visible');
            processBtn.disabled = false;
            downloadSection.classList.remove('visible');
            errorSection.classList.remove('visible');
        }
        
        processBtn.addEventListener('click', async () => {
            if (!selectedFile) return;
            
            processBtn.disabled = true;
            progressSection.classList.add('visible');
            downloadSection.classList.remove('visible');
            errorSection.classList.remove('visible');
            
            try {
                // Upload
                updateStatus('Uploading video...', 10);
                const formData = new FormData();
                formData.append('file', selectedFile);
                
                const uploadRes = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                const { job_id } = await uploadRes.json();
                currentJobId = job_id;
                
                // Start processing
                updateStatus('Starting processing...', 20);
                await fetch(`/process/${job_id}`, { method: 'POST' });
                
                // Poll for status
                pollStatus(job_id);
                
            } catch (err) {
                showError(err.message);
            }
        });
        
        async function pollStatus(jobId) {
            const statusMap = {
                'extracting_frames': { text: 'Extracting frames...', progress: 40 },
                'analyzing': { text: 'Analyzing with GPT-4o...', progress: 60 },
                'generating_pdf': { text: 'Generating PDF...', progress: 80 },
                'complete': { text: 'Complete!', progress: 100 },
                'error': { text: 'Error', progress: 0 }
            };
            
            try {
                const res = await fetch(`/status/${jobId}`);
                const data = await res.json();
                
                if (data.status === 'complete') {
                    updateStatus('Complete!', 100);
                    downloadLink.href = `/download/${jobId}`;
                    downloadSection.classList.add('visible');
                    progressSection.classList.remove('visible');
                    processBtn.disabled = false;
                } else if (data.status === 'error') {
                    showError(data.error || 'Processing failed');
                } else {
                    const info = statusMap[data.status] || { text: 'Processing...', progress: 50 };
                    updateStatus(info.text, info.progress);
                    setTimeout(() => pollStatus(jobId), 1000);
                }
            } catch (err) {
                showError(err.message);
            }
        }
        
        function updateStatus(text, progress) {
            statusText.textContent = text;
            progressFill.style.width = `${progress}%`;
        }
        
        function showError(message) {
            errorSection.textContent = `Error: ${message}`;
            errorSection.classList.add('visible');
            progressSection.classList.remove('visible');
            processBtn.disabled = false;
        }
    </script>
</body>
</html>
```

### requirements.txt

```
fastapi==0.109.0
uvicorn==0.27.0
python-multipart==0.0.6
openai==1.12.0
reportlab==4.1.0
python-dotenv==1.0.0
```

### .env.example

```
OPENAI_API_KEY=sk-your-key-here
FRAME_INTERVAL=2
MAX_FRAMES=50
```

### README.md

```markdown
# Video-to-Doc

Convert screen recordings into step-by-step PDF documentation using GPT-4o.

## Prerequisites

- Python 3.10+
- ffmpeg installed and in PATH
- OpenAI API key with GPT-4o access

## Setup

1. Clone this repo
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and add your OpenAI API key
5. Verify ffmpeg is installed:
   ```bash
   ffmpeg -version
   ```

## Run

```bash
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000

## Usage

1. Drag and drop a screen recording (MP4, MOV, or WebM)
2. Click "Generate Documentation"
3. Wait for processing (typically 30-90 seconds)
4. Download the PDF guide

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| FRAME_INTERVAL | 2 | Seconds between frame captures |
| MAX_FRAMES | 50 | Max frames to send to GPT-4o |
```

## Success Criteria

- [ ] Can upload a 2-minute screen recording
- [ ] Processing completes in under 90 seconds
- [ ] Generates accurate step-by-step documentation
- [ ] PDF is well-formatted and readable
- [ ] Output is immediately usable (share with team, print, etc.)

## Token Cost Estimate

| Video Length | Frames (2s interval) | Estimated Cost |
|--------------|---------------------|----------------|
| 1 minute | 30 frames | ~$0.30-0.60 |
| 2 minutes | 60 frames (capped to 50) | ~$0.50-1.00 |
| 5 minutes | 150 frames (capped to 50) | ~$0.50-1.00 |

## Future Enhancements (Post-POC)

- [ ] Whisper transcription for narrated videos
- [ ] Scene detection instead of fixed intervals
- [ ] Embed actual frame screenshots in PDF
- [ ] Multiple output formats (DOCX, HTML)
- [ ] Batch processing multiple videos
- [ ] Hosted version with authentication
