# Video-to-Doc Agent v2.0 PRD

## Overview

Building on v1.0, this version embeds key screenshots directly into the PDF documentation and automatically scrubs personally identifiable information (PII) from those screenshots before inclusion. The result is a shareable, professional how-to guide that's safe to distribute externally.

## What's New in v2.0

| Feature | v1.0 | v2.0 |
|---------|------|------|
| PDF with steps | ✓ | ✓ |
| Embedded screenshots | ✗ | ✓ |
| PII detection | ✗ | ✓ |
| Auto-redaction | ✗ | ✓ |
| Redaction preview | ✗ | ✓ |

## Goals

- Embed relevant screenshots in PDF documentation for visual clarity
- Automatically detect and redact PII before embedding
- Give users control to review and adjust redactions before final PDF
- Keep processing time reasonable (< 3 minutes for typical videos)
- Maintain low false-positive rate on redactions (don't blur everything)

## PII Detection Scope

### Automatically Detected (High Confidence)

| PII Type | Detection Method | Example |
|----------|------------------|---------|
| Email addresses | Regex | `john.doe@company.com` |
| Phone numbers | Regex | `(555) 123-4567`, `+1-555-123-4567` |
| SSN patterns | Regex | `123-45-6789` |
| Credit card numbers | Regex + Luhn | `4111-1111-1111-1111` |
| IP addresses | Regex | `192.168.1.1` |
| User paths | Regex | `/Users/johndoe/`, `C:\Users\JohnDoe\` |
| AWS keys | Regex | `AKIA...` |
| API keys | Regex patterns | `sk-...`, `ghp_...` |

### Optionally Detected (User Toggle)

| PII Type | Detection Method | Notes |
|----------|------------------|-------|
| Person names | NER model (spaCy) | Higher false positive rate |
| URLs | Regex | May over-redact |
| Dates | Regex | Often not sensitive |
| Custom patterns | User-provided regex | For internal codes, project names |

### Out of Scope for v2.0

- Face detection/blurring
- Voice redaction in audio
- Handwritten text
- Non-English PII patterns

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web Frontend  │────▶│   Backend API   │────▶│   LLM (GPT-4o)  │
│  (Upload/Review)│     │   (Processing)  │     │   (Analysis)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
       ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
       │   FFmpeg    │  │  EasyOCR    │  │   Pillow    │
       │  (frames)   │  │  (text+box) │  │   (blur)    │
       └─────────────┘  └─────────────┘  └─────────────┘
```

## Frame Processing Strategy

The system processes frames in two parallel tracks:

**Track 1: GPT-4o Analysis (All Frames)**
- Extracts all frames up to `MAX_FRAMES` limit (default: 50)
- Sends all frames to GPT-4o for context and documentation generation
- GPT-4o sees the full video sequence for accurate step-by-step analysis

**Track 2: OCR & PII Detection (Key Frames Only)**
- Selects key frames for embedding (default: max 10 frames)
- Runs OCR on key frames only (faster, more efficient)
- Detects PII in OCR results
- Generates redacted previews for user review

**Flow:**
```
All frames (50 max) → GPT-4o analysis
Key frames (10 max) → OCR → PII detection → Redaction → PDF embed
```

This approach balances accuracy (full context for GPT-4o) with performance (OCR only on frames that will be embedded).

## User Flow

```
1. User opens localhost:8000
2. User uploads video
3. Click "Generate Documentation"
4. Processing:
   - Extract frames
   - Select key frames for embedding
   - OCR each key frame
   - Detect PII in OCR results
   - Generate redacted previews
   - Analyze with GPT-4o (all frames)
5. Automatic redirect to Redaction Review screen:
   - Show each key frame with red boxes around detected PII
   - User can: approve or remove redaction for each detected PII
   - Toggle optional PII types (names, URLs, etc.) - triggers re-detection
   - If zero PII detected, show message: "No PII detected. You can proceed to generate the PDF."
6. Click "Generate PDF"
7. Final PDF with redacted screenshots embedded
8. Download PDF
```

## New/Modified API Endpoints

### v2.0 New Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/review/{job_id}` | GET | Get frames with PII annotations for review |
| `/redactions/{job_id}` | PUT | Update redaction decisions |
| `/generate/{job_id}` | POST | Generate final PDF with approved redactions |
| `/frame/{job_id}/{frame_id}` | GET | Get individual frame image (original or redacted) |

### Updated v1.0 Endpoints (Backward Compatible)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload` | POST | Upload video file (unchanged) |
| `/process/{job_id}` | POST | Now includes frame selection, OCR, and PII detection. Returns status `ready_for_review` when complete. |
| `/status/{job_id}` | GET | Get job status. New status values: `ready_for_review` (between processing and final PDF generation) |
| `/download/{job_id}` | GET | Download final PDF (unchanged) |

**Status Flow:**
- `uploaded` → `processing` → `ready_for_review` → `complete`
- v1.0 flow: `uploaded` → `processing` → `complete` (skips review, no screenshots embedded)
- v2.0 flow: `uploaded` → `processing` → `ready_for_review` → `complete` (includes review step)

**Job Status Response (v2.0):**
```json
{
  "status": "ready_for_review",
  "has_pii_detections": true,
  "key_frame_count": 8,
  "video_path": "...",
  "filename": "..."
}
```

## File Structure (Changes from v1.0)

```
video-to-doc/
├── main.py                 # FastAPI app (updated routes)
├── processor.py            # Frame extraction (unchanged)
├── frame_selector.py       # NEW: Select key frames for embedding
├── ocr_engine.py           # NEW: EasyOCR wrapper with bounding boxes
├── pii_detector.py         # NEW: Regex + NER PII detection
├── redactor.py             # NEW: Apply blur/redaction to images
├── analyzer.py             # GPT-4o integration (updated prompt)
├── pdf_generator.py        # PDF creation (updated for images)
├── static/
│   ├── index.html          # Updated with review flow
│   ├── review.html         # NEW: Redaction review interface
│   └── style.css
├── temp/
│   ├── uploads/
│   ├── frames/
│   ├── redacted/           # NEW: Redacted frame versions
│   └── output/
├── requirements.txt        # Updated dependencies
└── README.md
```

## Implementation Details

### frame_selector.py - Key Frame Selection

```python
"""
Select which frames to embed in the PDF.
Not every frame needs to be included — pick frames that show distinct steps.
"""

def select_key_frames(frame_paths: list[str], max_embed: int = 10) -> list[str]:
    """
    Select key frames for PDF embedding.
    
    Strategy:
    1. Always include first and last frame
    2. Use image difference detection to find frames with significant UI changes
    3. Cap at max_embed frames
    
    Returns list of frame paths to embed.
    """
    from PIL import Image
    import numpy as np
    
    if len(frame_paths) <= max_embed:
        return frame_paths
    
    # Calculate difference scores between consecutive frames
    differences = []
    prev_img = None
    
    for path in frame_paths:
        img = Image.open(path).convert('L').resize((320, 180))  # Grayscale, small
        img_array = np.array(img)
        
        if prev_img is not None:
            diff = np.mean(np.abs(img_array - prev_img))
            differences.append(diff)
        else:
            differences.append(0)
        
        prev_img = img_array
    
    # Select frames with highest difference scores
    indexed_diffs = list(enumerate(differences))
    indexed_diffs.sort(key=lambda x: x[1], reverse=True)
    
    # Always include first and last
    selected_indices = {0, len(frame_paths) - 1}
    
    # Add highest-change frames until we hit max
    for idx, _ in indexed_diffs:
        if len(selected_indices) >= max_embed:
            break
        selected_indices.add(idx)
    
    # Return in original order
    return [frame_paths[i] for i in sorted(selected_indices)]
```

### ocr_engine.py - Text Extraction with Bounding Boxes

```python
"""
Extract text and bounding boxes from frames using EasyOCR.
"""

import easyocr
from dataclasses import dataclass

# Initialize once (loads model)
reader = easyocr.Reader(['en'], gpu=False)

@dataclass
class TextRegion:
    text: str
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float

def extract_text_regions(image_path: str) -> list[TextRegion]:
    """
    Extract all text regions from an image.
    
    Returns list of TextRegion with text content and bounding box coordinates.
    """
    results = reader.readtext(image_path)
    
    regions = []
    for bbox, text, confidence in results:
        # EasyOCR returns bbox as 4 corner points, convert to x1,y1,x2,y2
        x_coords = [p[0] for p in bbox]
        y_coords = [p[1] for p in bbox]
        
        regions.append(TextRegion(
            text=text,
            bbox=(int(min(x_coords)), int(min(y_coords)), 
                  int(max(x_coords)), int(max(y_coords))),
            confidence=confidence
        ))
    
    return regions
```

### pii_detector.py - PII Detection

```python
"""
Detect PII in extracted text regions.
"""

import re
from dataclasses import dataclass
from ocr_engine import TextRegion

@dataclass
class PIIMatch:
    region: TextRegion
    pii_type: str
    confidence: str  # 'high' or 'medium'
    matched_text: str

# High-confidence patterns (always applied)
PII_PATTERNS = {
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'phone': r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    'user_path_unix': r'/Users/[A-Za-z0-9_-]+',
    'user_path_windows': r'C:\\Users\\[A-Za-z0-9_-]+',
    'aws_key': r'\b(AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b',
    'api_key_openai': r'\bsk-[A-Za-z0-9]{32,}\b',
    'api_key_github': r'\bghp_[A-Za-z0-9]{36}\b',
}

# Optional patterns (user must enable)
OPTIONAL_PATTERNS = {
    'url': r'https?://[^\s<>"{}|\\^`\[\]]+',
    'date': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
}

