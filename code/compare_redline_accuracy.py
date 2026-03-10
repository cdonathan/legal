#!/usr/bin/env python3
"""
Compare AI Redlining Accuracy vs Attorney-Accepted Redlines
"""

import subprocess
import os

def convert_to_text(docx_path):
    """Convert docx to text for comparison"""
    try:
        output_path = f"/tmp/{os.path.basename(docx_path)}.txt"
        result = subprocess.run([
            'libreoffice', '--headless', '--convert-to', 'txt',
            '--outdir', '/tmp', docx_path
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    except Exception as e:
        print(f"Conversion error: {e}")
        return None

def compare_redlines(sample_name, original_path, ai_redlined_path, attorney_accepted_path):
    """Compare AI redlines vs attorney accepted"""
    print(f"\n{'='*60}")
    print(f"🔍 COMPARING {sample_name}")
    print(f"{'='*60}")
    
    # Convert all documents to text
    print("📄 Converting documents to text...")
    original_text = convert_to_text(original_path)
    ai_text = convert_to_text(ai_redlined_path)
    attorney_text = convert_to_text(attorney_accepted_path)
    
    if not all([original_text, ai_text, attorney_text]):
        print("❌ Failed to convert one or more documents")
        return
    
    print("✅ All documents converted successfully")
    
    # Basic comparison metrics
    print(f"\n📊 DOCUMENT LENGTHS:")
    print(f"Original: {len(original_text)} characters")
    print(f"AI Redlined: {len(ai_text)} characters")
    print(f"Attorney Accepted: {len(attorney_text)} characters")
    
    # Look for key attorney changes
    attorney_changes = []
    ai_changes = []
    
    # Check for common attorney patterns
    patterns_to_check = [
        "reasonable attorney's fees",
        "Confidential Information does not include",
        "publicly available",
        "independently developed",
        "Effective Date",
        "electronic signatures",
        "counterparts"
    ]
    
    print(f"\n🔍 PATTERN ANALYSIS:")
    for pattern in patterns_to_check:
        in_original = pattern.lower() in original_text.lower()
        in_ai = pattern.lower() in ai_text.lower()
        in_attorney = pattern.lower() in attorney_text.lower()
        
        status = "✅" if (in_ai == in_attorney) else "❌"
        print(f"{status} {pattern}:")
        print(f"   Original: {'Yes' if in_original else 'No'}")
        print(f"   AI: {'Yes' if in_ai else 'No'}")
        print(f"   Attorney: {'Yes' if in_attorney else 'No'}")
    
    # Save comparison files
    comparison_dir = "/home/cliff/redact/redline_project/comparisons"
    os.makedirs(comparison_dir, exist_ok=True)
    
    with open(f"{comparison_dir}/{sample_name}_original.txt", 'w') as f:
        f.write(original_text)
    with open(f"{comparison_dir}/{sample_name}_ai_redlined.txt", 'w') as f:
        f.write(ai_text)
    with open(f"{comparison_dir}/{sample_name}_attorney_accepted.txt", 'w') as f:
        f.write(attorney_text)
    
    print(f"\n💾 Comparison files saved to: {comparison_dir}")

def main():
    """Compare all available samples"""
    
    comparisons = [
        {
            "name": "SAMPLE_1",
            "original": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Conf_Agr_Sample1-pre-redline.docx",
            "ai_redlined": "/home/cliff/redact/redline_project/libreTest/REDLINE_Conf_Agr_Sample1-pre-redline_Smart_Attorney_Redlined.docx",
            "attorney_accepted": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Conf_Agr_Sample1_accepted.docx"
        },
        {
            "name": "SAMPLE_2",
            "original": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx",
            "ai_redlined": "/home/cliff/redact/redline_project/libreTest/REDLINE_Confidentiality Agreement_Sample_2_pre_redline_Smart_Attorney_Redlined.docx",
            "attorney_accepted": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Confidentiality Agreement_Sample_2_changes_accepted.docx"
        },
        {
            "name": "SAMPLE_3",
            "original": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA -  Sample3_pre_redline.docx",
            "ai_redlined": "/home/cliff/redact/redline_project/libreTest/REDLINE - NDA -  Sample3_pre_redline_Smart_Attorney_Redlined.docx",
            "attorney_accepted": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA -  Sample3_accepted.docx"
        },
        {
            "name": "SAMPLE_4",
            "original": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA_Sample_4_pre_redline.docx",
            "ai_redlined": "/home/cliff/redact/redline_project/libreTest/REDLINE - NDA_Sample_4_pre_redline_Smart_Attorney_Redlined.docx",
            "attorney_accepted": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA_Sample_4_accepted.docx"
        },
        {
            "name": "SAMPLE_6",
            "original": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA_Sample_6_pre_redline.docx",
            "ai_redlined": "/home/cliff/redact/redline_project/libreTest/REDLINE - NDA_Sample_6_pre_redline_Smart_Attorney_Redlined.docx",
            "attorney_accepted": "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA_Sample_6_accepted.docx"
        }
    ]
    
    print("🔍 STARTING REDLINE ACCURACY COMPARISON")
    print(f"📅 {len(comparisons)} samples to compare")
    
    for comp in comparisons:
        # Check if all files exist
        missing_files = []
        for key, path in comp.items():
            if key != "name" and not os.path.exists(path):
                missing_files.append(f"{key}: {path}")
        
        if missing_files:
            print(f"\n❌ {comp['name']}: Missing files:")
            for missing in missing_files:
                print(f"   {missing}")
            continue
        
        compare_redlines(
            comp["name"],
            comp["original"],
            comp["ai_redlined"], 
            comp["attorney_accepted"]
        )
    
    print(f"\n🎯 COMPARISON COMPLETE!")

if __name__ == "__main__":
    main()
