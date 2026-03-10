#!/usr/bin/env python3
"""
LibreOffice-Only 4-Call System
No python-docx - uses LibreOffice UNO API for everything
"""

import os
import sys
import subprocess
import json
import re
import openai
import uno
import time
from com.sun.star.beans import PropertyValue

class LibreOfficeOnly4CallSystem:
    def __init__(self):
        self.personal_info = {}
        self.openai_client = self._setup_openai()
    
    def _setup_openai(self):
        try:
            with open('/home/cliff/redact/openai_api_key.txt', 'r') as f:
                api_key = f.read().strip()
            return openai.OpenAI(api_key=api_key)
        except:
            return None
    
    def create_property(self, name, value):
        """Create PropertyValue for LibreOffice"""
        prop = PropertyValue()
        prop.Name = name
        prop.Value = value
        return prop
    
    def start_libreoffice(self, port=2002):
        """Start LibreOffice in headless mode"""
        os.system(f"libreoffice --headless --invisible --nodefault --nolockcheck --nologo --norestore --accept='socket,host=localhost,port={port};urp;StarOffice.ServiceManager' &")
        time.sleep(3)
        
        try:
            local_context = uno.getComponentContext()
            resolver = local_context.ServiceManager.createInstanceWithContext(
                "com.sun.star.bridge.UnoUrlResolver", local_context)
            
            context = resolver.resolve(f"uno:socket,host=localhost,port={port};urp;StarOffice.ComponentContext")
            desktop = context.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", context)
            
            return desktop
        except Exception as e:
            print(f"   ❌ LibreOffice connection failed: {e}")
            return None
    
    def stop_libreoffice(self, desktop):
        """Stop LibreOffice"""
        try:
            if desktop:
                desktop.terminate()
        except:
            pass
        os.system("pkill -f libreoffice")
    
    def convert_with_libreoffice(self, input_path):
        """Convert document using LibreOffice"""
        output_dir = "/tmp"
        cmd = [
            'libreoffice', 
            '--headless', 
            '--convert-to', 'txt',
            '--outdir', output_dir,
            input_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            txt_file = os.path.join(output_dir, f"{base_name}.txt")
            
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content
        
        return None
    
    def redact_personal_info(self, text):
        """Redact personal information"""
        redacted_text = text
        counter = len(self.personal_info) + 1
        
        patterns = [
            (r'\b[A-Z][A-Z\s&,\.]{3,}(?:LLC|INC|CORP|LP|LLP|COMPANY|CO\.)\b', 'COMPANY'),
            (r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln)[^,\n]*', 'ADDRESS'),
            (r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', 'DATE'),
            (r'\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b', 'NAME')
        ]
        
        for pattern, label in patterns:
            for match in re.finditer(pattern, text):
                if any(term in match.group().lower() for term in 
                      ['party', 'agreement', 'information', 'confidential', 'broker', 'seller']):
                    continue
                
                placeholder = f"[{label}_{counter}]"
                if placeholder not in self.personal_info:
                    self.personal_info[placeholder] = match.group()
                    redacted_text = redacted_text.replace(match.group(), placeholder, 1)
                    counter += 1
        
        return redacted_text
    
    def ai_call_4_implementation_instructions(self, recommendations_content, redacted_text, base_name):
        """Call 4: Implementation instructions with line numbers"""
        if not self.openai_client:
            return None, []
        
        # Add line numbers to text
        lines = redacted_text.split('\n')
        numbered_lines = []
        line_number = 1
        
        for line in lines:
            if line.strip():
                numbered_lines.append(f"LINE {line_number:03d}: {line.strip()}")
                line_number += 1
        
        line_numbered_text = '\n'.join(numbered_lines)
        
        prompt = f"""You are an attorney providing precise implementation instructions.

RECOMMENDATIONS TO IMPLEMENT:
{recommendations_content}

LINE-NUMBERED NDA:
{line_numbered_text}

TASK: Convert recommendations into precise line-numbered implementation instructions.

Return ONLY JSON array:
[
  {{
    "recommendation": "Add definition of Confidential Information",
    "change_type": "insert_definition_section",
    "line_number": 1,
    "insert_text": "For purposes of this Agreement, 'Confidential Information' means...",
    "reason": "Addresses strategic goal #2 - clearly define confidential information"
  }},
  {{
    "recommendation": "Replace vague term",
    "change_type": "replace_term",
    "line_number": 5,
    "find_text": "Informational Materials",
    "replace_with": "Confidential Information",
    "reason": "Addresses strategic goal #2 - use consistent terminology"
  }}
]

Provide precise line numbers and exact text for each recommendation."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.1
            )
            
            implementation_content = response.choices[0].message.content
            
            # Save implementation instructions
            implementation_file = f"/home/cliff/redact/redline_project/{base_name}_Call4_Implementation.md"
            with open(implementation_file, 'w') as f:
                f.write(f"# Implementation Instructions\n\n")
                f.write("**AI Implementation Output:**\n\n")
                f.write("```json\n")
                f.write(implementation_content)
                f.write("\n```\n\n")
            
            # Parse JSON
            json_start = implementation_content.find('[')
            json_end = implementation_content.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = implementation_content[json_start:json_end]
                instructions = json.loads(json_str)
                
                print(f"   ✓ Call 4 - Implementation instructions: {os.path.basename(implementation_file)}")
                return implementation_file, instructions
            else:
                print("   ❌ Could not parse implementation JSON")
                return implementation_file, []
                
        except Exception as e:
            print(f"   ❌ Call 4 error: {e}")
            return None, []
    
    def create_documents_with_libreoffice(self, instructions, original_path, base_name):
        """Step 5: Use LibreOffice to create redlined and clean documents"""
        print("   🔄 Starting LibreOffice for document creation...")
        desktop = self.start_libreoffice(2002)
        
        if not desktop:
            return None, None
        
        try:
            # Load original document
            original_url = uno.systemPathToFileUrl(os.path.abspath(original_path))
            load_props = (self.create_property("Hidden", True),)
            doc = desktop.loadComponentFromURL(original_url, "_blank", 0, load_props)
            
            # Enable track changes for redlined version
            doc.recordChanges(True)
            
            implemented_count = 0
            
            # Implement each instruction
            for inst in instructions:
                try:
                    change_type = inst.get('change_type', '')
                    
                    if 'insert' in change_type:
                        # Insert new text
                        insert_text = inst.get('insert_text', '')
                        
                        # Get text cursor and insert at end
                        text = doc.getText()
                        cursor = text.createTextCursor()
                        cursor.gotoEnd(False)
                        text.insertString(cursor, f"\n\n{insert_text}", False)
                        
                        implemented_count += 1
                        print(f"   ✓ LibreOffice inserted: {change_type}")
                    
                    elif 'replace' in change_type:
                        # Replace text
                        find_text = inst.get('find_text', '')
                        replace_text = inst.get('replace_with', '')
                        
                        if find_text:
                            # Use LibreOffice find & replace
                            replace_desc = doc.createReplaceDescriptor()
                            replace_desc.setSearchString(find_text)
                            replace_desc.setReplaceString(replace_text)
                            
                            replaced = doc.replaceAll(replace_desc)
                            if replaced > 0:
                                implemented_count += 1
                                print(f"   ✓ LibreOffice replaced: {find_text} → {replace_text}")
                    
                except Exception as e:
                    print(f"   ❌ LibreOffice failed: {e}")
            
            # Save redlined version (with track changes)
            redlined_path = f"/home/cliff/redact/redline_project/{base_name}_LibreOffice_Redlined.docx"
            redlined_url = uno.systemPathToFileUrl(os.path.abspath(redlined_path))
            
            save_props = (
                self.create_property("FilterName", "MS Word 2007 XML"),
                self.create_property("Overwrite", True)
            )
            doc.storeAsURL(redlined_url, save_props)
            
            # Create clean version (accept all changes)
            doc.getTrackedChanges().acceptAll()
            
            clean_path = f"/home/cliff/redact/redline_project/{base_name}_LibreOffice_Clean.docx"
            clean_url = uno.systemPathToFileUrl(os.path.abspath(clean_path))
            doc.storeAsURL(clean_url, save_props)
            
            # Close document
            doc.close(True)
            
            print(f"   ✓ LibreOffice created redlined: {os.path.basename(redlined_path)}")
            print(f"   ✓ LibreOffice created clean: {os.path.basename(clean_path)}")
            print(f"   ✓ LibreOffice implemented {implemented_count}/{len(instructions)} instructions")
            
            return redlined_path, clean_path
            
        except Exception as e:
            print(f"   ❌ LibreOffice error: {e}")
            return None, None
        
        finally:
            self.stop_libreoffice(desktop)
    
    def restore_personal_info_with_libreoffice(self, doc_path):
        """Restore personal information using LibreOffice"""
        if not doc_path or not os.path.exists(doc_path):
            return
        
        desktop = self.start_libreoffice(2003)
        if not desktop:
            return
        
        try:
            # Load document
            doc_url = uno.systemPathToFileUrl(os.path.abspath(doc_path))
            load_props = (self.create_property("Hidden", True),)
            doc = desktop.loadComponentFromURL(doc_url, "_blank", 0, load_props)
            
            # Replace personal info placeholders
            for placeholder, original in self.personal_info.items():
                replace_desc = doc.createReplaceDescriptor()
                replace_desc.setSearchString(placeholder)
                replace_desc.setReplaceString(original)
                doc.replaceAll(replace_desc)
            
            # Save
            save_props = (
                self.create_property("FilterName", "MS Word 2007 XML"),
                self.create_property("Overwrite", True)
            )
            doc.storeAsURL(doc_url, save_props)
            doc.close(True)
            
        except Exception as e:
            print(f"   ❌ Personal info restore error: {e}")
        
        finally:
            self.stop_libreoffice(desktop)
    
    def process_libreoffice_only_system(self, input_path):
        """Complete LibreOffice-only 4-call system"""
        print(f"🔄 LibreOffice-Only 4-Call System: {os.path.basename(input_path)}")
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        
        # Convert document
        print("[█░░░░] Step 1: Converting document with LibreOffice...")
        text_content = self.convert_with_libreoffice(input_path)
        if not text_content:
            print("❌ LibreOffice conversion failed")
            return
        
        # Redact personal info
        redacted_text = self.redact_personal_info(text_content)
        print(f"   ✓ Redacted {len(self.personal_info)} personal items")
        
        # Use existing Call 3 recommendations for now
        recommendations_content = """
## P1 Recommendations (Must Implement)

### Recommendation 3: Definition of Confidential Information
**Strategic Goal:** Clearly define what is and is not confidential  
**Recommendation:** Insert a comprehensive definition of what constitutes "Confidential Information" within the agreement.  
**Justification:** A clear definition helps to avoid misunderstandings about what information is protected, ensuring that both parties are aligned on the scope of confidentiality.
"""
        
        # Call 4: Implementation Instructions
        print("[██░░░] Call 4: Implementation instructions...")
        implementation_file, instructions = self.ai_call_4_implementation_instructions(recommendations_content, redacted_text, base_name)
        
        # Step 5: LibreOffice document creation
        if instructions:
            print("[███░░] Step 5: Creating documents with LibreOffice...")
            redlined_path, clean_path = self.create_documents_with_libreoffice(instructions, input_path, base_name)
            
            # Restore personal info
            if redlined_path:
                print("[████░] Step 6: Restoring personal info...")
                self.restore_personal_info_with_libreoffice(redlined_path)
            if clean_path:
                self.restore_personal_info_with_libreoffice(clean_path)
        else:
            redlined_path, clean_path = None, None
        
        print("✅ LIBREOFFICE-ONLY 4-CALL SYSTEM COMPLETE!")
        print(f"📋 Call 4 - Implementation: {os.path.basename(implementation_file) if implementation_file else 'FAILED'}")
        print(f"📝 LibreOffice Redlined: {os.path.basename(redlined_path) if redlined_path else 'FAILED'}")
        print(f"📄 LibreOffice Clean: {os.path.basename(clean_path) if clean_path else 'FAILED'}")
        print(f"🎯 Total implementation instructions: {len(instructions)}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 libreoffice_only_4call_system.py input.docx")
        sys.exit(1)
    
    system = LibreOfficeOnly4CallSystem()
    system.process_libreoffice_only_system(sys.argv[1])

if __name__ == "__main__":
    main()
