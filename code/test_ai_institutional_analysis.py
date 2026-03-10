#!/usr/bin/env python3
"""
Test AI Analysis with Specific Institutional Requirements
"""

import openai
from docx import Document

def test_ai_institutional_analysis():
    """Test AI's ability to analyze document against specific institutional requirements"""
    
    # Setup OpenAI
    try:
        with open('/home/cliff/redact/openai_api_key.txt', 'r') as f:
            api_key = f.read().strip()
        client = openai.OpenAI(api_key=api_key)
    except:
        print("Error: OpenAI API key not found")
        return
    
    # Load the document
    doc_path = "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA_Sample_4_pre_redline.docx"
    doc = Document(doc_path)
    text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
    
    prompt = f"""You are an experienced real estate attorney analyzing an NDA for institutional compliance.

DOCUMENT TO ANALYZE:
{text}

INSTITUTIONAL NDA REQUIREMENTS:
1. Clear definition of Confidential Information (financial data, strategy, customer lists, trade secrets, transaction discussions)
2. Standard legal exceptions (already known, public, third party, independently developed, legally required)
3. Advisor disclosure rights (investors, employees, attorneys, accountants, lenders, advisors)
4. Seller liability limitation ("no representation or warranty as to accuracy")
5. Injunctive relief clause ("unauthorized disclosure causes irreparable harm")
6. No transaction obligation clause ("NDA does not create transaction commitment")
7. Return/destruction of materials clause
8. Governing law and jurisdiction
9. Standard contract boilerplate (entire agreement, amendment, assignment, severability)
10. Broker protection (cannot contact tenants, must go through broker)

ANALYSIS TASK:
For each of the 10 requirements above, analyze this NDA and report:
- Is this requirement currently met? (YES/NO/PARTIAL)
- What specific changes are needed to meet institutional standards?
- Provide exact language that should be added, modified, or removed

Return your analysis in this format:

**REQUIREMENT 1: Clear Definition of Confidential Information**
Status: [YES/NO/PARTIAL]
Current language: [quote existing text or "MISSING"]
Needed changes: [specific changes required]
Recommended language: [exact text to add/modify]

[Continue for all 10 requirements]

**SUMMARY:**
- Requirements fully met: X/10
- Requirements needing changes: X/10
- Priority changes: [list top 3 most critical changes]

Focus on what specifically needs to change to meet institutional standards."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.1
        )
        
        analysis = response.choices[0].message.content
        
        # Save analysis
        output_file = "/home/cliff/redact/redline_project/AI_Institutional_Analysis_NDA_Sample_4.md"
        
        with open(output_file, 'w') as f:
            f.write(f"# AI Institutional NDA Analysis - Sample 4\n\n")
            f.write(f"**Document:** REDLINE - NDA_Sample_4_pre_redline.docx\n")
            f.write(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(analysis)
        
        print(f"✅ AI institutional analysis complete: {output_file}")
        print("\n📋 PREVIEW OF ANALYSIS:")
        print("=" * 60)
        print(analysis[:1000] + "..." if len(analysis) > 1000 else analysis)
        
        return output_file
        
    except Exception as e:
        print(f"❌ AI analysis error: {e}")
        return None

if __name__ == "__main__":
    from datetime import datetime
    test_ai_institutional_analysis()