def luhn_check(card_number: str) -> bool:
    """
    Validate credit card number using Luhn algorithm.
    Reduces false positives from random 16-digit numbers.
    """
    # Remove non-digits
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    
    return checksum % 10 == 0

def detect_pii(
    regions: list[TextRegion],
    enable_optional: list[str] = None
) -> list[PIIMatch]:
    """
    Scan text regions for PII patterns.
    
    Args:
        regions: List of TextRegion from OCR
        enable_optional: List of optional pattern names to enable
    
    Returns:
        List of PIIMatch with detected PII
    """
    enable_optional = enable_optional or []
    matches = []
    
    # Combine patterns
    active_patterns = dict(PII_PATTERNS)
    for name in enable_optional:
        if name in OPTIONAL_PATTERNS:
            active_patterns[name] = OPTIONAL_PATTERNS[name]
    
    for region in regions:
        for pii_type, pattern in active_patterns.items():
            found = re.findall(pattern, region.text, re.IGNORECASE)
            if found:
                matched_text = found[0] if isinstance(found[0], str) else found[0][0]
                
                # Additional validation for credit cards
                if pii_type == 'credit_card':
                    # Remove spaces/dashes for Luhn check
                    card_digits = ''.join(c for c in matched_text if c.isdigit())
                    if not luhn_check(card_digits):
                        continue  # Skip if Luhn check fails
                
                matches.append(PIIMatch(
                    region=region,
                    pii_type=pii_type,
                    confidence='high' if pii_type in PII_PATTERNS else 'medium',
                    matched_text=matched_text
                ))
    
    return matches


