#!/usr/bin/env python3
import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

def create_simple_pdf(text_file):
    """Create a simple PDF from text file"""
    try:
        # Read the text file
        with open(text_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Create output filename
        base_name = os.path.splitext(os.path.basename(text_file))[0]
        output_dir = '/mnt/c/seedJura/contracts/phase4'
        pdf_file = os.path.join(output_dir, f"{base_name}.pdf")
        
        # Create PDF
        doc = SimpleDocTemplate(pdf_file, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Add title
        title = Paragraph(f"<b>{base_name.replace('_', ' ')}</b>", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.2*inch))
        
        # Split content into paragraphs and add to PDF
        paragraphs = content.split('\n\n')
        for para in paragraphs[:50]:  # Limit to first 50 paragraphs to avoid timeout
            if para.strip():
                # Clean up the text for PDF
                clean_text = para.strip().replace('<', '&lt;').replace('>', '&gt;')
                p = Paragraph(clean_text, styles['Normal'])
                story.append(p)
                story.append(Spacer(1, 0.1*inch))
        
        # Build PDF
        doc.build(story)
        print(f"✓ Created PDF: {pdf_file}")
        return pdf_file
        
    except Exception as e:
        print(f"✗ PDF creation failed: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 simple_pdf.py <text_file>")
        sys.exit(1)
    
    text_file = sys.argv[1]
    if not os.path.exists(text_file):
        print(f"Error: File not found: {text_file}")
        sys.exit(1)
    
    create_simple_pdf(text_file)
