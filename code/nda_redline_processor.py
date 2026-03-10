#!/usr/bin/env python3
"""
NDA Redlining System
Processes NDAs through: redaction -> AI redline -> track changes -> restore personal info
"""

import zipfile
import xml.etree.ElementTree as ET
import re
import json
import os
from datetime import datetime
import openai

class NDARedlineProcessor:
    def __init__(self):
        self.personal_info = {}
        self.openai_client = self._setup_openai()
    
    def _setup_openai(self):
        try:
            with open('/home/cliff/redact/openai_api_key.txt', 'r') as f:
                api_key = f.read().strip()
            return openai.OpenAI(api_key=api_key)
        except:
            print("Error: OpenAI API key not found")
            return None
    
    def extract_text_from_docx(self, docx_path):
        """Extract text from Word document"""
        with zipfile.ZipFile(docx_path, 'r') as docx:
            xml_content = docx.read('word/document.xml')
            root = ET.fromstring(xml_content)
            paragraphs = []
            for para in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                para_text = ""
                for text in para.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
                    if text.text:
                        para_text += text.text
                if para_text.strip():
                    paragraphs.append(para_text.strip())
            return paragraphs
    
    def redact_personal_info(self, text):
        """Step 1: Redact personal information and store for later restoration"""
        redacted_text = text
        counter = 1
        
        # Company names (capitalized sequences)
        company_pattern = r'\b[A-Z][A-Z\s&,\.]{2,}(?:LLC|INC|CORP|LP|LLP|COMPANY)\b'
        for match in re.finditer(company_pattern, text):
            placeholder = f"[COMPANY_{counter}]"
            self.personal_info[placeholder] = match.group()
            redacted_text = redacted_text.replace(match.group(), placeholder)
            counter += 1
        
        # Addresses
        address_pattern = r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln)[^,]*'
        for match in re.finditer(address_pattern, text):
            placeholder = f"[ADDRESS_{counter}]"
            self.personal_info[placeholder] = match.group()
            redacted_text = redacted_text.replace(match.group(), placeholder)
            counter += 1
        
        # Dates
        date_pattern = r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
        for match in re.finditer(date_pattern, text):
            placeholder = f"[DATE_{counter}]"
            self.personal_info[placeholder] = match.group()
            redacted_text = redacted_text.replace(match.group(), placeholder)
            counter += 1
        
        # Names (Title Case sequences)
        name_pattern = r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'
        for match in re.finditer(name_pattern, text):
            if not any(word in match.group().lower() for word in ['party', 'agreement', 'information']):
                placeholder = f"[NAME_{counter}]"
                self.personal_info[placeholder] = match.group()
                redacted_text = redacted_text.replace(match.group(), placeholder)
                counter += 1
        
        return redacted_text
    
    def ai_redline(self, redacted_text):
        """Step 2: Send redacted text to OpenAI for redlining"""
        if not self.openai_client:
            return redacted_text
        
        with open('/home/cliff/redact/redline_project/golden_nda.md', 'r') as f:
            golden_nda = f.read()
        
        with open('/home/cliff/redact/redline_project/nda_clause_library.md', 'r') as f:
            clause_library = f.read()
        
        prompt = f"""You are an experienced transactional attorney redlining an NDA. Apply minimal edits to align with institutional standards.

GOLDEN NDA REFERENCE:
{golden_nda[:2000]}...

CLAUSE LIBRARY:
{clause_library[:2000]}...

NDA TO REDLINE:
{redacted_text}

INSTRUCTIONS:
- Make minimal edits only
- Preserve original language when possible
- Add missing standard clauses if critical protections are missing
- Return the redlined version with clear markup showing changes
- Use [INSERT: text] for additions and [DELETE: text] for deletions
- Maintain legal balance between parties

Return only the redlined NDA text with markup."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return redacted_text
    
    def create_tracked_docx(self, original_text, redlined_text, output_path):
        """Step 3: Create Word document with track changes"""
        # Simple approach: create new document with redlined content
        # For full track changes, would need python-docx with revision tracking
        
        docx_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
<w:p><w:r><w:t>{redlined_text}</w:t></w:r></w:p>
</w:body>
</w:document>'''
        
        # Create minimal DOCX structure
        with zipfile.ZipFile(output_path, 'w') as docx:
            # Add required files
            docx.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''')
            
            docx.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''')
            
            docx.writestr('word/document.xml', docx_content)
    
    def restore_personal_info(self, redlined_text):
        """Step 4: Restore personal information"""
        restored_text = redlined_text
        for placeholder, original in self.personal_info.items():
            restored_text = restored_text.replace(placeholder, original)
        return restored_text
    
    def process_nda(self, input_docx_path):
        """Main processing pipeline"""
        print(f"Processing: {input_docx_path}")
        
        # Extract text
        paragraphs = self.extract_text_from_docx(input_docx_path)
        original_text = '\n\n'.join(paragraphs)
        
        # Step 1: Redact personal info
        print("Step 1: Redacting personal information...")
        redacted_text = self.redact_personal_info(original_text)
        print(f"Stored {len(self.personal_info)} personal info items")
        
        # Step 2: AI redlining
        print("Step 2: AI redlining...")
        redlined_text = self.ai_redline(redacted_text)
        
        # Step 3: Create tracked document
        base_name = os.path.splitext(os.path.basename(input_docx_path))[0]
        temp_output = f"/home/cliff/redact/redline_project/{base_name}_temp_redlined.docx"
        print("Step 3: Creating tracked document...")
        self.create_tracked_docx(original_text, redlined_text, temp_output)
        
        # Step 4: Restore personal info
        print("Step 4: Restoring personal information...")
        final_text = self.restore_personal_info(redlined_text)
        
        # Step 5: Save final document
        final_output = f"/home/cliff/redact/redline_project/{base_name}_redlined.docx"
        print("Step 5: Saving final document...")
        self.create_tracked_docx(original_text, final_text, final_output)
        
        print(f"Complete! Saved as: {final_output}")
        return final_output

if __name__ == "__main__":
    processor = NDARedlineProcessor()
    
    # Test with first NDA
    test_file = "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Conf_Agr_Sample1-pre-redline.docx"
    if os.path.exists(test_file):
        processor.process_nda(test_file)
    else:
        print(f"Test file not found: {test_file}")
