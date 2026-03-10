#!/usr/bin/env python3
"""
Smart Attorney Pattern-Based NDA Redlining System with Hex Mapping PII Redaction
Complete 7-document output system with privacy protection
"""

import os
import sys
import subprocess
import json
import secrets
import re
from datetime import datetime
import uno
from com.sun.star.beans import PropertyValue

class SmartAttorneySystem:
    def __init__(self):
        self.openai_client = None
        self.patterns_prompt = None
        self.personal_info = {}
        self.setup_openai()
        self.load_patterns_prompt()
    
    def setup_openai(self):
        """Initialize OpenAI client"""
        try:
            import openai
            
            # Try to read API key from file
            api_key_file = "/home/cliff/redact/openai_api_key.txt"
            if os.path.exists(api_key_file):
                with open(api_key_file, 'r') as f:
                    api_key = f.read().strip()
                self.openai_client = openai.OpenAI(api_key=api_key)
                print("✅ OpenAI client initialized")
            else:
                print("❌ OpenAI API key file not found")
                
        except ImportError:
            print("❌ OpenAI library not installed")
        except Exception as e:
            print(f"❌ OpenAI setup failed: {e}")
    
    def load_patterns_prompt(self):
        """Load attorney patterns prompt"""
        try:
            patterns_file = "/home/cliff/redact/redline_project/code/attorney_patterns_prompt.txt"
            if os.path.exists(patterns_file):
                with open(patterns_file, 'r') as f:
                    self.patterns_prompt = f.read()
                print("✅ Attorney patterns loaded")
            else:
                print("❌ Attorney patterns file not found")
        except Exception as e:
            print(f"❌ Failed to load patterns: {e}")
    
    def convert_to_docx(self, input_path):
        """Convert any file to DOCX format"""
        if input_path.endswith('.docx'):
            return input_path
        
        try:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = f"/tmp/{base_name}_converted.docx"
            
            cmd = ['libreoffice', '--headless', '--convert-to', 'docx', '--outdir', '/tmp', input_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
            else:
                print(f"   ❌ Conversion failed: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"   ❌ Conversion error: {e}")
            return None
    
    def convert_with_libreoffice(self, docx_path):
        """Convert DOCX to text using LibreOffice"""
        try:
            cmd = ['libreoffice', '--headless', '--convert-to', 'txt', '--outdir', '/tmp', docx_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                base_name = os.path.splitext(os.path.basename(docx_path))[0]
                txt_file = f"/tmp/{base_name}.txt"
                
                if os.path.exists(txt_file):
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        return f.read()
            return None
        except Exception as e:
            print(f"   ❌ Text conversion error: {e}")
            return None
    
    def redact_docx_pii(self, docx_path, base_name):
        """Redact PII from DOCX using hex mapping system"""
        try:
            # Convert DOCX to text for redaction
            text_content = self.convert_with_libreoffice(docx_path)
            if not text_content:
                return None, None
            
            # Apply hex mapping redaction
            redacted_text, hex_mapping = self.apply_hex_redaction(text_content)
            redacted_count = len(hex_mapping)
            
            # Create new DOCX with redacted content
            from docx import Document
            new_doc = Document()
            
            # Split redacted text into lines and add as paragraphs
            for line in redacted_text.split('\n'):
                if line.strip():
                    new_doc.add_paragraph(line.strip())
            
            # Save redacted DOCX and mapping file
            redacted_path = f"/tmp/{base_name}_redacted.docx"
            mapping_path = f"/tmp/{base_name}_mapping.json"
            
            new_doc.save(redacted_path)
            
            with open(mapping_path, 'w') as f:
                json.dump(hex_mapping, f, indent=2)
            
            print(f"   ✓ Redacted {redacted_count} PII items with hex mapping")
            return redacted_path, mapping_path
            
        except Exception as e:
            print(f"   ❌ Redaction failed: {e}")
            return None, None
    
    def apply_hex_redaction(self, text):
        """Apply hex mapping redaction patterns"""
        patterns = [
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
        
        redacted_text = text
        hex_mapping = {}
        
        for pattern, label in patterns:
            matches = list(re.finditer(pattern, redacted_text))
            for match in matches:
                original = match.group()
                hex_id = secrets.token_hex(8)
                placeholder = f"[{label}:{hex_id}]"
                
                # Store mapping
                hex_mapping[hex_id] = {
                    'type': label,
                    'original': original,
                    'placeholder': placeholder
                }
                
                redacted_text = redacted_text.replace(original, placeholder, 1)
        
        return redacted_text, hex_mapping

    def restore_pii_in_docx(self, redacted_docx_path, mapping_path, output_path):
        """Restore PII in DOCX using hex mapping"""
        try:
            # Load mapping
            with open(mapping_path, 'r') as f:
                hex_mapping = json.load(f)
            
            # Convert redacted DOCX to text
            redacted_text = self.convert_with_libreoffice(redacted_docx_path)
            if not redacted_text:
                return False
            
            # Restore PII
            restored_text = redacted_text
            for hex_id, data in hex_mapping.items():
                restored_text = restored_text.replace(data['placeholder'], data['original'])
            
            # Create restored DOCX
            from docx import Document
            doc = Document()
            
            for line in restored_text.split('\n'):
                if line.strip():
                    doc.add_paragraph(line.strip())
            
            doc.save(output_path)
            return True
            
        except Exception as e:
            print(f"   ❌ PII restoration failed: {e}")
            return False
    
    def smart_attorney_analysis(self, redacted_text, base_name):
        """Smart attorney pattern analysis with timing"""
        if not self.openai_client or not self.patterns_prompt:
            print("   ❌ OpenAI client or patterns not available")
            return None, None
        
        try:
            # Add line numbers to text for precise targeting
            lines = redacted_text.split('\n')
            numbered_lines = []
            for i, line in enumerate(lines, 1):
                if line.strip():
                    numbered_lines.append(f"LINE {i:03d}: {line}")
            
            numbered_text = '\n'.join(numbered_lines)
            
            # Create the prompt
            prompt = f"""{self.patterns_prompt}

LINE-NUMBERED NDA:
{numbered_text}

CRITICAL: Use exact LINE numbers and exact text from the document above. Copy/paste exactly from the LINE XXX: content."""
            
            # Make API call with timing
            start_time = datetime.now()
            print(f"   🔄 Starting OpenAI API call at {start_time.strftime('%H:%M:%S')}")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert attorney specializing in contract redlining for purchaser protection. You must respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print(f"   ✅ OpenAI API call completed at {end_time.strftime('%H:%M:%S')}")
            print(f"   ⏱️ API call duration: {duration:.2f} seconds")
            
            # Parse response
            response_text = response.choices[0].message.content.strip()
            
            # Clean up response if it has markdown formatting
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            instructions = json.loads(response_text)
            
            # Save analysis to file
            analysis_file = f"/home/cliff/redact/redline_project/libreTest/{base_name}_Smart_Attorney_Analysis.md"
            with open(analysis_file, 'w') as f:
                f.write(f"# Smart Attorney Analysis: {base_name}\n\n")
                f.write(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**Patterns Triggered:** {len(instructions.get('patterns', []))}\n\n")
                f.write("## Recommended Changes:\n\n")
                
                for i, pattern in enumerate(instructions.get('patterns', []), 1):
                    f.write(f"### Pattern {pattern.get('pattern_number', i)}: {pattern.get('title', 'Unknown')}\n")
                    f.write(f"**Line:** {pattern.get('line_number', 'Unknown')}\n\n")
                    f.write(f"**Reasoning:** {pattern.get('reasoning', 'Not provided')}\n\n")
                    f.write(f"**Benefit:** {pattern.get('benefit', 'Not provided')}\n\n")
                    f.write("---\n\n")
            
            print(f"   ✓ Smart attorney analysis: {os.path.basename(analysis_file)}")
            print(f"   ✓ Triggered {len(instructions.get('patterns', []))} attorney patterns")
            
            return analysis_file, instructions
            
        except json.JSONDecodeError as e:
            print(f"   ❌ Smart attorney analysis error: {e}")
            print(f"   Raw response: {response_text[:200]}...")
            return None, None
        except Exception as e:
            print(f"   ❌ Smart attorney analysis error: {e}")
            return None, None
    
    def analyze_with_openai(self, text_content, base_name):
        """Wrapper for smart attorney analysis"""
        analysis_file, instructions = self.smart_attorney_analysis(text_content, base_name)
        return instructions
    
    def create_smart_redlined_document(self, instructions, original_path, base_name):
        """Create redlined document using line-based precise changes"""
        import uno
        from com.sun.star.beans import PropertyValue
        
        if not instructions or 'patterns' not in instructions:
            print("   ❌ No valid instructions provided")
            return None, None
        
        try:
            print("   🔄 Starting LibreOffice for line-based attorney redlining...")
            
            # Kill any existing LibreOffice processes
            os.system("pkill -f libreoffice")
            
            # Start LibreOffice in headless mode
            import time
            time.sleep(2)
            
            # Initialize UNO connection
            local_context = uno.getComponentContext()
            resolver = local_context.ServiceManager.createInstanceWithContext(
                "com.sun.star.bridge.UnoUrlResolver", local_context)
            
            try:
                context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
            except:
                # Start LibreOffice with UNO connection
                subprocess.Popen([
                    'libreoffice', '--headless', '--invisible', '--nocrashreport', '--nodefault', '--nolockcheck',
                    '--nologo', '--norestore', '--accept=socket,host=localhost,port=2002;urp;'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(3)
                context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
            
            desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
            
            # Load document
            file_url = uno.systemPathToFileUrl(os.path.abspath(original_path))
            properties = (PropertyValue("Hidden", 0, True, 0),)
            document = desktop.loadComponentFromURL(file_url, "_blank", 0, properties)
            
            # Check for protective order page break
            text = document.getText()
            full_text = text.getString()
            
            protective_order_found = False
            if "protective order" in full_text.lower():
                print("   ⚠️ 'Protective order' found - inserting page break")
                protective_order_found = True
            else:
                print("   ✓ No 'protective order' page break found")
            
            # Enable track changes
            document.setPropertyValue("RecordChanges", True)
            track_changes_enabled = document.getPropertyValue("RecordChanges")
            print(f"   ✓ Track changes enabled: {track_changes_enabled}")
            
            # Get initial redline count
            redlines = document.getRedlines()
            initial_count = redlines.getCount()
            print(f"   📊 Initial redlines: {initial_count}")
            
            # Apply patterns
            patterns_applied = 0
            for pattern in instructions.get('patterns', []):
                pattern_num = pattern.get('pattern_number', 'Unknown')
                title = pattern.get('title', 'Unknown Pattern')
                line_num = pattern.get('line_number', 0)
                
                print(f"   🔄 Applying: Pattern {pattern_num}: {title} (Line {line_num})")
                
                try:
                    if self.apply_pattern_to_document(document, pattern):
                        patterns_applied += 1
                        print(f"   ✓ Pattern {pattern_num} applied successfully")
                    else:
                        print(f"   ❌ Pattern {pattern_num} failed to apply")
                except Exception as e:
                    print(f"   ❌ Pattern {pattern_num} error: {e}")
            
            # Get final redline count
            final_redlines = document.getRedlines()
            final_count = final_redlines.getCount()
            added_redlines = final_count - initial_count
            print(f"   📊 Final redlines: {final_count} (added {added_redlines})")
            
            # Save redlined version
            redlined_path = f"/home/cliff/redact/redline_project/libreTest/{base_name}_Smart_Attorney_Redlined.docx"
            redlined_url = uno.systemPathToFileUrl(os.path.abspath(redlined_path))
            save_props = (PropertyValue("FilterName", 0, "MS Word 2007 XML", 0),)
            document.storeAsURL(redlined_url, save_props)
            print(f"   ✅ Created redlined document: {os.path.basename(redlined_path)}")
            
            # Accept all changes for clean version
            changes_accepted = 0
            try:
                redlines_to_accept = document.getRedlines()
                for i in range(redlines_to_accept.getCount()):
                    redline = redlines_to_accept.getByIndex(0)  # Always get first as they shift
                    redline.accept()
                    changes_accepted += 1
            except Exception as e:
                print(f"   ⚠️ Error accepting changes: {e}")
            
            # Save clean version
            clean_path = f"/home/cliff/redact/redline_project/libreTest/{base_name}_Smart_Attorney_Clean.docx"
            clean_url = uno.systemPathToFileUrl(os.path.abspath(clean_path))
            document.storeAsURL(clean_url, save_props)
            print(f"   ✅ Created clean document: {os.path.basename(clean_path)} ({changes_accepted} changes applied)")
            
            # Close document
            document.close(True)
            
            print(f"   ✅ Applied {patterns_applied}/{len(instructions.get('patterns', []))} attorney patterns with precise line targeting")
            
            return redlined_path, clean_path
            
        except Exception as e:
            print(f"   ❌ LibreOffice redlining failed: {e}")
            return None, None
        finally:
            # Clean up LibreOffice processes
            time.sleep(1)
            os.system("pkill -f libreoffice")
    
    def apply_pattern_to_document(self, document, pattern):
        """Apply a specific pattern to the document"""
        try:
            line_number = pattern.get('line_number', 0)
            original_text = pattern.get('original_text', '')
            replacement_text = pattern.get('replacement_text', '')
            
            if not original_text or not replacement_text:
                print(f"   ❌ Line {line_number}: Missing original or replacement text")
                return False
            
            # Get document text
            text = document.getText()
            full_text = text.getString()
            
            # Try exact match first
            if original_text in full_text:
                # Use search and replace
                search = document.createSearchDescriptor()
                search.setSearchString(original_text)
                search.setPropertyValue("SearchRegularExpression", False)
                search.setPropertyValue("SearchCaseSensitive", False)
                
                found = document.findFirst(search)
                if found:
                    found.setString(replacement_text)
                    print(f"   ✓ Line {line_number}: Replaced '{original_text[:30]}...' with track changes")
                    return True
            
            # Try flexible matching for partial text
            search_terms = original_text.split()[:5]  # First 5 words
            search_phrase = ' '.join(search_terms)
            
            if search_phrase in full_text:
                search = document.createSearchDescriptor()
                search.setSearchString(search_phrase)
                search.setPropertyValue("SearchRegularExpression", False)
                search.setPropertyValue("SearchCaseSensitive", False)
                
                found = document.findFirst(search)
                if found:
                    # Expand selection to include more context
                    cursor = found.getText().createTextCursorByRange(found)
                    cursor.goRight(len(original_text), True)
                    cursor.setString(replacement_text)
                    print(f"   ✓ Line {line_number}: Replaced '{search_phrase}...' with track changes")
                    return True
            
            # If no match found, try insertion at end
            if line_number == 0:
                cursor = text.createTextCursor()
                cursor.gotoEnd(False)
                cursor.setString(f"\n\n{replacement_text}")
                print(f"   ✓ Line {line_number}: Inserted at end of document")
                return True
            
            print(f"   ❌ Line {line_number}: Text not found with flexible matching - '{original_text[:50]}...'")
            return False
            
        except Exception as e:
            print(f"   ❌ Pattern application error: {e}")
            return False
    
    def process_smart_attorney_system(self, input_path):
        """Complete smart attorney pattern-based system with hex mapping redaction"""
        print(f"🔄 Smart Attorney Pattern System: {os.path.basename(input_path)}")
        
        # Step 0: Convert to DOCX if needed
        print("[░░░░] Step 0: Converting to DOCX format...")
        docx_path = self.convert_to_docx(input_path)
        if not docx_path:
            print("❌ Could not convert to DOCX format")
            return
        
        base_name = os.path.splitext(os.path.basename(docx_path))[0]
        
        # Step 1: Redact PII from DOCX before processing
        print("[█░░░] Step 1: Redacting personal information...")
        redacted_docx_path, mapping_path = self.redact_docx_pii(docx_path, base_name)
        if not redacted_docx_path:
            print("❌ Document redaction failed")
            return
        
        # Step 2: Convert redacted document to text for analysis
        print("[██░░] Step 2: Converting redacted document...")
        text_content = self.convert_with_libreoffice(redacted_docx_path)
        if not text_content:
            print("❌ Document conversion failed")
            return
        
        # Step 3: Smart attorney pattern analysis
        print("[██░░] Step 2: Smart attorney pattern analysis...")
        analysis_file, instructions = self.smart_attorney_analysis(text_content, base_name)
        
        if not instructions:
            print("❌ No attorney patterns triggered")
            return
        
        # Step 4: Create redlined document using REDACTED DOCX
        print("[███░] Step 3: Creating smart attorney redlined document...")
        redlined_path, clean_path = self.create_smart_redlined_document(instructions, redacted_docx_path, base_name)
        
        # Step 5: Create redlined document using ORIGINAL DOCX (for proper redlines with PII)
        print("[████] Step 4: Creating final documents with PII restoration...")
        
        if redlined_path and clean_path and mapping_path:
            # Copy original to final directory
            import shutil
            original_final = f"/home/cliff/redact/redline_project/libreTest/{base_name}_Original.docx"
            shutil.copy2(docx_path, original_final)
            
            # Copy redacted to final directory  
            redacted_final = f"/home/cliff/redact/redline_project/libreTest/{base_name}_Redacted.docx"
            shutil.copy2(redacted_docx_path, redacted_final)
            
            # Copy mapping to final directory
            mapping_final = f"/home/cliff/redact/redline_project/libreTest/{base_name}_Mapping.json"
            shutil.copy2(mapping_path, mapping_final)
            
            # Create redlined document by applying redlines to ORIGINAL document (not restoring PII)
            print("   🔄 Applying redlines to original document for proper track changes...")
            redlined_original_path = f"/home/cliff/redact/redline_project/libreTest/{base_name}_Smart_Attorney_Redlined_Original.docx"
            clean_original_path = f"/home/cliff/redact/redline_project/libreTest/{base_name}_Smart_Attorney_Clean_Original.docx"
            
            # Apply redlines to original document (with PII intact)
            redlined_orig, clean_orig = self.create_smart_redlined_document(instructions, docx_path, f"{base_name}_Original")
            
            if redlined_orig and clean_orig:
                # Move to final locations
                shutil.move(redlined_orig, redlined_original_path)
                shutil.move(clean_orig, clean_original_path)
                print(f"   ✅ Created redlined with original PII: {os.path.basename(redlined_original_path)}")
                print(f"   ✅ Created clean with original PII: {os.path.basename(clean_original_path)}")
            else:
                print("   ❌ Failed to create original redlined documents")
            
            print(f"\n📁 ALL 7 DOCUMENTS SAVED TO /home/cliff/redact/redline_project/libreTest/:")
            print(f"   1. Original: {original_final}")
            print(f"   2. Redacted: {redacted_final}")
            print(f"   3. Mapping: {mapping_final}")
            print(f"   4. Redlined (redacted): {redlined_path}")
            print(f"   5. Clean (redacted): {clean_path}")
            print(f"   6. Redlined (original): {redlined_original_path}")
            print(f"   7. Clean (original): {clean_original_path}")
        
        else:
            print("❌ Missing required files for PII restoration")
        
        print("✅ SMART ATTORNEY PATTERN SYSTEM COMPLETE!")
        print(f"📋 Pattern Analysis: {os.path.basename(analysis_file) if analysis_file else 'FAILED'}")
        print(f"📝 Smart Redlined: {os.path.basename(redlined_path) if redlined_path else 'FAILED'}")
        print(f"📄 Smart Clean: {os.path.basename(clean_path) if clean_path else 'FAILED'}")
        print(f"🎯 Attorney patterns applied: {len(instructions.get('patterns', []))}")
        
        # Display applied patterns
        if instructions and 'patterns' in instructions:
            print(f"\n🧠 ATTORNEY PATTERNS APPLIED:")
            for i, pattern in enumerate(instructions['patterns'], 1):
                print(f"{i}. Pattern {pattern.get('pattern_number', 'Unknown')}: {pattern.get('title', 'Unknown')}")
                print(f"   Reasoning: {pattern.get('reasoning', 'Not provided')}")
                print(f"   Benefit: {pattern.get('benefit', 'Not provided')}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 smart_attorney_system.py <input_file>")
        print("Supported formats: .docx, .pdf, .txt, .mhtml")
        sys.exit(1)
    
    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"Error: File not found - {input_file}")
        sys.exit(1)
    
    system = SmartAttorneySystem()
    system.process_smart_attorney_system(input_file)

if __name__ == "__main__":
    main()