def detect_names_ner(regions: list[TextRegion]) -> list[PIIMatch]:
    """
    Use spaCy NER to detect person names.
    Separate function due to higher false-positive rate.
    """
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except:
        return []  # spaCy not installed or model missing
    
    matches = []
    
    for region in regions:
        doc = nlp(region.text)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                matches.append(PIIMatch(
                    region=region,
                    pii_type='person_name',
                    confidence='medium',
                    matched_text=ent.text
                ))
    
    return matches
```

### redactor.py - Apply Redactions

```python
"""
Apply blur/redaction to images at specified bounding boxes.
"""

from PIL import Image, ImageFilter, ImageDraw
from pii_detector import PIIMatch

def apply_redactions(
    image_path: str,
    output_path: str,
    pii_matches: list[PIIMatch],
    mode: str = 'blur'  # 'blur', 'black', 'pixelate'
) -> str:
    """
    Apply redactions to image and save to output path.
    
    Note: Redaction mode is global - applies to all frames and all PII matches.
    Users select one mode (blur/black/pixelate) that applies universally.
    
    Args:
        image_path: Source image
        output_path: Where to save redacted version
        pii_matches: List of PII matches with bounding boxes
        mode: Redaction style (global setting)
    
    Returns:
        Output path
    """
    img = Image.open(image_path)
    
    for match in pii_matches:
        bbox = match.region.bbox
        x1, y1, x2, y2 = bbox
        
        # Add padding around the detected region
        padding = 5
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(img.width, x2 + padding)
        y2 = min(img.height, y2 + padding)
        
        if mode == 'blur':
            # Extract region, blur heavily, paste back
            region = img.crop((x1, y1, x2, y2))
            blurred = region.filter(ImageFilter.GaussianBlur(radius=15))
            img.paste(blurred, (x1, y1))
            
        elif mode == 'black':
            # Draw black rectangle
            draw = ImageDraw.Draw(img)
            draw.rectangle([x1, y1, x2, y2], fill='black')
            
        elif mode == 'pixelate':
            # Pixelate by scaling down then up
            region = img.crop((x1, y1, x2, y2))
            small = region.resize((8, 8), Image.BILINEAR)
            pixelated = small.resize(region.size, Image.NEAREST)
            img.paste(pixelated, (x1, y1))
    
    img.save(output_path, quality=90)
    return output_path


