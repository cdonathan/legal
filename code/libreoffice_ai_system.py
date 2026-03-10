#!/usr/bin/env python3
"""
LibreOffice UNO API Line-Numbered AI System
Uses LibreOffice for proper document processing and line numbering
"""

import uno
import os
import sys
import time
import json
import openai
from com.sun.star.beans import PropertyValue

class LibreOfficeAISystem:
    def __init__(self):
        self.personal_info = {}
        self.openai_client = self._setup_openai()
        self.desktop = None
    
    def _setup_openai(self):
        try:
            with open('/home/cliff/redact/openai_api_key.txt', 'r') as f:
                api_key = f.read().strip()
            return openai.OpenAI(api_key=api_key)
        except:
            return None
    
    def start_libreoffice(self):
        """Start LibreOffice in headless mode"""
        print("   🔄 Starting LibreOffice...")
        os.system("libreoffice --headless --invisible --nodefault --nolockcheck --nologo --norestore --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' &")
        time.sleep(3)
        
        try:
            local_context = uno.getComponentContext()
            resolver = local_context.ServiceManager.createInstanceWithContext(
                "com.sun.star.bridge.UnoUrlResolver", local_context)
            
            context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
            self.desktop = context.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", context)
            
            print("   ✓ LibreOffice connected")
            return True
        except Exception as e:
            print(f"   ❌ LibreOffice connection failed: {e}")
            return False
    
    def create_property_value(self, name, value):
        """Create PropertyValue for LibreOffice"""
        prop = PropertyValue()
        prop.Name = name
        prop.Value = value
        return prop
    
    def add_line_numbers_to_document(self, input_path, output_path):
        """Use LibreOffice to add line numbers to document"""
        input_url = uno.systemPathToFileUrl(os.path.abspath(input_path))
        output_url = uno.systemPathToFileUrl(os.path.abspath(output_path))
        
        # Load document
        load_props = (self.create_property_value("Hidden", True),)
        doc = self.desktop.loadComponentFromURL(input_url, "_blank", 0, load_props)
        
        # Add line numbers using LibreOffice
        page_style = doc.getStyleFamilies().getByName("PageStyles").getByName("Standard")
        page_style.LineNumberCountLines = True
        page_style.LineNumberPosition = 0  # Left margin
        page_style.LineNumberDistance = 500  # Distance from text
        
        # Save with line numbers
        save_props = (
            self.create_property_value("FilterName", "MS Word 2007 XML"),
            self.create_property_value("Overwrite", True)
        )
        doc.storeAsURL(output_url, save_props)
        
        # Extract text with line numbers for AI analysis
        text_content = []
        text_cursor = doc.getText().createTextCursor()
        
        # Get all paragraphs
        paragraph_enum = doc.getText().createEnumeration()
        line_number = 1
        
        while paragraph_enum.hasMoreElements():
            paragraph = paragraph_enum.nextElement()
            if hasattr(paragraph, 'getString'):
                para_text = paragraph.getString().strip()
                if para_text:
                    # Redact personal info
                    redacted_text = self.redact_personal_info(para_text)
                    text_content.append(f"LINE {line_number:03d}: {redacted_text}")
                    line_number += 1
                else:
                    text_content.append(f"LINE {line_number:03d}: [EMPTY]")
                    line_number += 1
        
        doc.close(True)
        
        line_numbered_text = '\n'.join(text_content)
        
        # Save line-numbered text for AI analysis
        with open('/home/cliff/redact/redline_project/LibreOffice_Line_Numbered.txt', 'w') as f:
            f.write("# LibreOffice Line-Numbered Document\n\n")
            f.write(line_numbered_text)
        
        print(f"   ✓ Added line numbers, extracted {line_number-1} lines")
        return line_numbered_text
    
    def redact_personal_info(self, text):
        """Redact personal information"""
        import re
        redacted_text = text
        counter = 1
        
        patterns = [
            (r'\b[A-Z][A-Z\s&,\.]{3,}(?:LLC|INC|CORP|LP|LLP|COMPANY|CO\.)\b', 'COMPANY'),
            (r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln)[^,\n]*', 'ADDRESS'),
            (r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', 'DATE'),
            (r'\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b', 'NAME')
        ]
        
        for pattern, label in patterns:
            for match in re.finditer(pattern, text):
                if any(term in match.group().lower() for term in 
                      ['party', 'agreement', 'information', 'confidential']):
                    continue
                
                placeholder = f"[{label}_{counter}]"
                self.personal_info[placeholder] = match.group()
                redacted_text = redacted_text.replace(match.group(), placeholder, 1)
                counter += 1
        
        return redacted_text
    
    def get_ai_recommendations(self, line_numbered_text):
        """AI analyzes LibreOffice line-numbered document"""
        if not self.openai_client:
            return []
        
        # Load problems analysis and golden NDA
        with open('/home/cliff/redact/redline_project/Sample_2_Problems_Analysis.md', 'r') as f:
            problems_analysis = f.read()
        
        with open('/home/cliff/redact/redline_project/golden_nda.md', 'r') as f:
            golden_nda = f.read()
        
        prompt = f"""You are an attorney analyzing a LibreOffice line-numbered NDA. Provide PRECISE location instructions.

GOLDEN NDA STANDARD:
{golden_nda}

PROBLEMS IDENTIFIED:
{problems_analysis}

LIBREOFFICE LINE-NUMBERED NDA:
{line_numbered_text}

TASK: Provide precise change instructions using LibreOffice line numbers. Be SPECIFIC about locations.

Return ONLY JSON array:
[
  {{
    "problem_addressed": "Definition of Confidential Information",
    "change_type": "replace_text_on_line",
    "line_number": 5,
    "find_text": "exact text to find on that line",
    "replace_with": "exact replacement text",
    "reason": "why this fixes the problem",
    "priority": "HIGH"
  }},
  {{
    "problem_addressed": "Missing Purpose Clause",
    "change_type": "insert_after_line",
    "line_number": 3,
    "insert_text": "exact text to insert",
    "reason": "why this addresses the problem",
    "priority": "HIGH"
  }}
]

CRITICAL: Use EXACT line numbers from the LibreOffice line-numbered document. Address ALL high-priority problems."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            
            # Save AI recommendations
            with open('/home/cliff/redact/redline_project/LibreOffice_AI_Recommendations.md', 'w') as f:
                f.write("# LibreOffice AI Recommendations\n\n")
                f.write("**AI Analysis Output:**\n\n")
                f.write("```\n")
                f.write(content)
                f.write("\n```\n\n")
            
            # Extract JSON
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                recommendations = json.loads(json_str)
                
                # Add detailed recommendations
                with open('/home/cliff/redact/redline_project/LibreOffice_AI_Recommendations.md', 'a') as f:
                    f.write(f"**Parsed Recommendations:** {len(recommendations)}\n\n")
                    
                    for i, rec in enumerate(recommendations, 1):
                        f.write(f"## Recommendation {i}: {rec.get('problem_addressed', 'Unknown')}\n\n")
                        f.write(f"**Priority:** {rec.get('priority', 'UNKNOWN')}\n\n")
                        f.write(f"**Change Type:** {rec.get('change_type', 'unknown')}\n\n")
                        f.write(f"**Line Number:** {rec.get('line_number', 'N/A')}\n\n")
                        f.write(f"**Find Text:**\n```\n{rec.get('find_text', 'N/A')}\n```\n\n")
                        f.write(f"**Replace/Insert:**\n```\n{rec.get('replace_with', rec.get('insert_text', 'N/A'))}\n```\n\n")
                        f.write(f"**Reason:** {rec.get('reason', 'N/A')}\n\n")
                        f.write("---\n\n")
                
                return recommendations
            else:
                return []
                
        except Exception as e:
            print(f"AI recommendation error: {e}")
            return []
    
    def implement_with_libreoffice(self, original_path, recommendations, output_redlined, output_clean):
        """Use LibreOffice to implement AI recommendations with track changes"""
        original_url = uno.systemPathToFileUrl(os.path.abspath(original_path))
        redlined_url = uno.systemPathToFileUrl(os.path.abspath(output_redlined))
        clean_url = uno.systemPathToFileUrl(os.path.abspath(output_clean))
        
        # Create redlined version with track changes
        load_props = (self.create_property_value("Hidden", True),)
        doc = self.desktop.loadComponentFromURL(original_url, "_blank", 0, load_props)
        
        # Enable track changes
        doc.recordChanges(True)
        
        # Get text cursor
        text = doc.getText()
        cursor = text.createTextCursor()
        
        implemented_count = 0
        
        # Process recommendations
        for rec in recommendations:
            try:
                if rec.get('change_type') == 'replace_text_on_line':
                    # Find and replace text
                    replace_desc = doc.createReplaceDescriptor()
                    replace_desc.setSearchString(rec['find_text'])
                    replace_desc.setReplaceString(rec['replace_with'])
                    
                    if doc.replaceAll(replace_desc) > 0:
                        implemented_count += 1
                        print(f"   ✓ Replaced text on line {rec.get('line_number')}")
                
                elif rec.get('change_type') in ['insert_after_line', 'insert_at_end']:
                    # Insert text (simplified - at end for now)
                    cursor.gotoEnd(False)
                    text.insertString(cursor, f"\n{rec['insert_text']}", False)
                    implemented_count += 1
                    print(f"   ✓ Inserted text for {rec.get('problem_addressed')}")
                    
            except Exception as e:
                print(f"   ❌ Failed to implement {rec.get('problem_addressed')}: {e}")
        
        # Save redlined version
        save_props = (
            self.create_property_value("FilterName", "MS Word 2007 XML"),
            self.create_property_value("Overwrite", True)
        )
        doc.storeAsURL(redlined_url, save_props)
        
        # Create clean version (accept all changes)
        doc.getTrackedChanges().acceptAll()
        doc.storeAsURL(clean_url, save_props)
        
        doc.close(True)
        
        print(f"   ✓ LibreOffice implemented {implemented_count} recommendations")
        return implemented_count
    
    def stop_libreoffice(self):
        """Stop LibreOffice"""
        try:
            if self.desktop:
                self.desktop.terminate()
        except:
            pass
        os.system("pkill -f libreoffice")
    
    def process_nda(self, input_path):
        """Complete LibreOffice AI workflow"""
        print(f"🔄 Processing with LibreOffice: {os.path.basename(input_path)}")
        
        try:
            # Step 1: Start LibreOffice
            print("[█░░░░] Step 1: Starting LibreOffice...")
            if not self.start_libreoffice():
                return None, None
            
            # Step 2: Add line numbers and extract text
            print("[██░░░] Step 2: Adding line numbers with LibreOffice...")
            temp_numbered = "/tmp/line_numbered_temp.docx"
            line_numbered_text = self.add_line_numbers_to_document(input_path, temp_numbered)
            print(f"   ✓ Redacted {len(self.personal_info)} personal items")
            
            # Step 3: AI Analysis
            print("[███░░] Step 3: Getting AI recommendations...")
            recommendations = self.get_ai_recommendations(line_numbered_text)
            print(f"   ✓ AI provided {len(recommendations)} recommendations")
            
            # Step 4: LibreOffice Implementation
            print("[████░] Step 4: Implementing with LibreOffice track changes...")
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            redlined_path = f"/home/cliff/redact/redline_project/{base_name}_libreoffice_redlined.docx"
            clean_path = f"/home/cliff/redact/redline_project/{base_name}_libreoffice_clean-version.docx"
            
            implemented = self.implement_with_libreoffice(input_path, recommendations, redlined_path, clean_path)
            
            print("[█████] Step 5: Complete!")
            print("✅ LIBREOFFICE AI SYSTEM COMPLETE!")
            print(f"📝 Redlined: {os.path.basename(redlined_path)}")
            print(f"📄 Clean: {os.path.basename(clean_path)}")
            print(f"📋 Line-numbered: LibreOffice_Line_Numbered.txt")
            print(f"📋 AI Recommendations: LibreOffice_AI_Recommendations.md")
            print(f"🎯 AI recommended {len(recommendations)}, LibreOffice implemented {implemented}")
            
            return redlined_path, clean_path
            
        finally:
            # Always stop LibreOffice
            self.stop_libreoffice()

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 libreoffice_ai_system.py input.docx")
        sys.exit(1)
    
    processor = LibreOfficeAISystem()
    processor.process_nda(sys.argv[1])

if __name__ == "__main__":
    main()
