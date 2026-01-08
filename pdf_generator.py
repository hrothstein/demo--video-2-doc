from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.colors import HexColor
import re
import os
import logging
from PIL import Image as PILImage
import tempfile

logger = logging.getLogger(__name__)

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
    
    # Custom styles - only add if they don't already exist
    if 'DocTitle' not in styles.byName:
        styles.add(ParagraphStyle(
            name='DocTitle',
            parent=styles['Title'],
            fontSize=20,
            spaceAfter=20,
            textColor=HexColor('#1a1a1a')
        ))
    
    if 'SectionHead' not in styles.byName:
        styles.add(ParagraphStyle(
            name='SectionHead',
            parent=styles['Heading1'],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=8,
            textColor=HexColor('#2563eb')
        ))
    
    if 'StepHead' not in styles.byName:
        styles.add(ParagraphStyle(
            name='StepHead',
            parent=styles['Heading2'],
            fontSize=12,
            spaceBefore=12,
            spaceAfter=6,
            textColor=HexColor('#1e40af')
        ))
    
    if 'BodyText' not in styles.byName:
        styles.add(ParagraphStyle(
            name='BodyText',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            leading=14
        ))
    
    if 'BoldLabel' not in styles.byName:
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
            story.append(Spacer(1, 6))
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
    if 'DocTitle' not in styles.byName:
        styles.add(ParagraphStyle(
            name='DocTitle', parent=styles['Title'],
            fontSize=20, spaceAfter=20, textColor=HexColor('#1a1a1a')
        ))
    if 'SectionHead' not in styles.byName:
        styles.add(ParagraphStyle(
            name='SectionHead', parent=styles['Heading1'],
            fontSize=14, spaceBefore=15, spaceAfter=8, textColor=HexColor('#2563eb')
        ))
    if 'StepHead' not in styles.byName:
        styles.add(ParagraphStyle(
            name='StepHead', parent=styles['Heading2'],
            fontSize=12, spaceBefore=12, spaceAfter=6, textColor=HexColor('#1e40af')
        ))
    if 'BodyText' not in styles.byName:
        styles.add(ParagraphStyle(
            name='BodyText', parent=styles['Normal'],
            fontSize=10, spaceAfter=6, leading=14
        ))
    if 'BoldLabel' not in styles.byName:
        styles.add(ParagraphStyle(
            name='BoldLabel', parent=styles['Normal'],
            fontSize=10, spaceAfter=4, leading=14
        ))
    
    story = []
    lines = markdown_content.split('\n')
    
    # Check if any frame references exist
    has_frame_refs = any(re.search(r'\[FRAME:\d+\]', line) for line in lines)
    
    temp_files = []  # Track temp files for cleanup
    
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue
        
        # Check for frame reference
        frame_match = re.match(r'\[FRAME:(\d+)\]', line)
        if frame_match:
            frame_num = int(frame_match.group(1))
            
            # Validate frame reference
            if frame_num <= 0:
                logger.warning(f"Invalid frame reference: [FRAME:{frame_num}] - ignoring")
                continue
            
            if frame_num in redacted_frames:
                img_path = redacted_frames[frame_num]
                
                if not os.path.exists(img_path):
                    logger.warning(f"Frame image not found: {img_path} - skipping")
                    continue
                
                # Resize image: max 1200px width, maintain aspect ratio
                try:
                    pil_img = PILImage.open(img_path)
                    max_width_px = 1200
                    
                    if pil_img.width > max_width_px:
                        aspect_ratio = pil_img.height / pil_img.width
                        new_width = max_width_px
                        new_height = int(max_width_px * aspect_ratio)
                        pil_img = pil_img.resize((new_width, new_height), PILImage.LANCZOS)
                        # Save resized version temporarily
                        temp_path = tempfile.mktemp(suffix='.jpg')
                        pil_img.save(temp_path, quality=90)
                        temp_files.append(temp_path)
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
                except Exception as e:
                    logger.error(f"Failed to embed image {img_path}: {e}")
                    continue
            else:
                # Frame reference out of range - log warning, skip
                logger.warning(f"Frame reference [FRAME:{frame_num}] not found in redacted_frames - ignoring")
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
                story.append(Paragraph(f"<b>{label}:</b> {text}", styles['BoldLabel']))
        # Bullets
        elif line.startswith('- '):
            story.append(Paragraph(f"• {line[2:]}", styles['BodyText']))
        # Regular text
        else:
            story.append(Paragraph(line, styles['BodyText']))
    
    # If no frame references found, generate text-only PDF (backward compatible with v1.0)
    if not has_frame_refs and not redacted_frames:
        logger.info("No [FRAME:N] tags found in markdown - generating text-only PDF")
    
    doc.build(story)
    
    # Clean up temp files
    for temp_file in temp_files:
        try:
            os.remove(temp_file)
        except Exception:
            pass