def generate_preview(
    image_path: str,
    output_path: str,
    pii_matches: list[PIIMatch]
) -> str:
    """
    Generate preview image with red boxes around detected PII.
    Does NOT apply actual redaction — just shows what will be redacted.
    """
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    
    for match in pii_matches:
        bbox = match.region.bbox
        # Red box with label
        draw.rectangle(bbox, outline='red', width=3)
        draw.text(
            (bbox[0], bbox[1] - 15),
            match.pii_type,
            fill='red'
        )
    
    img.save(output_path, quality=90)
    return output_path
```

### Updated analyzer.py - GPT-4o with Frame References

```python
"""
Updated system prompt to reference embedded frames.
"""

SYSTEM_PROMPT_V2 = """You are a technical documentation writer creating a step-by-step how-to guide with embedded screenshots.

You will receive sequential screenshots from a screen recording. Some screenshots are marked as "KEY FRAME" — these will be embedded in the final PDF.

## Output Format

Return your response in this exact markdown structure:

# [Task Title - infer from what you see]

## Prerequisites
- [Any requirements visible or implied]

## Steps

### Step 1: [Action Title]
[FRAME:1]
**Action:** [Click/Type/Select/etc.]
**Location:** [Where in the UI]
**Details:** [Specific values, text to enter, options to select]

### Step 2: [Action Title]
[FRAME:3]
**Action:** ...
...continue for all steps...

## Notes
- [Any warnings, tips, or troubleshooting observed]

## Rules for Frame References
- Use [FRAME:N] tags to indicate which key frame should appear with each step
- Place the frame reference on its own line right after the step heading
- Not every step needs a frame — only include when the visual adds clarity
- A frame can be referenced in multiple steps if relevant
- Reference frames by their KEY FRAME number (1, 2, 3...), not the raw frame number

## Writing Rules
- Be concise but thorough
- Use exact text shown in UI for button names, menu items, field labels
- If you see error messages, include troubleshooting steps
- Assume reader is technical but unfamiliar with this specific process
- Note: Screenshots will have some text redacted for privacy — work around any blurred areas
"""

def analyze_frames_v2(
    all_frame_paths: list[str],
    key_frame_paths: list[str]
) -> str:
    """
    Send frames to Azure OpenAI GPT-4o with key frames marked.
    
    Args:
        all_frame_paths: All extracted frames in order (up to MAX_FRAMES)
        key_frame_paths: Subset of frames that will be embedded (up to MAX_KEY_FRAMES)
    
    Returns:
        Markdown string with [FRAME:N] references
    """
    from openai import AzureOpenAI
    import base64
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Initialize Azure OpenAI client
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    key_frame_set = set(key_frame_paths)
    key_frame_index = {path: i+1 for i, path in enumerate(key_frame_paths)}
    
    image_content = []
    for i, path in enumerate(all_frame_paths):
        # Mark key frames
        if path in key_frame_set:
            label = f"Frame {i+1} (KEY FRAME {key_frame_index[path]}):"
        else:
            label = f"Frame {i+1}:"
        
        image_content.append({"type": "text", "text": label})
        
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        
        image_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}
        })
    
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_V2},
            {"role": "user", "content": image_content}
        ],
        max_tokens=4096
    )
    
    return response.choices[0].message.content
