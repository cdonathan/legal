#!/usr/bin/env python3
"""
4-Call AI System for NDA Redlining
Call 1: Problem Identification | Call 2: Problem Prioritization | Call 3: Recommendation Creation | Call 4: Implementation Instructions
"""

import os
import sys
import subprocess
import json
import re
import openai
import time
from docx import Document
from docx.shared import RGBColor

class FourCallAISystem:
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
    
    def ai_call_1_problem_identification(self, redacted_text, base_name):
        """Call 1: Problem identification by comparing NDA to Golden NDA"""
        if not self.openai_client:
            return None
        
        # Load Golden NDA (from components folder)
        with open('/home/cliff/redact/redline_project/components/golden_nda_prioritized.md', 'r') as f:
            golden_nda = f.read()
        
        prompt = f"""You are an attorney comparing an NDA to the Golden NDA standard. Your ONLY job is to identify problems.

GOLDEN NDA STANDARD:
{golden_nda}

NDA TO ANALYZE:
{redacted_text}

TASK: Identify ALL problems by comparing this NDA to the Golden NDA. Do NOT worry about solutions or priorities yet.

Create a comprehensive problem list:

# Problem Identification Report

## Problems Found

### Problem 1: [Category]
**What's Missing/Wrong:** [Specific issue]
**Golden NDA Has:** [What the standard includes]
**Current NDA Has:** [What this NDA has instead, or "MISSING"]

### Problem 2: [Category]
**What's Missing/Wrong:** [Specific issue]
**Golden NDA Has:** [What the standard includes]
**Current NDA Has:** [What this NDA has instead, or "MISSING"]

[Continue for ALL problems found]

## Summary
**Total Problems Identified:** [Number]

Focus ONLY on identifying problems. Do NOT suggest solutions or prioritize yet."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.1
            )
            
            problems_content = response.choices[0].message.content
            
            # Save problems
            problems_file = f"/home/cliff/redact/redline_project/{base_name}_Call1_Problems.md"
            with open(problems_file, 'w') as f:
                f.write(problems_content)
            
            print(f"   ✓ Call 1 - Problem identification: {os.path.basename(problems_file)}")
            return problems_file, problems_content
            
        except Exception as e:
            print(f"   ❌ Call 1 error: {e}")
            return None, None
    
    def ai_call_2_problem_prioritization(self, problems_content, base_name):
        """Call 2: Problem prioritization using NDA prioritization"""
        if not self.openai_client:
            return None
        
        # Load prioritized Golden NDA (from components folder)
        with open('/home/cliff/redact/redline_project/components/golden_nda_prioritized.md', 'r') as f:
            prioritized_golden = f.read()
        
        prompt = f"""You are an attorney prioritizing problems using the NDA Prioritization rules.

PRIORITIZATION RULES:
{prioritized_golden}

PROBLEMS IDENTIFIED:
{problems_content}

TASK: Prioritize each problem using P1/P2/P3/P4 rules. Your ONLY job is prioritization.

Create prioritized problem list:

# Problem Prioritization Report

## P1 (Required) Problems - Must Fix
[List problems that are P1 according to prioritization rules]

### Problem: [Name]
**Priority:** P1
**Rule:** [Why this is P1 according to prioritization rules]
**Action Required:** [Must fix/Must add/Must modify]

## P2 (Conditional) Problems - Consider Fixing
[List problems that are P2]

### Problem: [Name]
**Priority:** P2
**Rule:** [Why this is P2 according to prioritization rules]
**Action Required:** [Add if missing and necessary]

## P3 (Situational) Problems - Leave Unchanged
[List problems that are P3]

## P4 (Structural) Problems - Reference Only
[List problems that are P4]

## Summary
**P1 Problems:** [Number] (Must fix)
**P2 Problems:** [Number] (Consider)
**P3 Problems:** [Number] (Leave alone)
**P4 Problems:** [Number] (Reference only)

