#!/usr/bin/env python3
import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

def create_pdf(content, output_path):
    """Create PDF from text content"""
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Split content into paragraphs
    paragraphs = content.split('\n\n')
    
    for para in paragraphs:
        if para.strip():
            p = Paragraph(para.strip(), styles['Normal'])
            story.append(p)
            story.append(Spacer(1, 0.2*inch))
    
    doc.build(story)

def main():
    """Format all reassembled documents from phase4"""
    phase4_dir = Path('/mnt/c/seedJura/contracts/phase4')
    phase5_dir = Path('/mnt/c/seedJura/contracts/phase5')
    phase5_dir.mkdir(exist_ok=True)
    
    # Find all FINAL.txt files
    final_files = list(phase4_dir.glob('*_FINAL.txt'))
    
    if not final_files:
        print("No FINAL.txt files found in phase4")
        return
    
    print(f"Found {len(final_files)} files to format")
    
    for final_file in final_files:
        print(f"Formatting: {final_file.name}")
        
        # Read the reassembled content
        with open(final_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create output filenames
        base_name = final_file.stem.replace('_FINAL', '')
        txt_output = phase5_dir / f"{base_name}_FORMATTED_REDACTED.txt"
        pdf_output = phase5_dir / f"{base_name}_FORMATTED_REDACTED.pdf"
        
        # Save formatted text
        with open(txt_output, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Create PDF
        create_pdf(content, str(pdf_output))
        
        print(f"✓ Created: {txt_output.name}")
        print(f"✓ Created: {pdf_output.name}")
    
    print(f"\nPhase 5 complete! Formatted {len(final_files)} documents")

if __name__ == "__main__":
    main()