```

### Updated pdf_generator.py - Embed Images

```python
"""
Updated PDF generator that embeds redacted screenshots.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.colors import HexColor
import re
import os

def generate_pdf_v2(
    markdown_content: str,
    output_path: str,
    redacted_frames: dict[int, str]  # {frame_number: redacted_image_path}
):
    """
    Generate PDF with embedded screenshots.
    
    Args:
        markdown_content: Markdown from GPT-4o with [FRAME:N] references
        output_path: Where to save PDF
        redacted_frames: Mapping of frame numbers to redacted image paths
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    
    # Add custom styles (same as v1.0)
    styles.add(ParagraphStyle(
        name='DocTitle', parent=styles['Title'],
        fontSize=20, spaceAfter=20, textColor=HexColor('#1a1a1a')
    ))
    styles.add(ParagraphStyle(
        name='SectionHead', parent=styles['Heading1'],
        fontSize=14, spaceBefore=15, spaceAfter=8, textColor=HexColor('#2563eb')
    ))
    styles.add(ParagraphStyle(
        name='StepHead', parent=styles['Heading2'],
        fontSize=12, spaceBefore=12, spaceAfter=6, textColor=HexColor('#1e40af')
    ))
    styles.add(ParagraphStyle(
        name='BodyText', parent=styles['Normal'],
        fontSize=10, spaceAfter=6, leading=14
    ))
    
    story = []
    lines = markdown_content.split('\n')
    
    # Check if any frame references exist
    has_frame_refs = any(re.search(r'\[FRAME:\d+\]', line) for line in lines)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for frame reference
        frame_match = re.match(r'\[FRAME:(\d+)\]', line)
        if frame_match:
            frame_num = int(frame_match.group(1))
            
            # Validate frame reference
            if frame_num <= 0:
                import logging
                logging.warning(f"Invalid frame reference: [FRAME:{frame_num}] - ignoring")
                continue
            
            if frame_num in redacted_frames:
                img_path = redacted_frames[frame_num]
                
                # Resize image: max 1200px width, maintain aspect ratio
                from PIL import Image as PILImage
                pil_img = PILImage.open(img_path)
                max_width_px = 1200
                
                if pil_img.width > max_width_px:
                    aspect_ratio = pil_img.height / pil_img.width
                    new_width = max_width_px
                    new_height = int(max_width_px * aspect_ratio)
                    pil_img = pil_img.resize((new_width, new_height), PILImage.LANCZOS)
                    # Save resized version temporarily
                    import tempfile
                    temp_path = tempfile.mktemp(suffix='.jpg')
                    pil_img.save(temp_path, quality=90)
                    img_path = temp_path
                
                # Calculate image width for PDF (max 5 inches, maintain aspect ratio)
                img = Image(img_path)
                aspect = img.imageHeight / img.imageWidth
                img_width = min(5*inch, 6.5*inch)  # Max width with margins
                img_height = img_width * aspect
                
                # Cap height too
                if img_height > 4*inch:
                    img_height = 4*inch
                    img_width = img_height / aspect
                
                img = Image(img_path, width=img_width, height=img_height)
                story.append(img)
                story.append(Spacer(1, 10))
            else:
                # Frame reference out of range - log warning, skip
                import logging
                logging.warning(f"Frame reference [FRAME:{frame_num}] not found in redacted_frames - ignoring")
            continue
        
        # Title
        if line.startswith('# ') and not line.startswith('## '):
            story.append(Paragraph(line[2:], styles['DocTitle']))
        # Section
        elif line.startswith('## '):
            story.append(Paragraph(line[3:], styles['SectionHead']))
        # Step
        elif line.startswith('### '):
            story.append(Paragraph(line[4:], styles['StepHead']))
        # Bold labels
        elif line.startswith('**') and ':**' in line:
            match = re.match(r'\*\*(.+?):\*\*\s*(.*)', line)
            if match:
                label, text = match.groups()
                story.append(Paragraph(f"<b>{label}:</b> {text}", styles['BodyText']))
        # Bullets
        elif line.startswith('- '):
            story.append(Paragraph(f"• {line[2:]}", styles['BodyText']))
        # Regular text
        else:
            story.append(Paragraph(line, styles['BodyText']))
    
    # If no frame references found, generate text-only PDF (backward compatible with v1.0)
    if not has_frame_refs and not redacted_frames:
        import logging
        logging.info("No [FRAME:N] tags found in markdown - generating text-only PDF")
    
    doc.build(story)
