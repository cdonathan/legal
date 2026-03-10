#!/usr/bin/env python3
import os
import json
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

def redact_with_ollama(text, model="phi3.5", host="172.25.48.1"):
    """Redact text using any Ollama model"""
    
    prompt = f"""You are a document redaction specialist. Replace ALL personally identifiable information with [REDACT].

REDACT these types of information:
- Personal names (first, last, full names)
- Company names and business entities
- Addresses, street names, building names
- Phone numbers, fax numbers, email addresses
- Dollar amounts and financial figures
- Dates that could be identifying
- Geographic locations (cities, states, zip codes)
- Account numbers, ID numbers
- Any other identifying information

PRESERVE legal terminology, generic business terms, and document structure.

Text to redact:
{text}

Return ONLY the redacted text with sensitive information replaced by [REDACT]."""

    url = f"http://{host}:11434/api/generate"
    
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "top_p": 0.1
        }
    }
    
    try:
        response = requests.post(url, json=data, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            print(f"Ollama error: {response.status_code}")
            return text
            
    except Exception as e:
        print(f"Redaction error: {e}")
        return text

def process_single_chunk(chunk_file, input_dir, output_dir, model):
    """Process a single chunk with Ollama"""
    try:
        chunk_path = os.path.join(input_dir, chunk_file)
        
        with open(chunk_path, 'r', encoding='utf-8') as f:
            chunk_content = f.read()
        
        redacted_content = redact_with_ollama(chunk_content, model)
        
        output_file = os.path.join(output_dir, chunk_file)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(redacted_content)
        
        return chunk_file, True
        
    except Exception as e:
        print(f"Error processing {chunk_file}: {e}")
        return chunk_file, False

def main(model="phi3.5"):
    """Phase 3: AI-based redaction with Ollama"""
    print(f"=== PHASE 3: AI REDACTION WITH {model.upper()} ===")
    
    input_dir = '/mnt/c/seedJura/contracts/phase2'
    output_dir = '/mnt/c/seedJura/contracts/phase3'
    os.makedirs(output_dir, exist_ok=True)
    
    input_path = Path(input_dir)
    chunk_files = [f.name for f in input_path.glob('*.txt') if not f.name.endswith('_mapping.json')]
    
    if not chunk_files:
        print("No chunk files found in phase2")
        return False
    
    print(f"Processing {len(chunk_files)} chunks with {model}...")
    
    processed = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_chunk = {
            executor.submit(process_single_chunk, chunk_file, input_dir, output_dir, model): chunk_file 
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
    
    # Copy mapping files
    for mapping_file in input_path.glob('*_mapping.json'):
        output_mapping = os.path.join(output_dir, mapping_file.name)
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        mapping_data['phase3_processed'] = True
        mapping_data['ai_model'] = model
        
        with open(output_mapping, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, indent=2)
    
    print(f"\nPhase 3 complete: {processed} chunks processed, {failed} failed")
    return processed > 0

if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "phi3.5"
    main(model)
