#!/usr/bin/env python3
import os
import sys
from redactor import ContractRedactor

def analyze_document(input_file):
    """Analyze document and show what will be processed"""
    print(f"Analyzing: {os.path.basename(input_file)}")
    
    # Extract text
    redactor = ContractRedactor()
    if input_file.endswith('.mhtml'):
        text = redactor.extract_text_from_mhtml(input_file)
    else:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    
    # Calculate chunks (character-based)
    chunk_size = 1000  # characters
    num_chunks = (len(text) + chunk_size - 1) // chunk_size
    
    # Quick pattern analysis
    redaction_count = 0
    for pattern, label in redactor.patterns:
        import re
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        redaction_count += len(matches)
    
    flagged = redactor.whitelist_redact(text)
    
    print(f"\n=== DOCUMENT ANALYSIS ===")
    print(f"Total characters: {len(text):,}")
    print(f"Total words: {len(text.split()):,}")
    print(f"Will create: {num_chunks} chunks ({chunk_size} characters each)")
    print(f"Pattern redactions found: {redaction_count}")
    print(f"Flagged terms: {len(flagged)}")
    
    return num_chunks, redaction_count, len(flagged)

def interactive_pipeline(input_file):
    """Interactive pipeline with user confirmation"""
    
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        return
    
    # Analyze first
    num_chunks, redactions, flagged = analyze_document(input_file)
    
    print(f"\n=== PROCESSING OPTIONS ===")
    print(f"1. Fast redaction (Pattern-only, <1 second)")
    print(f"2. Full pipeline with AI review (~{num_chunks * 10} seconds)")
    print(f"3. Cancel")
    
    choice = input("\nChoose option (1/2/3): ").strip()
    
    if choice == "1":
        print("\nRunning fast redaction...")
        # Fast redaction inline
        redactor = ContractRedactor()
        output_dir = '/mnt/c/seedJura/contracts/phase4'
        os.makedirs(output_dir, exist_ok=True)
        
        if input_file.endswith('.mhtml'):
            text = redactor.extract_text_from_mhtml(input_file)
        else:
            with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        
        # Apply pattern redaction
        redacted_text = text
        redaction_count = 0
        
        import re
        for pattern, label in redactor.patterns:
            matches = list(re.finditer(pattern, redacted_text, re.IGNORECASE))
            for match in matches:
                redacted_text = redacted_text.replace(match.group(), '[REDACT]', 1)
                redaction_count += 1
        
        # Save result
        input_name = os.path.basename(input_file)
        name_without_ext = os.path.splitext(input_name)[0]
        output_file = os.path.join(output_dir, f"{name_without_ext}_FAST_REDACTED.txt")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(redacted_text)
            f.write(f"\n\n=== REDACTION SUMMARY ===\n")
            f.write(f"Pattern redactions: {redaction_count}\n")
            f.write(f"Processing time: <1 second\n")
        
        print(f"✓ Complete! {redaction_count} redactions made")
        print(f"Output: {output_file}")
        
    elif choice == "2":
        confirm = input(f"\nAI review will take ~{num_chunks * 10} seconds ({num_chunks} chunks). Continue? (y/n): ")
        if confirm.lower() == 'y':
            import time
            print(f"\n[{time.strftime('%H:%M:%S')}] Starting full pipeline execution...")
            try:
                from pipeline import run_pipeline
                print(f"[{time.strftime('%H:%M:%S')}] Pipeline module imported successfully")
                result = run_pipeline(input_file)
                if result:
                    print(f"[{time.strftime('%H:%M:%S')}] Pipeline completed successfully!")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Pipeline failed!")
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Pipeline error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("Cancelled.")
            
    else:
        print("Cancelled.")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 interactive_pipeline.py <input_file>")
        print("Example: python3 interactive_pipeline.py contract.mhtml")
        return
    
    interactive_pipeline(sys.argv[1])

if __name__ == "__main__":
    main()
