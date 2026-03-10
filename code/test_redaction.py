#!/usr/bin/env python3

import os
import sys
import subprocess
from docx import Document

class RedactionTester:
    def __init__(self):
        self.personal_info = {}
        self.patterns = [
            (r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', 'NAME'),  # Names like "John Smith"
            (r'\b\d{1,5}\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd)\b', 'ADDRESS'),  # Addresses
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL'),  # Emails
            (r'\(\d{3}\)\s*\d{3}-\d{4}', 'PHONE'),  # Phone numbers
            (r'\b\d{5}(?:-\d{4})?\b', 'ZIP'),  # ZIP codes
        ]
    
    def redact_text(self, text):
        """Apply redaction patterns to text"""
        import re
        
        redacted_text = text
        counter = 1
        
        for pattern, label in self.patterns:
            matches = list(re.finditer(pattern, redacted_text))
            for match in matches:
                placeholder = f"[{label}_{counter}]"
                if placeholder not in self.personal_info:
                    self.personal_info[placeholder] = match.group()
                    redacted_text = redacted_text.replace(match.group(), placeholder, 1)
                    counter += 1
        
        return redacted_text
    
    def restore_text(self, redacted_text):
        """Restore original PII from redacted text"""
        restored_text = redacted_text
        for placeholder, original in self.personal_info.items():
            restored_text = restored_text.replace(placeholder, original)
        return restored_text
    
    def test_redaction_cycle(self, input_docx):
        """Test complete redaction and restoration cycle"""
        print(f"🔄 Testing redaction cycle: {os.path.basename(input_docx)}")
        
        # Step 1: Convert DOCX to text
        print("Step 1: Converting DOCX to text...")
        text_content = self.docx_to_text(input_docx)
        if not text_content:
            print("❌ Failed to convert DOCX")
            return
        
        print(f"Original text length: {len(text_content)} chars")
        print(f"First 200 chars: {text_content[:200]}...")
        
        # Step 2: Apply redaction
        print("\nStep 2: Applying redaction...")
        redacted_text = self.redact_text(text_content)
        print(f"Found {len(self.personal_info)} PII items:")
        for placeholder, original in self.personal_info.items():
            print(f"  {placeholder} = {original}")
        
        print(f"Redacted text first 200 chars: {redacted_text[:200]}...")
        
        # Step 3: Create redacted DOCX
        print("\nStep 3: Creating redacted DOCX...")
        redacted_docx = "/tmp/test_redacted.docx"
        self.text_to_docx(redacted_text, redacted_docx)
        
        # Step 4: Restore PII
        print("\nStep 4: Testing PII restoration...")
        restored_text = self.restore_text(redacted_text)
        restored_docx = "/tmp/test_restored.docx"
        self.text_to_docx(restored_text, restored_docx)
        
        print(f"Restored text first 200 chars: {restored_text[:200]}...")
        
        # Step 5: Verify files exist
        print(f"\n✅ Files created:")
        print(f"  Redacted: {redacted_docx} ({os.path.getsize(redacted_docx)} bytes)")
        print(f"  Restored: {restored_docx} ({os.path.getsize(restored_docx)} bytes)")
        
        return redacted_docx, restored_docx
    
    def docx_to_text(self, docx_path):
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
    
    def text_to_docx(self, text, output_path):
        """Convert text to DOCX"""
        try:
            doc = Document()
            
            # Split text into paragraphs and add to document
            paragraphs = text.split('\n')
            for para_text in paragraphs:
                if para_text.strip():  # Skip empty lines
                    doc.add_paragraph(para_text.strip())
            
            doc.save(output_path)
            return True
        except Exception as e:
            print(f"DOCX creation error: {e}")
            return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 test_redaction.py <input.docx>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)
    
    tester = RedactionTester()
    redacted_file, restored_file = tester.test_redaction_cycle(input_file)
    
    print(f"\n🎯 Test complete! Check files:")
    print(f"  Original: {input_file}")
    print(f"  Redacted: {redacted_file}")
    print(f"  Restored: {restored_file}")

if __name__ == "__main__":
    main()
