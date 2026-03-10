#!/usr/bin/env python3
import os
import json
import hashlib
import random
import string
from pathlib import Path

def generate_random_hash():
    """Generate a random hash ID"""
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    return hashlib.md5(random_string.encode()).hexdigest()[:12]

def chunk_file(input_file, output_dir, chunk_size=1000):
    """Break a file into chunks with random hash IDs"""
    
    # Read the file
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split into words
    words = content.split()
    
    # Get base filename without extension
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    
    # Create chunks with random hash IDs
    chunks_info = []
    chunk_files = []
    
    for i in range(0, len(words), chunk_size):
        chunk_content = ' '.join(words[i:i + chunk_size])
        chunk_hash = generate_random_hash()
        chunk_order = len(chunks_info) + 1
        
        # Save chunk with hash ID as filename
        chunk_filename = f"{chunk_hash}.txt"
        chunk_path = os.path.join(output_dir, chunk_filename)
        
        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write(chunk_content)
        
        # Store mapping information
        chunks_info.append({
            'hash_id': chunk_hash,
            'filename': chunk_filename,
            'order': chunk_order,
            'word_count': len(chunk_content.split()),
            'start_word': i + 1,
            'end_word': min(i + chunk_size, len(words))
        })
        
        chunk_files.append(chunk_path)
        print(f"Created chunk {chunk_order}: {chunk_hash}.txt ({len(chunk_content.split())} words)")
    
    # Create mapping file
    mapping = {
        'original_file': os.path.basename(input_file),
        'total_chunks': len(chunks_info),
        'total_words': len(words),
        'chunk_size': chunk_size,
        'chunks': chunks_info
    }
    
    mapping_filename = f"{base_name}_mapping.json"
    mapping_path = os.path.join(output_dir, mapping_filename)
    
    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2)
    
    print(f"Created mapping file: {mapping_filename}")
    
    return chunk_files, mapping_path

def reassemble_file(mapping_file, output_file):
    """Reassemble chunks back into original file using mapping"""
    
    # Load mapping
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    # Get directory containing chunks
    chunks_dir = os.path.dirname(mapping_file)
    
    # Sort chunks by order
    sorted_chunks = sorted(mapping['chunks'], key=lambda x: x['order'])
    
    # Reassemble content
    reassembled_content = []
    
    for chunk_info in sorted_chunks:
        chunk_path = os.path.join(chunks_dir, chunk_info['filename'])
        
        with open(chunk_path, 'r', encoding='utf-8') as f:
            chunk_content = f.read()
            reassembled_content.append(chunk_content)
    
    # Write reassembled file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(' '.join(reassembled_content))
    
    print(f"Reassembled file: {output_file}")
    return output_file

def main():
    # Input and output directories
    input_dir = '/mnt/c/seedJura/contracts/phase1'
    output_dir = '/mnt/c/seedJura/contracts/phase2'
    
    # Create phase2 directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Find redacted files
    input_path = Path(input_dir)
    redacted_files = list(input_path.glob('*_REDACTED.txt'))
    
    if not redacted_files:
        print("No redacted files found to chunk")
        return
    
    # Process each redacted file
    for file_path in redacted_files:
        print(f"\nChunking: {file_path.name}")
        chunk_files, mapping_file = chunk_file(str(file_path), output_dir, chunk_size=1000)
        print(f"Created {len(chunk_files)} chunks with mapping file")

if __name__ == "__main__":
    main()
