#!/usr/bin/env python3
"""
Golden NDA Standard Analysis - What's wrong with Sample 2
"""

import openai
from docx import Document

def analyze_sample_2_against_golden_standard():
    """Analyze Sample 2 against Golden NDA standard to identify what's wrong"""
    
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
    sample_2_text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
    
    # Load Golden NDA
    with open('/home/cliff/redact/redline_project/golden_nda.md', 'r') as f:
        golden_nda = f.read()
    
    prompt = f"""You are an experienced real estate attorney. The Golden NDA below represents the GOLD STANDARD for commercial real estate confidentiality agreements.

GOLDEN NDA (GOLD STANDARD):
{golden_nda}

SAMPLE 2 NDA TO ANALYZE:
{sample_2_text}

TASK: Analyze Sample 2 and identify what is WRONG with it compared to the Golden NDA standard.

Focus on:
- What legal protections are missing
- What language is inadequate or problematic
- What risks are left unaddressed
- What clauses are poorly structured
- What terms are vague or unenforceable

Create a detailed markdown report identifying all the problems with Sample 2.

Format your response as:

# What's Wrong with Sample 2 NDA

## Executive Summary
[Brief overview of major problems]

## Critical Legal Deficiencies

### 1. [Problem Category]
**Issue:** [What's wrong]
**Golden Standard:** [How Golden NDA handles this correctly]
**Risk:** [What legal/business risk this creates]
**Fix Required:** [What needs to be changed]

[Continue for all major problems]

## Structural Problems
[Issues with document organization, flow, clarity]

## Language Problems  
[Vague terms, ambiguous clauses, unenforceable language]

## Missing Protections
[Critical clauses completely absent]

## Risk Assessment
**High Risk Issues:** [List most critical problems]
**Medium Risk Issues:** [List moderate problems]
**Low Risk Issues:** [List minor problems]

## Conclusion
[Overall assessment of how far Sample 2 falls short of the gold standard]

Be thorough and critical. Identify every significant problem."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0.1
        )
        
        analysis = response.choices[0].message.content
        
        # Save analysis
        output_file = "/home/cliff/redact/redline_project/Sample_2_Problems_Analysis.md"
        
        with open(output_file, 'w') as f:
            f.write(analysis)
        
        print(f"✅ Golden standard analysis complete: {output_file}")
        print("\n📋 PREVIEW:")
        print("=" * 60)
        print(analysis[:2000] + "..." if len(analysis) > 2000 else analysis)
        
        return output_file
        
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        return None

if __name__ == "__main__":
    analyze_sample_2_against_golden_standard()