```

### static/review.html - Redaction Review Interface

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Review Redactions - Video to Doc</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 2rem;
            background: #f9fafb;
        }
        h1 { margin-bottom: 0.5rem; }
        .subtitle { color: #6b7280; margin-bottom: 1.5rem; }
        
        .controls {
            background: white;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            align-items: center;
        }
        .controls label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
        }
        
        .frame-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 1.5rem;
        }
        
        .frame-card {
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .frame-card img {
            width: 100%;
            max-width: 800px;
            display: block;
        }
        .loading {
            text-align: center;
            padding: 2rem;
            color: #6b7280;
        }
        .spinner {
            border: 3px solid #f3f4f6;
            border-top: 3px solid #2563eb;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .frame-info {
            padding: 1rem;
        }
        .frame-title {
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .pii-list {
            font-size: 0.875rem;
            color: #6b7280;
        }
        .pii-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.25rem 0;
        }
        .pii-item input { cursor: pointer; }
        .pii-type {
            background: #fef2f2;
            color: #dc2626;
            padding: 0.125rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
        }
        
        .actions {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            padding: 1rem 2rem;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .actions button {
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
        }
        .btn-secondary {
            background: white;
            border: 1px solid #d1d5db;
        }
        .btn-primary {
            background: #2563eb;
            color: white;
            border: none;
        }
        
        .redaction-mode {
            display: flex;
            gap: 0.5rem;
        }
        .redaction-mode button {
            padding: 0.5rem 1rem;
            border: 1px solid #d1d5db;
            background: white;
            border-radius: 4px;
            cursor: pointer;
        }
        .redaction-mode button.active {
            background: #2563eb;
            color: white;
            border-color: #2563eb;
        }
    </style>
</head>
<body>
    <h1>Review Redactions</h1>
    <p class="subtitle">Red boxes show detected PII. Uncheck items you don't want redacted.</p>
    <p style="font-size: 0.875rem; color: #6b7280; margin-top: -0.5rem;">
        Note: Manual redaction (drawing boxes) is not available in v2.0. If you need to redact something not detected, 
        consider re-uploading with the sensitive area cropped out, or edit the PDF afterward.
    </p>
    
    <div class="controls">
        <span>Redaction style (applies to all frames):</span>
        <div class="redaction-mode">
            <button class="active" data-mode="blur">Blur</button>
            <button data-mode="black">Black box</button>
            <button data-mode="pixelate">Pixelate</button>
        </div>
        
        <span style="margin-left: auto;">Optional detection:</span>
        <label><input type="checkbox" id="detectNames"> Person names</label>
        <label><input type="checkbox" id="detectUrls"> URLs</label>
    </div>
    
    <div class="frame-grid" id="frameGrid">
        <!-- Populated by JavaScript -->
    </div>
    
    <div class="actions">
        <button class="btn-secondary" onclick="location.href='/'">Cancel</button>
        <div>
            <span id="piiCount">0 items will be redacted</span>
            <button class="btn-primary" id="generateBtn">Generate PDF</button>
        </div>
    </div>
    
    <div style="height: 80px;"></div> <!-- Spacer for fixed footer -->

    <script>
        // JavaScript to:
        // 1. Fetch review data from /review/{job_id}
        // 2. Render frames with PII annotations
        // 3. Handle checkbox toggles
        // 4. Handle redaction mode changes
        // 5. Submit final decisions to /redactions/{job_id}
        // 6. Trigger PDF generation via /generate/{job_id}
        
        const jobId = new URLSearchParams(location.search).get('job_id');
        let reviewData = null;
        let redactionMode = 'blur';
        let ocrResults = null;  // Cache OCR results for re-detection
        
        async function loadReview() {
            const res = await fetch(`/review/${jobId}`);
            reviewData = await res.json();
            ocrResults = reviewData.ocr_results;  // Store for re-detection
            renderFrames();
        }
        
        function renderFrames() {
            const grid = document.getElementById('frameGrid');
            grid.innerHTML = reviewData.frames.map((frame, i) => `
                <div class="frame-card">
                    <img src="/frame/${jobId}/${frame.id}?preview=true" alt="Frame ${i+1}">
                    <div class="frame-info">
                        <div class="frame-title">Key Frame ${i+1}</div>
                        <div class="pii-list">
                            ${frame.pii.length === 0 ? '<em>No PII detected</em>' : 
                              frame.pii.map((p, j) => `
                                <div class="pii-item">
                                    <input type="checkbox" checked 
                                           data-frame="${frame.id}" 
                                           data-pii="${j}"
                                           onchange="updateCount()">
                                    <span class="pii-type">${p.type}</span>
                                    <span>${maskText(p.text)}</span>
                                </div>
                              `).join('')}
                        </div>
                    </div>
                </div>
            `).join('');
            updateCount();
        }
        
        function maskText(text) {
            if (text.length <= 4) return '••••';
            return text.slice(0, 2) + '••••' + text.slice(-2);
        }
        
        function updateCount() {
            const checked = document.querySelectorAll('.pii-item input:checked').length;
            document.getElementById('piiCount').textContent = 
                `${checked} item${checked !== 1 ? 's' : ''} will be redacted`;
        }
        
        document.querySelectorAll('.redaction-mode button').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelector('.redaction-mode .active').classList.remove('active');
                btn.classList.add('active');
                redactionMode = btn.dataset.mode;
            });
        });
        
        // Handle optional detection toggles - re-run PII detection
        document.getElementById('detectNames').addEventListener('change', async () => {
            await rerunDetection();
        });
        document.getElementById('detectUrls').addEventListener('change', async () => {
            await rerunDetection();
        });
        
        async function rerunDetection() {
            // Show loading spinner
            const grid = document.getElementById('frameGrid');
            grid.innerHTML = '<div class="loading"><div class="spinner"></div><p>Re-running PII detection...</p></div>';
            
            // Get enabled optional types
            const enabledOptional = [];
            if (document.getElementById('detectNames').checked) enabledOptional.push('person_name');
            if (document.getElementById('detectUrls').checked) enabledOptional.push('url');
            
            // Re-run detection with new settings
            const res = await fetch(`/review/${jobId}?rerun_detection=true`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ocr_results: ocrResults, enable_optional: enabledOptional})
            });
            
            reviewData = await res.json();
            renderFrames();
        }
        
        document.getElementById('generateBtn').addEventListener('click', async () => {
            // Collect redaction decisions
            const decisions = {};
            document.querySelectorAll('.pii-item input').forEach(input => {
                const frameId = input.dataset.frame;
                const piiIdx = input.dataset.pii;
                if (!decisions[frameId]) decisions[frameId] = [];
                decisions[frameId].push({
                    index: parseInt(piiIdx),
                    redact: input.checked
                });
            });
            
            // Submit
            await fetch(`/redactions/${jobId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({decisions, mode: redactionMode})
            });
            
            // Generate
            await fetch(`/generate/${jobId}`, {method: 'POST'});
            
            // Redirect to download
            location.href = `/?job_id=${jobId}&complete=true`;
        });
        
        loadReview();
    </script>
