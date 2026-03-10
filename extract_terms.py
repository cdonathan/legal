#!/usr/bin/env python3
import re
from pathlib import Path
from redactor import ContractRedactor

def extract_all_non_whitelisted():
    redactor = ContractRedactor()
    contracts_dir = Path.home() / 'redact' / 'contracts'
    
    all_terms = set()
    
    for file_path in contracts_dir.glob('*.mhtml'):
        print(f"Processing: {file_path.name}")
        
        text = redactor.extract_text_from_mhtml(str(file_path))
        redacted_text, _ = redactor.pattern_redact(text)
        whitelist_findings = redactor.whitelist_redact(redacted_text)
        
        for finding in whitelist_findings:
            all_terms.add(finding['text'].lower())
    
    # Sort alphabetically
    sorted_terms = sorted(all_terms)
    
    print(f"\n=== ALL NON-WHITELISTED TERMS ({len(sorted_terms)}) ===")
    for i, term in enumerate(sorted_terms, 1):
        print(f"{i:4d}. {term}")

if __name__ == "__main__":
    extract_all_non_whitelisted()
