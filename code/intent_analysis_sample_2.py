#!/usr/bin/env python3
"""
Intent-Based NDA Analysis - Analyze document against 10 strategic legal intents
"""

import openai
from docx import Document

def analyze_nda_against_intents():
    """Analyze Sample 2 against the 10 strategic legal intents"""
    
    # Setup OpenAI
    try:
        with open('/home/cliff/redact/openai_api_key.txt', 'r') as f:
            api_key = f.read().strip()
        client = openai.OpenAI(api_key=api_key)
    except:
        print("Error: OpenAI API key not found")
        return
    
    # Load Sample 2
    doc = Document('/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx')
    text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
    
    # Load Golden NDA for reference
    with open('/home/cliff/redact/redline_project/golden_nda.md', 'r') as f:
        golden_nda = f.read()
    
    prompt = f"""You are an experienced real estate attorney analyzing an NDA against strategic legal intents.

GOLDEN NDA STANDARD (for reference):
{golden_nda}

NDA TO ANALYZE:
{text}

THE 10 STRATEGIC LEGAL INTENTS:
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

For each intent, analyze:
- Does this NDA address this intent? (FULLY/PARTIALLY/MISSING)
- What specific language addresses it (quote exact text)
- How does it compare to the Golden NDA approach?
- What needs to be clarified, strengthened, or added?

CRITICAL: Focus on LEGAL INTENT, not mechanical clause matching.

Return analysis in this format:

**INTENT 1: Limit liability for seller/broker**
Status: [FULLY/PARTIALLY/MISSING]
Current language: [quote relevant text or "NONE FOUND"]
Golden NDA approach: [how Golden NDA handles this]
Gap analysis: [what's missing or needs improvement]
Recommended action: [specific change needed]

[Continue for all 10 intents]

**STRATEGIC SUMMARY:**
- Intents fully addressed: X/10
- Intents needing clarification: X/10  
- Intents completely missing: X/10
- Primary legal risks: [list top 3 risks this NDA leaves unaddressed]
- Priority fixes: [list top 3 changes needed to achieve attorney intent]"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0.1
        )
        
        analysis = response.choices[0].message.content
        
        # Save analysis
        output_file = "/home/cliff/redact/redline_project/Intent_Analysis_Sample_2.md"
        
        with open(output_file, 'w') as f:
            f.write(f"# Intent-Based NDA Analysis - Sample 2\n\n")
            f.write(f"**Document:** REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx\n")
            f.write(f"**Analysis Focus:** Strategic legal intents vs. mechanical clause matching\n\n")
            f.write("---\n\n")
            f.write(analysis)
        
        print(f"✅ Intent-based analysis complete: {output_file}")
        print("\n📋 PREVIEW:")
        print("=" * 60)
        print(analysis[:1500] + "..." if len(analysis) > 1500 else analysis)
        
        return output_file
        
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        return None

if __name__ == "__main__":
    analyze_nda_against_intents()
