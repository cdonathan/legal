#!/usr/bin/env python3
"""
Working LibreOffice AI System - Simplified approach
"""

import os
import sys
import subprocess
import openai
import json
import re

class WorkingLibreOfficeAI:
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
    
    def convert_to_text_with_libreoffice(self, input_path):
        """Use LibreOffice to convert document to text"""
        output_dir = "/home/cliff/redact/redline_project"
        
        cmd = [
            'libreoffice', 
            '--headless', 
            '--convert-to', 'txt',
            '--outdir', output_dir,
            input_path
        ]
        
        print("   🔄 Converting document with LibreOffice...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Find the output file
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            txt_file = os.path.join(output_dir, f"{base_name}.txt")
            
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                print(f"   ✓ LibreOffice conversion successful")
                return content
            else:
                print(f"   ❌ Output file not found: {txt_file}")
                return None
        else:
            print(f"   ❌ LibreOffice conversion failed: {result.stderr}")
            return None
    
    def add_line_numbers(self, text):
        """Add line numbers to text content"""
        lines = text.split('\n')
        numbered_lines = []
        line_number = 1
        
        for line in lines:
            if line.strip():  # Only number non-empty lines
                # Redact personal info
                redacted_line = self.redact_personal_info(line.strip())
                numbered_lines.append(f"LINE {line_number:03d}: {redacted_line}")
                line_number += 1
            else:
                numbered_lines.append("")  # Keep empty lines for structure
        
        line_numbered_text = '\n'.join(numbered_lines)
        
        # Save for reference
        with open('/home/cliff/redact/redline_project/LibreOffice_Line_Numbered.txt', 'w') as f:
            f.write("# LibreOffice Line-Numbered Document\n\n")
            f.write(line_numbered_text)
        
        print(f"   ✓ Added line numbers to {line_number-1} lines")
        return line_numbered_text
    
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
    
    def get_ai_recommendations(self, line_numbered_text):
        """Get AI recommendations with line numbers"""
        if not self.openai_client:
            return []
        
        # Load problems analysis and golden NDA
        with open('/home/cliff/redact/redline_project/Sample_2_Problems_Analysis.md', 'r') as f:
            problems_analysis = f.read()
        
        with open('/home/cliff/redact/redline_project/golden_nda.md', 'r') as f:
            golden_nda = f.read()
        
        prompt = f"""You are an attorney analyzing a LibreOffice-processed, line-numbered NDA. Provide PRECISE location instructions.

GOLDEN NDA STANDARD:
{golden_nda}

PROBLEMS IDENTIFIED:
{problems_analysis}

LIBREOFFICE LINE-NUMBERED NDA:
{line_numbered_text}

TASK: Provide precise change instructions using line numbers. Address ALL the high-priority problems identified.

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

CRITICAL: Use EXACT line numbers. Address the 7 high-priority problems from the analysis."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            
            # Save AI recommendations
            with open('/home/cliff/redact/redline_project/Working_LibreOffice_AI_Recommendations.md', 'w') as f:
                f.write("# Working LibreOffice AI Recommendations\n\n")
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
                with open('/home/cliff/redact/redline_project/Working_LibreOffice_AI_Recommendations.md', 'a') as f:
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
    
    def create_output_summary(self, recommendations, input_path):
        """Create summary of what would be implemented"""
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        
        summary_file = f"/home/cliff/redact/redline_project/{base_name}_LibreOffice_Implementation_Plan.md"
        
        with open(summary_file, 'w') as f:
            f.write(f"# LibreOffice AI Implementation Plan\n\n")
            f.write(f"**Document:** {os.path.basename(input_path)}\n")
            f.write(f"**Personal Items Redacted:** {len(self.personal_info)}\n")
            f.write(f"**AI Recommendations:** {len(recommendations)}\n\n")
            
            f.write("## Implementation Plan\n\n")
            
            for i, rec in enumerate(recommendations, 1):
                f.write(f"### Change {i}: {rec.get('problem_addressed', 'Unknown')}\n\n")
                f.write(f"**Priority:** {rec.get('priority', 'UNKNOWN')}\n")
                f.write(f"**Type:** {rec.get('change_type', 'unknown')}\n")
                f.write(f"**Location:** Line {rec.get('line_number', 'N/A')}\n\n")
                
                if rec.get('change_type') == 'replace_text_on_line':
                    f.write(f"**Action:** Replace text on line {rec.get('line_number')}\n")
                    f.write(f"**Find:** `{rec.get('find_text', 'N/A')[:100]}...`\n")
                    f.write(f"**Replace with:** `{rec.get('replace_with', 'N/A')[:100]}...`\n")
                elif rec.get('change_type') == 'insert_after_line':
                    f.write(f"**Action:** Insert after line {rec.get('line_number')}\n")
                    f.write(f"**Insert:** `{rec.get('insert_text', 'N/A')[:100]}...`\n")
                
                f.write(f"**Reason:** {rec.get('reason', 'N/A')}\n\n")
                f.write("---\n\n")
            
            f.write("## Next Steps\n\n")
            f.write("1. Review AI recommendations above\n")
            f.write("2. Implement changes using LibreOffice UNO API or manual editing\n")
            f.write("3. Create redlined and clean versions\n")
            f.write("4. Restore personal information\n")
        
        return summary_file
    
    def process_nda(self, input_path):
        """Complete working LibreOffice AI workflow"""
        print(f"🔄 Processing with Working LibreOffice AI: {os.path.basename(input_path)}")
        
        # Step 1: Convert with LibreOffice
        print("[█░░░░] Step 1: Converting document with LibreOffice...")
        text_content = self.convert_to_text_with_libreoffice(input_path)
        if not text_content:
            print("❌ LibreOffice conversion failed")
            return None, None
        
        # Step 2: Add line numbers
        print("[██░░░] Step 2: Adding line numbers...")
        line_numbered_text = self.add_line_numbers(text_content)
        print(f"   ✓ Redacted {len(self.personal_info)} personal items")
        
        # Step 3: AI Analysis
        print("[███░░] Step 3: Getting AI recommendations...")
        recommendations = self.get_ai_recommendations(line_numbered_text)
        print(f"   ✓ AI provided {len(recommendations)} recommendations")
        
        # Step 4: Create implementation plan
        print("[████░] Step 4: Creating implementation plan...")
        summary_file = self.create_output_summary(recommendations, input_path)
        
        print("[█████] Step 5: Complete!")
        print("✅ WORKING LIBREOFFICE AI SYSTEM COMPLETE!")
        print(f"📋 Line-numbered document: LibreOffice_Line_Numbered.txt")
        print(f"📋 AI Recommendations: Working_LibreOffice_AI_Recommendations.md")
        print(f"📋 Implementation Plan: {os.path.basename(summary_file)}")
        print(f"🎯 AI provided {len(recommendations)} precise recommendations")
        
        return summary_file, line_numbered_text

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 working_libreoffice_ai.py input.docx")
        sys.exit(1)
    
    processor = WorkingLibreOfficeAI()
    processor.process_nda(sys.argv[1])

if __name__ == "__main__":
    main()