Focus ONLY on prioritization. Do NOT suggest solutions yet."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.1
            )
            
            prioritized_content = response.choices[0].message.content
            
            # Save prioritized problems
            prioritized_file = f"/home/cliff/redact/redline_project/{base_name}_Call2_Prioritized.md"
            with open(prioritized_file, 'w') as f:
                f.write(prioritized_content)
            
            print(f"   ✓ Call 2 - Problem prioritization: {os.path.basename(prioritized_file)}")
            return prioritized_file, prioritized_content
            
        except Exception as e:
            print(f"   ❌ Call 2 error: {e}")
            return None, None
    
    def ai_call_3_recommendation_creation(self, prioritized_content, base_name):
        """Call 3: Recommendation creation using the 10 bullets"""
        if not self.openai_client:
            return None
        
        # The 10 strategic goals
        ten_bullets = """
1. Limit liability for the seller/broker
2. Clearly define what is and is not confidential
3. Ensure information can legally be shared within the buyer's organization
4. Allow legally required disclosures
5. Control how the buyer interacts with the property, tenants, or sources
6. Create enforceable remedies if confidentiality is breached
7. Add modern contract enforceability language
8. Establish clear scope of permitted use
9. Protect transaction flexibility (no obligation to complete deal)
10. Allocate risk appropriately between parties
"""
        
        prompt = f"""You are an attorney creating specific recommendations to address prioritized problems.

10 STRATEGIC GOALS:
{ten_bullets}

PRIORITIZED PROBLEMS:
{prioritized_content}

TASK: Create specific recommendations ONLY for P1 and essential P2 problems. Focus on which of the 10 goals each recommendation serves.

Create recommendation list:

# Recommendation Creation Report

## P1 Recommendations (Must Implement)

### Recommendation 1: [Problem Being Addressed]
**Strategic Goal:** [Which of the 10 bullets this serves]
**Recommendation:** [Specific action - add definition, insert clause, modify language, etc.]
**Justification:** [Why this specific recommendation addresses the problem]

### Recommendation 2: [Problem Being Addressed]
**Strategic Goal:** [Which of the 10 bullets this serves]
**Recommendation:** [Specific action]
**Justification:** [Why this addresses the problem]

[Continue for all P1 problems]

## P2 Recommendations (Consider Implementing)

### Recommendation: [Problem Being Addressed]
**Strategic Goal:** [Which of the 10 bullets this serves]
**Recommendation:** [Specific action]
**Justification:** [Why this might be needed]

## Summary
**P1 Recommendations:** [Number] (Must implement)
**P2 Recommendations:** [Number] (Consider)
**Strategic Goals Addressed:** [List which of the 10 bullets are covered]

Focus on creating SPECIFIC recommendations that serve the 10 strategic goals."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.1
            )
            
            recommendations_content = response.choices[0].message.content
            
            # Save recommendations
            recommendations_file = f"/home/cliff/redact/redline_project/{base_name}_Call3_Recommendations.md"
            with open(recommendations_file, 'w') as f:
                f.write(recommendations_content)
            
            print(f"   ✓ Call 3 - Recommendation creation: {os.path.basename(recommendations_file)}")
            return recommendations_file, recommendations_content
            
        except Exception as e:
            print(f"   ❌ Call 3 error: {e}")
            return None, None
    
    def ai_call_4_implementation_instructions(self, recommendations_content, redacted_text, base_name):
        """Call 4: Implementation instructions with line numbers"""
        if not self.openai_client:
            return None
        
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
                
                # Add detailed instructions
                with open(implementation_file, 'a') as f:
                    f.write(f"**Parsed Instructions:** {len(instructions)}\n\n")
                    
                    for i, inst in enumerate(instructions, 1):
                        f.write(f"## Instruction {i}: {inst.get('recommendation', 'Unknown')}\n\n")
                        f.write(f"**Change Type:** {inst.get('change_type', 'unknown')}\n\n")
                        f.write(f"**Line Number:** {inst.get('line_number', 'N/A')}\n\n")
                        f.write(f"**Find Text:**\n```\n{inst.get('find_text', 'N/A')}\n```\n\n")
                        f.write(f"**Replace/Insert:**\n```\n{inst.get('replace_with', inst.get('insert_text', 'N/A'))}\n```\n\n")
                        f.write(f"**Reason:** {inst.get('reason', 'N/A')}\n\n")
                        f.write("---\n\n")
                
                print(f"   ✓ Call 4 - Implementation instructions: {os.path.basename(implementation_file)}")
                return implementation_file, instructions
            else:
                print("   ❌ Could not parse implementation JSON")
                return implementation_file, []
                
        except Exception as e:
            print(f"   ❌ Call 4 error: {e}")
            return None, []
    
    def process_four_call_system(self, input_path):
        """Complete 4-call AI system"""
        print(f"🔄 4-Call AI System: {os.path.basename(input_path)}")
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
        
        # Call 1: Problem Identification
        print("[██░░░] Call 1: Problem identification...")
        problems_file, problems_content = self.ai_call_1_problem_identification(redacted_text, base_name)
        if not problems_content:
            return
        
        # Call 2: Problem Prioritization
        print("[███░░] Call 2: Problem prioritization...")
        prioritized_file, prioritized_content = self.ai_call_2_problem_prioritization(problems_content, base_name)
        if not prioritized_content:
            return
        
        # Call 3: Recommendation Creation
        print("[████░] Call 3: Recommendation creation...")
        recommendations_file, recommendations_content = self.ai_call_3_recommendation_creation(prioritized_content, base_name)
        if not recommendations_content:
            return
        
        # Call 4: Implementation Instructions
        print("[█████] Call 4: Implementation instructions...")
        implementation_file, instructions = self.ai_call_4_implementation_instructions(recommendations_content, redacted_text, base_name)
        
        # Step 5: Create documents with LibreOffice verification
        if instructions:
            print("[█████] Step 5: Creating documents with LibreOffice...")
            
            # Ensure LibreOffice is running
            print("   🔄 Ensuring LibreOffice is running...")
            os.system("pkill -f libreoffice")  # Kill any existing instances
            time.sleep(2)
            
            # Start LibreOffice with verification
            os.system("libreoffice --headless --invisible --nodefault --nolockcheck --nologo --norestore --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' &")
            time.sleep(5)
            
            # Test LibreOffice connection
            try:
                import uno
                from com.sun.star.beans import PropertyValue
                
                local_context = uno.getComponentContext()
                resolver = local_context.ServiceManager.createInstanceWithContext(
                    "com.sun.star.bridge.UnoUrlResolver", local_context)
                
                context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
                desktop = context.ServiceManager.createInstanceWithContext(
                    "com.sun.star.frame.Desktop", context)
                
                print("   ✓ LibreOffice connected successfully")
                
                # Now create documents with LibreOffice
                redlined_path, clean_path = self.create_libreoffice_documents(desktop, instructions, input_path, base_name)
                
            except Exception as e:
                print(f"   ❌ LibreOffice connection failed: {e}")
                redlined_path, clean_path = None, None
        else:
            redlined_path, clean_path = None, None
        
        print("✅ 4-CALL AI SYSTEM COMPLETE!")
        print(f"📋 Call 1 - Problems: {os.path.basename(problems_file) if problems_file else 'FAILED'}")
        print(f"📋 Call 2 - Prioritized: {os.path.basename(prioritized_file) if prioritized_file else 'FAILED'}")
        print(f"📋 Call 3 - Recommendations: {os.path.basename(recommendations_file) if recommendations_file else 'FAILED'}")
        print(f"📋 Call 4 - Implementation: {os.path.basename(implementation_file) if implementation_file else 'FAILED'}")
        print(f"🎯 Total implementation instructions: {len(instructions)}")
    
    def create_libreoffice_documents(self, desktop, instructions, original_path, base_name):
        """Create documents using LibreOffice UNO API"""
        import uno
        from com.sun.star.beans import PropertyValue
        
        def create_property(name, value):
            prop = PropertyValue()
            prop.Name = name
            prop.Value = value
            return prop
        
        try:
            # Load original document
            original_url = uno.systemPathToFileUrl(os.path.abspath(original_path))
            load_props = (create_property("Hidden", True),)
            doc = desktop.loadComponentFromURL(original_url, "_blank", 0, load_props)
            
            # Enable track changes (try different methods)
            try:
                doc.recordChanges(True)
            except:
                try:
                    doc.RecordChanges = True
                except:
                    print("   ⚠️ Could not enable track changes, continuing without")
            
            implemented_count = 0
            
            # Implement instructions
            for inst in instructions:
                try:
                    change_type = inst.get('change_type', '')
                    
                    if 'insert' in change_type:
                        insert_text = inst.get('insert_text', '')
                        text = doc.getText()
                        cursor = text.createTextCursor()
                        cursor.gotoEnd(False)
                        text.insertString(cursor, f"\n\n{insert_text}", False)
                        implemented_count += 1
                        print(f"   ✓ LibreOffice inserted: {change_type}")
                    
                    elif 'replace' in change_type:
                        find_text = inst.get('find_text', '')
                        replace_text = inst.get('replace_with', '')
                        
                        if find_text:
                            replace_desc = doc.createReplaceDescriptor()
                            replace_desc.setSearchString(find_text)
                            replace_desc.setReplaceString(replace_text)
                            
                            replaced = doc.replaceAll(replace_desc)
                            if replaced > 0:
                                implemented_count += 1
                                print(f"   ✓ LibreOffice replaced: {find_text} → {replace_text}")
                
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
            
            # Save redlined version
            redlined_path = f"/home/cliff/redact/redline_project/{base_name}_LibreOffice_Redlined.docx"
            redlined_url = uno.systemPathToFileUrl(os.path.abspath(redlined_path))
            
            save_props = (
                create_property("FilterName", "MS Word 2007 XML"),
                create_property("Overwrite", True)
            )
            doc.storeAsURL(redlined_url, save_props)
            
            # Create clean version
            doc.getTrackedChanges().acceptAll()
            clean_path = f"/home/cliff/redact/redline_project/{base_name}_LibreOffice_Clean.docx"
            clean_url = uno.systemPathToFileUrl(os.path.abspath(clean_path))
            doc.storeAsURL(clean_url, save_props)
            
            doc.close(True)
            
            print(f"   ✓ Created redlined: {os.path.basename(redlined_path)}")
            print(f"   ✓ Created clean: {os.path.basename(clean_path)}")
            print(f"   ✓ Implemented {implemented_count}/{len(instructions)} instructions")
            
            return redlined_path, clean_path
            
        except Exception as e:
            print(f"   ❌ LibreOffice document creation error: {e}")
            return None, None
        
        finally:
            try:
                desktop.terminate()
            except:
                pass
            os.system("pkill -f libreoffice")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 four_call_ai_system.py input.docx")
        sys.exit(1)
    
    system = FourCallAISystem()
    system.process_four_call_system(sys.argv[1])

if __name__ == "__main__":
    main()
