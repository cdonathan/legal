#!/usr/bin/env python3
import zipfile
import xml.etree.ElementTree as ET
import os
import glob

def extract_text_from_docx(docx_path):
    """Extract text from .docx file"""
    try:
        with zipfile.ZipFile(docx_path, 'r') as docx:
            xml_content = docx.read('word/document.xml')
            root = ET.fromstring(xml_content)
            
            # Extract all text nodes
            text_elements = []
            for elem in root.iter():
                if elem.text:
                    text_elements.append(elem.text)
            
            return ' '.join(text_elements)
    except Exception as e:
        return f"Error reading {docx_path}: {str(e)}"

def evaluate_documents():
    folder_path = "/home/cliff/redact/OneDrive_1_3-5-2026"
    docx_files = glob.glob(os.path.join(folder_path, "*.docx"))
    
    for docx_file in docx_files:
        if not docx_file.endswith(':Zone.Identifier'):
            print(f"\n{'='*60}")
            print(f"FILE: {os.path.basename(docx_file)}")
            print(f"{'='*60}")
            
            text_content = extract_text_from_docx(docx_file)
            print(text_content[:1000] + "..." if len(text_content) > 1000 else text_content)

if __name__ == "__main__":
    evaluate_documents()
