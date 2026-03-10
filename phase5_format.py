#!/usr/bin/env python3
import os
import re
import json
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def apply_redactions_to_original(original_file, redacted_content, output_file):
    """Apply redactions to original formatted document"""
    
    # Read original file
    with open(original_file, 'r', encoding='utf-8', errors='ignore') as f:
        original_content = f.read()
    
    # Extract the main document content (skip MIME headers)
    doc_start = original_content.find('<html')
    if doc_start == -1:
        doc_start = original_content.find('AGREEMENT')
    
    if doc_start > 0:
        document = original_content[doc_start:]
    else:
        document = original_content
    
    # Apply redactions from our pattern matching
    from redactor import ContractRedactor
    redactor = ContractRedactor()
    
    # Apply same patterns to the formatted document
    for pattern, label in redactor.patterns:
        document = re.sub(pattern, '[REDACT]', document, flags=re.IGNORECASE)
    
    # Clean up HTML encoding issues
    document = document.replace('=93', '"')
    document = document.replace('=94', '"')
    document = document.replace('=20', ' ')
    document = document.replace('=92', "'")
    document = document.replace('&nbsp;', ' ')
    
    # Remove excessive whitespace but preserve structure
    document = re.sub(r'\s+', ' ', document)
    document = re.sub(r'<p[^>]*>', '\n\n', document)
    document = re.sub(r'</p>', '', document)
    document = re.sub(r'<br[^>]*>', '\n', document)
    
    # Remove HTML tags but keep structure
    document = re.sub(r'<[^>]+>', '', document)
    
    # Fix paragraph spacing
    document = re.sub(r'\n\s*\n\s*\n+', '\n\n', document)
    
    # Save formatted redacted document
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(document.strip())
    
    return document.strip()

def create_pdf_from_text(text_content, pdf_file):
    """Create a PDF matching original document formatting exactly"""
    
    doc = SimpleDocTemplate(pdf_file, pagesize=letter, 
                          rightMargin=72, leftMargin=72, 
                          topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    
    # Match original Times New Roman, small size, no bold headers
    normal_style = ParagraphStyle(
        'OriginalNormal',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=9,  # Small like original
        spaceAfter=6,
        leftIndent=18,  # 4% indent like original
        alignment=0  # Left aligned
    )
    
    exhibit_style = ParagraphStyle(
        'ExhibitStyle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=9,
        spaceAfter=12,
        alignment=2  # Right aligned
    )
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=9,
        spaceAfter=12,
        alignment=1  # Center aligned
    )
    
    story = []
    
    # Split content into paragraphs
    paragraphs = text_content.split('\n\n')
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Handle EXHIBIT (right-aligned, bold)
        if 'EXHIBIT' in para and len(para) < 50:
            story.append(Paragraph(para, exhibit_style))
        
        # Handle main title (center-aligned, bold, underlined)
        elif 'AGREEMENT OF SALE AND PURCHASE' in para and len(para) < 100:
            story.append(Paragraph(f"<u>{para}</u>", title_style))
        
        # All other content - regular formatting with selective bold
        else:
            # Apply bold to specific terms only (like original)
            formatted_para = para
            
            # Bold specific legal terms
            bold_terms = [
                r'(THIS AGREEMENT OF SALE AND PURCHASE \([^)]+\))',
                r'(\([^)]*Seller[^)]*\))',
                r'(\([^)]*Buyer[^)]*\))',
                r'(\([^)]*Agreement[^)]*\))',
                r'(\([^)]*Effective Date[^)]*\))'
            ]
            
            for pattern in bold_terms:
                formatted_para = re.sub(pattern, r'<b>\1</b>', formatted_para)
            
            story.append(Paragraph(formatted_para, normal_style))
    
    doc.build(story)
    return pdf_file

def phase5_format_document(input_file):
    """Phase 5: Create properly formatted redacted document (text + PDF)"""
    print("=== PHASE 5: DOCUMENT FORMATTING ===")
    
    # Find the original file
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    if base_name.endswith('_FAST_REDACTED'):
        base_name = base_name[:-14]  # Remove _FAST_REDACTED suffix
    elif base_name.endswith('_REDACTED'):
        base_name = base_name[:-9]  # Remove _REDACTED suffix
    
    # Look for original in contracts directory
    contracts_dir = '/mnt/c/seedJura/contracts'
    original_file = None
    
    for ext in ['.mhtml', '.txt']:
        potential_original = os.path.join(contracts_dir, f"{base_name}{ext}")
        if os.path.exists(potential_original):
            original_file = potential_original
            break
    
    if not original_file:
        print(f"Could not find original file for {base_name}")
        return None
    
    # Create output directory
    output_dir = '/mnt/c/seedJura/contracts/phase5'
    os.makedirs(output_dir, exist_ok=True)
    
    # Read the redacted content (for reference)
    with open(input_file, 'r', encoding='utf-8') as f:
        redacted_content = f.read()
    
    # Create text output
    text_output = os.path.join(output_dir, f"{base_name}_FORMATTED_REDACTED.txt")
    formatted_text = apply_redactions_to_original(original_file, redacted_content, text_output)
    
    # Create PDF output
    pdf_output = os.path.join(output_dir, f"{base_name}_FORMATTED_REDACTED.pdf")
    
    try:
        create_pdf_from_text(formatted_text, pdf_output)
        print(f"Created formatted text: {os.path.basename(text_output)}")
        print(f"Created formatted PDF: {os.path.basename(pdf_output)}")
        return text_output, pdf_output
    except Exception as e:
        print(f"PDF creation failed: {e}")
        print(f"Created formatted text: {os.path.basename(text_output)}")
        return text_output, None

def main():
    # Find the latest phase4 output
    phase4_dir = '/mnt/c/seedJura/contracts/phase4'
    
    if not os.path.exists(phase4_dir):
        print("Phase 4 directory not found")
        return
    
    # Find REDACTED files from phase4
    redacted_files = list(Path(phase4_dir).glob('*_REDACTED.txt'))
    
    if not redacted_files:
        print("No REDACTED files found in phase4")
        return
    
    print(f"Found {len(redacted_files)} files to format")
    
    for redacted_file in redacted_files:
        print(f"Formatting: {redacted_file.name}")
        result = phase5_format_document(str(redacted_file))
        
        if result:
            if isinstance(result, tuple):
                text_file, pdf_file = result
                print(f"✓ Created: {os.path.basename(text_file)}")
                if pdf_file:
                    print(f"✓ Created: {os.path.basename(pdf_file)}")
            else:
                print(f"✓ Created: {os.path.basename(result)}")

if __name__ == "__main__":
    main()
