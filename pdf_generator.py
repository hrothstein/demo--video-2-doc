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

