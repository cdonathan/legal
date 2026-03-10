#!/usr/bin/env python3
import zipfile
import xml.etree.ElementTree as ET
import os
import re

def extract_text_from_docx(docx_path):
    try:
        with zipfile.ZipFile(docx_path, 'r') as docx:
            xml_content = docx.read('word/document.xml')
            root = ET.fromstring(xml_content)
            text_elements = []
            for elem in root.iter():
                if elem.text:
                    text_elements.append(elem.text)
            return ' '.join(text_elements)
    except Exception as e:
        return f"Error: {str(e)}"

def compare_documents():
    folder = "/home/cliff/redact/OneDrive_1_3-5-2026"
    
    # Document pairs
    pairs = [
        ("REDLINE_Conf_Agr_Sample1-pre-redline.docx", "REDLINE_Conf_Agr_Sample1.docx"),
        ("REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx", "REDLINE_Confidentiality Agreement_Sample_2.docx"),
        ("REDLINE - NDA -  Sample3_pre_redline.docx", "REDLINE - NDA -  Sample3.docx"),
        ("REDLINE - NDA_Sample_4_pre_redline.docx", "REDLINE - NDA_Sample_4.docx"),
        ("REDLINE_NDA_Sample5_pre_redline.docx", "REDLINE_NDA_Sample5.docx"),
        ("REDLINE - NDA_Sample_6_pre_redline.docx", "REDLINE - NDA_Sample_6.docx")
    ]
    
    for pre_file, post_file in pairs:
        pre_path = os.path.join(folder, pre_file)
        post_path = os.path.join(folder, post_file)
        
        if os.path.exists(pre_path) and os.path.exists(post_path):
            print(f"\n{'='*80}")
            print(f"COMPARING: {pre_file}")
            print(f"{'='*80}")
            
            pre_text = extract_text_from_docx(pre_path)
            post_text = extract_text_from_docx(post_path)
            
            # Find differences
            pre_words = pre_text.split()
            post_words = post_text.split()
            
            redacted_items = []
            for i, (pre_word, post_word) in enumerate(zip(pre_words, post_words)):
                if pre_word != post_word and ("XXX" in post_word or post_word == "[REDACTED]"):
                    redacted_items.append(f"'{pre_word}' -> '{post_word}'")
            
            print(f"REDACTED ITEMS ({len(redacted_items)}):")
            for item in redacted_items[:20]:  # Show first 20
                print(f"  {item}")
            
            if len(redacted_items) > 20:
                print(f"  ... and {len(redacted_items) - 20} more")

if __name__ == "__main__":
    compare_documents()
