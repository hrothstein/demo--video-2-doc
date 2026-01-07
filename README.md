# Video-to-Doc

Convert screen recordings into step-by-step PDF documentation using Azure OpenAI GPT-4o.

## Prerequisites

- Python 3.10+
- ffmpeg installed and in PATH
- Azure OpenAI account with GPT-4o deployment

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

4. Verify ffmpeg is installed:
   ```bash
   ffmpeg -version
   ```
   If not installed:
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt-get install ffmpeg`
   - Windows: Download from https://ffmpeg.org/download.html

5. Create `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```

6. Configure Azure OpenAI in `.env`:
   - `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL (e.g., `https://your-resource.openai.azure.com/`)
   - `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key
   - `AZURE_OPENAI_DEPLOYMENT_NAME`: The name of your GPT-4o deployment (create one in Azure OpenAI Studio)
   - `AZURE_OPENAI_API_VERSION`: API version (default: `2024-02-15-preview`)

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
| MAX_FILE_SIZE_MB | 500 | Maximum upload file size in MB |
| OUTPUT_DIR | ./temp/output | Directory for generated PDFs |

## Azure OpenAI Setup

1. Create an Azure OpenAI resource in Azure Portal
2. Deploy a GPT-4o model in Azure OpenAI Studio
3. Name your deployment (e.g., "gpt-4o-vision")
4. Copy the endpoint URL and API key
5. Add them to your `.env` file

## Project Structure

```
video-to-doc/
├── main.py                 # FastAPI app, routes, startup checks
├── processor.py            # Frame extraction with ffmpeg
├── analyzer.py             # Azure OpenAI GPT-4o integration
├── pdf_generator.py        # Markdown to PDF conversion
├── cleanup.py              # Background cleanup tasks
├── static/
│   └── index.html          # Frontend UI
├── temp/                   # Temp storage (gitignored)
│   ├── uploads/            # Uploaded videos
│   ├── frames/             # Extracted frames
│   └── output/             # Generated PDFs
├── requirements.txt
├── .env.example
└── README.md
```

## Notes

- Videos are processed locally
- Frames are cleaned up immediately after PDF generation
- Uploads and PDFs are cleaned up after 1 hour
- Job status is stored in memory (lost on server restart)

