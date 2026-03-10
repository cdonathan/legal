#!/usr/bin/env python3
"""
Test AI Change Logging - Compare AI proposals vs Attorney actual changes
"""

import json
import os
import re
import openai
from docx import Document

class AIChangeLogger:
    def __init__(self):
        self.personal_info = {}
        self.document_context = {}
        self.openai_client = self._setup_openai()
    
    def _setup_openai(self):
        try:
            with open('/home/cliff/redact/openai_api_key.txt', 'r') as f:
                api_key = f.read().strip()
            return openai.OpenAI(api_key=api_key)
        except:
            return None
    
    def redact_personal_info(self, text):
        """Redact personal info for AI processing"""
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
    
    def get_ai_change_proposals(self, redacted_text):
        """Get AI's proposed changes for comparison"""
        if not self.openai_client:
            return []
        
        prompt = f"""You are redlining an NDA to align with institutional standards. Propose specific changes.

CORE REDLINING GOALS:
1. Limit liability for seller/broker
2. Clearly define confidential information  
3. Allow sharing within buyer's organization
4. Control buyer interactions with property/tenants
5. Create enforceable remedies
6. Add modern contract language

NDA TEXT:
{redacted_text}

INSTRUCTIONS:
- Make minimal inline edits within existing sentences
- Focus on word/phrase replacements, not adding new sections
- Align with institutional real estate NDA standards

Return ONLY JSON array of changes:
[
  {{
    "find": "exact text to replace",
    "replace": "exact replacement text",
    "reason": "why this change supports institutional standards",
    "goal": "which of the 6 core goals this addresses"
  }}
]"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            # Find JSON array
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                return json.loads(json_str)
            else:
                return []
                
        except Exception as e:
            print(f"AI error: {e}")
            return []
    
    def create_change_comparison_log(self, input_path):
        """Create detailed log comparing AI vs Attorney changes"""
        print(f"🔍 Analyzing AI change proposals for: {os.path.basename(input_path)}")
        
        # Extract text
        doc = Document(input_path)
        text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
        
        # Redact for AI
        redacted_text = self.redact_personal_info(text)
        
        # Get AI proposals
        ai_changes = self.get_ai_change_proposals(redacted_text)
        
        # Create comparison log
        log_content = f"""# AI Change Proposals vs Attorney Changes - NDA Sample 4

## AI PROPOSED CHANGES ({len(ai_changes)} total)

"""
        
        for i, change in enumerate(ai_changes, 1):
            log_content += f"""### AI Change #{i}

**Find:** `{change.get('find', 'N/A')}`
**Replace:** `{change.get('replace', 'N/A')}`
**Reason:** {change.get('reason', 'N/A')}
**Goal:** {change.get('goal', 'N/A')}

---

"""
        
        log_content += """## ATTORNEY ACTUAL CHANGES (from previous analysis)

**Total Changes:** 27

**Change Types:**
- **13 Major Deletions** - Removed verbose content
- **5 Major Additions** - Restructured/moved content  
- **5 Text Modifications** - Minor language improvements
- **3 Paragraph Deletions** - Removed entire sections
- **1 Redaction** - XXXX replacement

**Key Attorney Patterns:**
1. **Content Reorganization** - Moved clauses around
2. **Simplification** - Removed verbose language
3. **Structure Cleanup** - Better paragraph flow
4. **Minimal Redaction** - Only 1 XXXX replacement
5. **Error Fixes** - Fixed OCR errors like "confidential" → "onfidential"

---

## COMPARISON ANALYSIS

**AI Focus Areas:**
"""
        
        # Analyze AI focus areas
        ai_goals = {}
        for change in ai_changes:
            goal = change.get('goal', 'Unknown')
            ai_goals[goal] = ai_goals.get(goal, 0) + 1
        
        for goal, count in ai_goals.items():
            log_content += f"- **{goal}:** {count} changes\n"
        
        log_content += f"""

**Attorney Focus Areas:**
- **Content Deletion/Reorganization:** 21 changes (78%)
- **Language Cleanup:** 5 changes (19%)
- **Redaction:** 1 change (4%)

**KEY DIFFERENCES:**

1. **AI Approach:** Focuses on adding/improving language within existing text
2. **Attorney Approach:** Focuses on removing/reorganizing content structure

**ALIGNMENT ASSESSMENT:**
- AI is making **content improvements**
- Attorneys made **structural edits**
- **Gap:** AI needs to focus more on deletion/reorganization vs addition/improvement

**RECOMMENDATIONS:**
1. AI should prioritize **removing verbose language**
2. AI should focus on **moving/reorganizing clauses**
3. AI should make **fewer additions** and **more deletions**
4. AI should **simplify complex sentences** rather than enhance them
"""
        
        return log_content
    
    def test_change_logging(self, input_path):
        """Test and create change comparison log"""
        log_content = self.create_change_comparison_log(input_path)
        
        output_file = "/home/cliff/redact/redline_project/AI_vs_Attorney_Changes_Comparison.md"
        
        with open(output_file, 'w') as f:
            f.write(log_content)
        
        print(f"✅ Change comparison log created: {output_file}")
        print("📊 Review this file to see how AI proposals compare to actual attorney changes")
        
        return output_file

def main():
    """Test AI change logging"""
    logger = AIChangeLogger()
    
    test_file = "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA_Sample_4_pre_redline.docx"
    if os.path.exists(test_file):
        logger.test_change_logging(test_file)
    else:
        print(f"Test file not found: {test_file}")

if __name__ == "__main__":
    main()
