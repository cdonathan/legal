#!/usr/bin/env python3

import re
import os
import sys
import subprocess
import secrets
import json
from docx import Document

class SimpleNDARedactor:
    def __init__(self):
        # Refined patterns for actual PII in NDAs with specific labels (order matters!)
        self.patterns = [
            # Email addresses (match first to avoid conflicts)
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL'),
            
            # Phone numbers
            (r'\(\d{3}\)\s*\d{3}-\d{4}', 'PHONE'),
            (r'\d{3}-\d{3}-\d{4}', 'PHONE'),
            
            # Full addresses (number + street name) - match before street alone
            (r'\b\d+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd)(?:\s*,\s*[A-Z][a-z]+)?(?:\s*,\s*[A-Z]{2})?\s*\d{5}?\b', 'ADDRESS'),
            
            # Street names (just the street part) - match after full addresses
            (r'\b[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd)\b', 'STREET'),
            
            # ZIP codes
            (r'\b\d{5}(?:-\d{4})?\b', 'ZIP'),
            
            # Specific company names (with business suffixes)
            (r'\b[A-Z][A-Za-z\s&]+(?:LLC|Inc|Corp|Corporation|Company|Co\.)\b', 'COMPANY'),
            
            # Dates in signature lines
            (r'\b\d{1,2}/\d{1,2}/\d{4}\b', 'DATE'),
            (r'\b\d{1,2}-\d{1,2}-\d{4}\b', 'DATE'),
            
            # Personal names (avoid common legal terms) - match last to avoid conflicts
            (r'\b(?!Real|Estate|This|Agreement|Property|Information|Party|Buyer|Seller|Company)[A-Z][a-z]+ [A-Z][a-z]+\b', 'PERSON'),
        ]
        
        self.hex_mapping = {}
    
    def generate_hex_id(self):
        """Generate a random 16-character hex ID"""
        return secrets.token_hex(8)
    
    def redact_text(self, text):
        """Apply redaction patterns with hex mappings"""
        redacted_text = text
        redactions_made = []
        
        for pattern, label in self.patterns:
            matches = list(re.finditer(pattern, redacted_text))
            for match in matches:
                original = match.group()
                hex_id = self.generate_hex_id()
                placeholder = f"[{label}:{hex_id}]"
                
                # Store mapping
                self.hex_mapping[hex_id] = {
                    'type': label,
                    'original': original,
                    'placeholder': placeholder
                }
                
                redacted_text = redacted_text.replace(original, placeholder, 1)
                redactions_made.append(f"{placeholder} (was: {original})")
        
        return redacted_text, redactions_made
    
    def save_mapping_file(self, output_path):
        """Save hex mapping to JSON file"""
        mapping_file = output_path.replace('.docx', '_mapping.json')
        with open(mapping_file, 'w') as f:
            json.dump(self.hex_mapping, f, indent=2)
        return mapping_file
    
    def restore_text(self, redacted_text):
        """Restore original text from hex mappings"""
        restored_text = redacted_text
        for hex_id, data in self.hex_mapping.items():
            restored_text = restored_text.replace(data['placeholder'], data['original'])
        return restored_text

def docx_to_text(docx_path):
    """Convert DOCX to text using LibreOffice"""
    try:
        cmd = ['libreoffice', '--headless', '--convert-to', 'txt', '--outdir', '/tmp', docx_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            base_name = os.path.splitext(os.path.basename(docx_path))[0]
            txt_file = f"/tmp/{base_name}.txt"
            
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    return f.read()
        return None
    except Exception as e:
        print(f"Conversion error: {e}")
        return None

def text_to_docx(text, output_path):
    """Convert text to DOCX"""
    try:
        doc = Document()
        
        # Split text into paragraphs
        paragraphs = text.split('\n')
        for para_text in paragraphs:
            if para_text.strip():
                doc.add_paragraph(para_text.strip())
        
        doc.save(output_path)
        return True
    except Exception as e:
        print(f"DOCX creation error: {e}")
        return False

def test_simple_redaction(input_docx):
    """Test simple NDA redaction with hex mappings"""
    print(f"🔄 Testing Simple NDA Redaction with Hex Mapping: {os.path.basename(input_docx)}")
    
    # Step 1: Convert to text
    print("Step 1: Converting DOCX to text...")
    original_text = docx_to_text(input_docx)
    if not original_text:
        print("❌ Failed to convert DOCX")
        return
    
    print(f"Original length: {len(original_text)} chars")
    print(f"Sample: {original_text[:300]}...")
    
    # Step 2: Apply redaction with hex mapping
    print("\nStep 2: Applying redaction with hex mapping...")
    redactor = SimpleNDARedactor()
    redacted_text, redactions = redactor.redact_text(original_text)
    
    print(f"Made {len(redactions)} redactions:")
    for redaction in redactions[:5]:  # Show first 5
        print(f"  {redaction}")
    if len(redactions) > 5:
        print(f"  ... and {len(redactions) - 5} more")
    
    print(f"Redacted sample: {redacted_text[:300]}...")
    
    # Step 3: Create redacted DOCX
    print("\nStep 3: Creating redacted DOCX...")
    redacted_docx = "/tmp/hex_redacted.docx"
    if text_to_docx(redacted_text, redacted_docx):
        print(f"✅ Created: {redacted_docx}")
        
        # Step 4: Save mapping file
        print("\nStep 4: Saving hex mapping file...")
        mapping_file = redactor.save_mapping_file(redacted_docx)
        print(f"✅ Created mapping: {mapping_file}")
        
        # Step 5: Show mapping sample
        print(f"\nMapping sample (first 3 entries):")
        count = 0
        for hex_id, data in redactor.hex_mapping.items():
            if count < 3:
                print(f"  {hex_id}: {data['type']} = '{data['original']}'")
                count += 1
        
        # Step 6: Test restoration
        print("\nStep 6: Testing restoration...")
        restored_text = redactor.restore_text(redacted_text)
        print(f"Restored sample: {restored_text[:300]}...")
        
        return redacted_docx, mapping_file
    else:
        print("❌ Failed to create redacted DOCX")
        return None, None

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 simple_nda_redaction.py <input.docx>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)
    
    result = test_simple_redaction(input_file)
    if result[0]:
        print(f"\n🎯 Success!")
        print(f"  Redacted file: {result[0]}")
        print(f"  Mapping file: {result[1]}")
    else:
        print("\n❌ Redaction failed")

if __name__ == "__main__":
    main()
