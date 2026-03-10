#!/usr/bin/env python3
import os
import json
import time
from pathlib import Path
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

def load_api_key():
    """Load OpenAI API key from file"""
    try:
        with open('openai_api_key.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("Error: openai_api_key.txt file not found")
        return None

def load_prompt():
    """Load the OpenAI prompt from file"""
    with open('openai_prompt.txt', 'r', encoding='utf-8') as f:
        return f.read().strip()

def process_single_chunk(chunk_file, prompt, api_key, output_dir):
    """Process a single chunk with OpenAI GPT-4o-mini"""
    try:
        client = OpenAI(api_key=api_key)
        
        # Read chunk content
        with open(chunk_file, 'r', encoding='utf-8') as f:
            chunk_content = f.read()
        
        # Process with OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": chunk_content}
            ],
            temperature=0,
            max_tokens=4000
        )
        
        redacted_content = response.choices[0].message.content.strip()
        
        # Save to phase3 with same filename
        output_file = os.path.join(output_dir, chunk_file.name)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(redacted_content)
        
        return chunk_file.name, True, None
        
    except Exception as e:
        print(f"Error processing {chunk_file.name}: {e}")
        return chunk_file.name, False, str(e)

def process_chunks():
    """Process all chunks in phase2 with OpenAI in parallel and save to phase3"""
    
    # Load API key
    api_key = load_api_key()
    if not api_key:
        return
    
    # Load prompt
    prompt = load_prompt()
    
    # Directories
    input_dir = '/mnt/c/seedJura/contracts/phase2'
    output_dir = '/mnt/c/seedJura/contracts/phase3'
    
    # Create phase3 directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all chunk files (exclude mapping files)
    input_path = Path(input_dir)
    chunk_files = [f for f in input_path.glob('*.txt') if not f.name.endswith('_mapping.json')]
    mapping_files = list(input_path.glob('*_mapping.json'))
    
    if not chunk_files:
        print("No chunk files found in phase2")
        return
    
    print(f"Found {len(chunk_files)} chunks to process in parallel")
    
    # Process chunks in parallel
    processed_chunks = []
    failed_chunks = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all chunks for processing
        future_to_chunk = {
            executor.submit(process_single_chunk, chunk_file, prompt, api_key, output_dir): chunk_file 
            for chunk_file in chunk_files
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_chunk):
            chunk_file = future_to_chunk[future]
            try:
                filename, success, error = future.result()
                if success:
                    processed_chunks.append(filename)
                    print(f"✓ Completed: {filename}")
                else:
                    failed_chunks.append((filename, error))
                    print(f"✗ Failed: {filename}")
            except Exception as e:
                failed_chunks.append((chunk_file.name, str(e)))
                print(f"✗ Exception: {chunk_file.name} - {e}")
    
    # Copy mapping files to phase3
    for mapping_file in mapping_files:
        output_mapping = os.path.join(output_dir, mapping_file.name)
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        # Update mapping to reflect phase3 processing
        mapping_data['phase3_processed'] = True
        mapping_data['processed_chunks'] = len(processed_chunks)
        mapping_data['failed_chunks'] = len(failed_chunks)
        
        with open(output_mapping, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, indent=2)
    
    print(f"\nPhase 3 complete!")
    print(f"Successfully processed: {len(processed_chunks)} chunks")
    if failed_chunks:
        print(f"Failed: {len(failed_chunks)} chunks")
    print(f"Results saved to: {output_dir}")

def main():
    process_chunks()

if __name__ == "__main__":
    main()