</body>
</html>
```

## Updated Requirements

```
# requirements.txt (v2.0)

# Core (same as v1.0)
fastapi==0.109.0
uvicorn==0.27.0
python-multipart==0.0.6
openai==1.12.0
reportlab==4.1.0
python-dotenv==1.0.0

# New for v2.0
easyocr==1.7.1
Pillow==10.2.0
numpy==1.26.3

# Optional (for name detection)
spacy==3.7.2
# After install: python -m spacy download en_core_web_sm
```

## Configuration (New Options)

```
# .env file for v2.0

# Azure OpenAI (required)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Frame extraction (existing)
FRAME_INTERVAL=2            # Seconds between frame captures
MAX_FRAMES=50               # Max frames to send to GPT-4o

# v2.0 New Options
MAX_KEY_FRAMES=10           # Max screenshots to embed in PDF
REDACTION_MODE=blur         # Default: blur, black, or pixelate (global setting)
ENABLE_NAME_DETECTION=false # Use spaCy NER for person names (optional)
OCR_GPU=false               # Use GPU for EasyOCR (if available)
```

## Success Criteria (v2.0)

- [ ] Key frames automatically selected (high-change moments)
- [ ] PII detected with < 5% false negative rate on common patterns
- [ ] User can review and adjust redactions before PDF generation
- [ ] Redacted screenshots embedded in PDF at appropriate steps
- [ ] Processing time < 3 minutes for 2-minute video (prioritizes accuracy over speed)
- [ ] PDF file size reasonable (< 10MB for typical output)

## Token Cost Estimate (v2.0)

Same as v1.0 for GPT-4o analysis. Additional costs:
- EasyOCR: Free (local)
- spaCy NER: Free (local, optional)

## Known Limitations

- OCR accuracy depends on font size and clarity
- Regex patterns tuned for US formats (phone, SSN)
- Name detection has higher false positive rate
- Small or stylized text may be missed
- Non-English text not fully supported

## Error Handling & Fallbacks

The system uses graceful degradation to ensure documentation generation succeeds even if PII detection fails:

| Failure Scenario | Behavior |
|-----------------|----------|
| EasyOCR fails to initialize | Skip PII detection, warn user "PII detection unavailable", still embed unredacted screenshots, continue with PDF generation |
| OCR returns no text for a frame | Treat frame as "no PII detected", continue normally |
| spaCy not installed | Name detection toggle disabled/grayed out in UI, other PII detection works normally |
| Individual frame OCR fails | Skip that frame's PII detection, log warning, continue with other frames |
| PII detection throws exception | Log error, continue without redactions, warn user in review page |

**Principle:** Documentation generation is the core value. PII redaction is a safety feature that should not block the workflow.

## Image Size/Quality Specifications

| Stage | Resolution | Notes |
|-------|------------|-------|
| OCR input | Original resolution | Full quality for better OCR accuracy |
| PDF embed | Max 1200px width | Maintain aspect ratio, resize after OCR |
| Preview in review.html | Max 800px width | Faster page load, smaller file size |

**Implementation:**
- OCR runs on original resolution images
- Resize happens after OCR, before PDF embed
- Use Pillow's `thumbnail()` with LANCZOS resampling for quality
- Images are resized to max 1200px width while maintaining aspect ratio

## Frame Reference Validation

The PDF generator handles invalid frame references gracefully:

| Issue | Behavior |
|-------|----------|
| `[FRAME:15]` when only 10 key frames | Ignore the tag, don't embed anything, log warning |
| No `[FRAME:N]` tags at all | Generate text-only PDF (backward compatible with v1.0) |
| `[FRAME:0]` or negative numbers | Ignore, log warning |
| Frame reference points to missing file | Skip that reference, log warning, continue |

**Principle:** Never crash or re-prompt GPT-4o. Skip invalid references and continue PDF generation.

## Migration from v1.0

v2.0 maintains **full backward compatibility** with v1.0 API endpoints:

### Backward Compatibility

**v1.0 Endpoints Still Work:**
- `POST /upload` - Unchanged
- `POST /process/{job_id}` - Enhanced but backward compatible
- `GET /status/{job_id}` - Enhanced with new status values
- `GET /download/{job_id}` - Unchanged

**v1.0 Flow Still Supported:**
- Upload → Process → Download (skips review, no screenshots embedded)
- Status goes: `uploaded` → `processing` → `complete`

**v2.0 Flow Adds:**
- Upload → Process → Review → Generate → Download (includes review step)
- Status goes: `uploaded` → `processing` → `ready_for_review` → `complete`

**Frontend Decision Logic:**
- If `status == "ready_for_review"` → redirect to review page
- If `status == "complete"` → show download link
- Frontend can detect v2.0 features by checking for `has_pii_detections` in status response

### Upgrade Steps

1. **Install new dependencies:**
   ```bash
   pip install -r requirements.txt  # Updated with easyocr, Pillow, numpy
   ```

2. **Update environment variables:**
   - Keep existing Azure OpenAI variables
   - Add new v2.0 variables (MAX_KEY_FRAMES, REDACTION_MODE, etc.)

3. **Create new directories:**
   ```bash
   mkdir -p temp/redacted
   ```

4. **No code changes required** - existing v1.0 integrations continue to work

**Breaking Changes:** None. All changes are additive.
