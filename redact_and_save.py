#!/usr/bin/env python3
import re
import os
from pathlib import Path
from redactor import ContractRedactor

def redact_contract_file(input_file, output_dir):
    """Redact a single contract and save to output directory"""
    redactor = ContractRedactor()
    
    print(f"Processing: {os.path.basename(input_file)}")
    
    # Extract text from file
    if input_file.endswith('.mhtml'):
        text = redactor.extract_text_from_mhtml(input_file)
    else:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    
    # Apply pattern-based redaction with [REDACTED]
    redacted_text = text
    pattern_findings = []
    
    for pattern, label in redactor.patterns:
        matches = list(re.finditer(pattern, redacted_text, re.IGNORECASE))
        for match in matches:
            pattern_findings.append({
                'type': 'pattern',
                'label': label,
                'text': match.group(),
                'start': match.start(),
                'end': match.end()
            })
            # Replace with [REDACTED] instead of [LABEL]
            redacted_text = redacted_text.replace(match.group(), '[REDACTED]', 1)
    
    # Apply whitelist-based flagging (but don't auto-redact)
    whitelist_findings = redactor.whitelist_redact(redacted_text)
    
    # Create output filename
    input_name = os.path.basename(input_file)
    name_without_ext = os.path.splitext(input_name)[0]
    output_file = os.path.join(output_dir, f"{name_without_ext}_REDACTED.txt")
    
    # Save redacted version in original format
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(redacted_text)
        
        # Add summary at end
        f.write("\n\n" + "=" * 50)
        f.write("\n=== REDACTION SUMMARY ===\n")
        f.write(f"Original file: {input_name}\n")
        f.write(f"Pattern redactions: {len(pattern_findings)}\n")
        f.write(f"Flagged terms: {len(whitelist_findings)}\n")
        f.write(f"\nPattern-based redactions ({len(pattern_findings)}):\n")
        for finding in pattern_findings:
            f.write(f"  {finding['label']}: {finding['text'][:50]}...\n")
        
        f.write(f"\nFlagged non-whitelisted terms ({len(set([f['text'] for f in whitelist_findings]))}):\n")
        unique_flagged = list(set([f['text'] for f in whitelist_findings]))[:50]
        f.write(f"  {', '.join(unique_flagged)}\n")
    
    print(f"Saved redacted version: {output_file}")
    return len(pattern_findings), len(whitelist_findings)

def main():
    # Process one contract as example
    contracts_dir = Path.home() / 'redact' / 'contracts'
    output_dir = '/mnt/c/seedJura/contracts/phase1'
    
    # Find first .mhtml file to process
    mhtml_files = list(contracts_dir.glob('*.mhtml'))
    if not mhtml_files:
        print("No .mhtml files found to process")
        return
    
    # Process the first contract
    input_file = str(mhtml_files[0])
    pattern_count, flagged_count = redact_contract_file(input_file, output_dir)
    
    print(f"\nRedaction complete!")
    print(f"Pattern redactions: {pattern_count}")
    print(f"Flagged terms: {flagged_count}")

if __name__ == "__main__":
    main()
