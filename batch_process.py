#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import requests
from pathlib import Path

def ensure_ollama_running():
    """Ensure Ollama service is accessible (running on Windows)"""
    # Try localhost first, then Windows host IP
    urls_to_try = [
        'http://localhost:11434/api/tags',
        'http://127.0.0.1:11434/api/tags',
        'http://172.25.48.1:11434/api/tags'  # Windows host IP from WSL
    ]
    
    for url in urls_to_try:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✓ Ollama is accessible at {url}")
                return True
        except Exception as e:
            continue
    
    print("✗ Cannot connect to Ollama on Windows")
    print("Please ensure Ollama is running on Windows and accessible from WSL")
    return False

def batch_process_folder(input_folder):
    """Process all contract files in a folder through the complete pipeline"""
    
    if not os.path.exists(input_folder):
        print(f"Folder not found: {input_folder}")
        return
    
    # Ensure Ollama is running
    if not ensure_ollama_running():
        print("Cannot proceed without Ollama. Exiting.")
        return
    
    # Find all contract files
    input_path = Path(input_folder)
    contract_files = []
    
    for ext in ['*.mhtml', '*.txt']:
        contract_files.extend(input_path.glob(ext))
    
    # Filter out already processed files
    contract_files = [f for f in contract_files if not any(suffix in f.name for suffix in ['_REDACTED', '_FORMATTED', 'mapping'])]
    
    if not contract_files:
        print(f"No unprocessed contract files found in {input_folder}")
        return
    
    print(f"Found {len(contract_files)} files to process")
    
    processed_files = []
    failed_files = []
    
    # Process each file individually through the pipeline
    for i, contract_file in enumerate(contract_files, 1):
        print(f"\n=== PROCESSING FILE {i}/{len(contract_files)}: {contract_file.name} ===")
        
        try:
            # Run page pipeline for this file
            os.system(f'cd /home/cliff/redact && python3 page_pipeline.py "{contract_file}"')
            processed_files.append(contract_file.name)
            print(f"✓ Completed phases 1-2 for {contract_file.name}")
            
        except Exception as e:
            print(f"✗ Failed to process {contract_file.name}: {e}")
            failed_files.append(contract_file.name)
    
    # Run Phase 3 once for all chunks
    print(f"\n=== PHASE 3: PROCESSING ALL CHUNKS ===")
    os.system('cd /home/cliff/redact && python3 phase3_selective.py phi3.5')
    
    # Run Phase 4 reassembly
    print(f"\n=== PHASE 4: REASSEMBLING DOCUMENTS ===")
    os.system('cd /home/cliff/redact && python3 phase4_reassemble.py')
    
    # Run Phase 5 for all documents
    print(f"\n=== PHASE 5: FORMATTING ALL DOCUMENTS ===")
    os.system('cd /home/cliff/redact && python3 phase5_format.py')
    
    # Run Phase 6 cleanup and output
    print(f"\n=== PHASE 6: OUTPUT AND CLEANUP ===")
    os.system('cd /home/cliff/redact && python3 phase6_cleanup.py')
    
    # Summary
    print(f"\n=== BATCH PROCESSING COMPLETE ===")
    print(f"Successfully processed: {len(processed_files)} files")
    if failed_files:
        print(f"Failed: {len(failed_files)} files")
        print(f"Failed files: {', '.join(failed_files)}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 batch_process.py <folder_path>")
        print("Example: python3 batch_process.py /mnt/c/seedJura/contracts")
        return
    
    input_folder = sys.argv[1]
    batch_process_folder(input_folder)

if __name__ == "__main__":
    main()
