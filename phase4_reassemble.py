#!/usr/bin/env python3
import os
import json
from pathlib import Path

def reassemble_file(mapping_file, chunks_dir, output_dir):
    """Reassemble chunks back into original file format using mapping"""
    
    # Load mapping
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    # Sort chunks by page number instead of order
    sorted_chunks = sorted(mapping['chunks'], key=lambda x: x['page_num'])
    
    # Reassemble content
    reassembled_content = []
    
    print(f"Reassembling {len(sorted_chunks)} chunks...")
    
    for chunk_info in sorted_chunks:
        chunk_path = os.path.join(chunks_dir, chunk_info['file'])
        
        if not os.path.exists(chunk_path):
            print(f"Warning: Chunk file not found: {chunk_info['file']}")
            continue
            
        with open(chunk_path, 'r', encoding='utf-8') as f:
            chunk_content = f.read()
            reassembled_content.append(chunk_content)
        
        print(f"✓ Added chunk page {chunk_info['page_num']}: {chunk_info['file']}")
    
    # Join chunks with single space (they were split by words)
    full_content = ' '.join(reassembled_content)
    
    # Create output filename
    original_name = mapping['original_file']
    base_name = os.path.splitext(original_name)[0]
    output_filename = f"{base_name}_REDACTED.txt"
    output_path = os.path.join(output_dir, output_filename)
    
    # Write reassembled file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    print(f"Reassembled file saved: {output_filename}")
    return output_path

def process_all_mappings():
    """Process all mapping files in phase3 and reassemble to phase4"""
    
    # Directories
    input_dir = '/mnt/c/seedJura/contracts/phase3'
    output_dir = '/mnt/c/seedJura/contracts/phase4'
    
    # Create phase4 directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Find mapping files
    input_path = Path(input_dir)
    mapping_files = list(input_path.glob('*_mapping.json'))
    
    if not mapping_files:
        print("No mapping files found in phase3")
        return
    
    print(f"Found {len(mapping_files)} mapping files to process")
    
    # Process each mapping file
    reassembled_files = []
    
    for mapping_file in mapping_files:
        print(f"\nProcessing: {mapping_file.name}")
        
        try:
            output_file = reassemble_file(str(mapping_file), input_dir, output_dir)
            reassembled_files.append(output_file)
            
        except Exception as e:
            print(f"Error processing {mapping_file.name}: {e}")
    
    print(f"\nPhase 4 complete!")
    print(f"Reassembled {len(reassembled_files)} files")
    print(f"Results saved to: {output_dir}")
    
    return reassembled_files

def main():
    process_all_mappings()

if __name__ == "__main__":
    main()
