#!/usr/bin/env python3
import os
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from phi35_redactor import redact_with_phi35

def process_single_chunk(chunk_file, input_dir, output_dir):
    """Process a single chunk with phi3.5"""
    try:
        chunk_path = os.path.join(input_dir, chunk_file)
        
        with open(chunk_path, 'r', encoding='utf-8') as f:
            chunk_content = f.read()
        
        # Redact using phi3.5
        redacted_content = redact_with_phi35(chunk_content)
        
        # Save redacted chunk
        output_file = os.path.join(output_dir, chunk_file)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(redacted_content)
        
        return chunk_file, True
        
    except Exception as e:
        print(f"Error processing {chunk_file}: {e}")
        return chunk_file, False

def main():
    """Phase 3: AI-based redaction with phi3.5"""
    print("=== PHASE 3: AI REDACTION WITH PHI3.5 ===")
    
    # Directories
    input_dir = '/mnt/c/seedJura/contracts/phase2'
    output_dir = '/mnt/c/seedJura/contracts/phase3'
    os.makedirs(output_dir, exist_ok=True)
    
    # Find chunk files (exclude mapping files)
    input_path = Path(input_dir)
    chunk_files = [f.name for f in input_path.glob('*.txt') if not f.name.endswith('_mapping.json')]
    
    if not chunk_files:
        print("No chunk files found in phase2")
        return False
    
    print(f"Processing {len(chunk_files)} chunks with phi3.5...")
    
    # Process chunks in parallel (reduced workers for local LLM)
    processed = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_chunk = {
            executor.submit(process_single_chunk, chunk_file, input_dir, output_dir): chunk_file 
            for chunk_file in chunk_files
        }
        
        for future in as_completed(future_to_chunk):
            filename, success = future.result()
            if success:
                processed += 1
                print(f"✓ Completed: {filename}")
            else:
                failed += 1
                print(f"✗ Failed: {filename}")
    
    # Copy mapping files to output directory
    for mapping_file in input_path.glob('*_mapping.json'):
        output_mapping = os.path.join(output_dir, mapping_file.name)
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        # Mark as processed by phi3.5
        mapping_data['phase3_processed'] = True
        mapping_data['ai_model'] = 'phi3.5'
        
        with open(output_mapping, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, indent=2)
    
    print(f"\nPhase 3 complete: {processed} chunks processed, {failed} failed")
    return processed > 0

if __name__ == "__main__":
    main()
