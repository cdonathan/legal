#!/usr/bin/env python3
import os
import json
import requests
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

def load_whitelist():
    """Load whitelist words"""
    whitelist = set()
    try:
        with open('redaction_whitelist.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    whitelist.add(line.lower())
    except FileNotFoundError:
        pass
    return whitelist

def extract_selective_content(text, whitelist):
    """Extract only high-risk sections for LLM processing"""
    words = text.split()
    
    # First 200 words
    opening = ' '.join(words[:200])
    
    # Last 100 words  
    closing = ' '.join(words[-100:]) if len(words) > 100 else ''
    
    # Find sentences with non-whitelisted words
    sentences = re.split(r'[.!?]+', text)
    flagged_sentences = []
    
    for sentence in sentences:
        sentence_words = re.findall(r'\b[A-Za-z]+\b', sentence)
        for word in sentence_words:
            if len(word) > 2 and word.lower() not in whitelist:
                if not re.match(r'\[.*\]', word):  # Skip already redacted
                    flagged_sentences.append(sentence.strip())
                    break
    
    # Combine sections
    selective_content = []
    if opening: selective_content.append(f"OPENING:\n{opening}")
    if closing: selective_content.append(f"CLOSING:\n{closing}")
    if flagged_sentences[:5]:  # Limit to 5 flagged sentences
        selective_content.append(f"FLAGGED:\n" + '\n'.join(flagged_sentences[:5]))
    
    return '\n\n'.join(selective_content)

def redact_with_ollama(text, model="phi3.5", host="172.25.48.1"):
    """Redact text using Ollama - verification mode"""
    
    prompt = f"""Review this pre-redacted contract text. Look for any missed PII that should be [REDACT]:

- Personal names not already redacted
- Company names not already redacted  
- Any identifying information missed

Text to review:
{text}

Return ONLY the text with any additional [REDACT] replacements needed."""

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
        response = requests.post(url, json=data, timeout=60)
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            return text
    except Exception as e:
        print(f"LLM error: {e}")
        return text

def process_single_chunk(chunk_file, input_dir, output_dir, model):
    """Process a small high-risk chunk"""
    try:
        chunk_path = os.path.join(input_dir, chunk_file)
        
        with open(chunk_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Simple verification prompt for small chunks
        prompt = f"""Review this contract text for missed PII. Replace any missed names, companies, or identifying info with [REDACT]:

{content}

Return the text with any additional [REDACT] needed:"""

        reviewed_content = redact_with_ollama_simple(content, prompt, model)
        
        output_file = os.path.join(output_dir, chunk_file)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(reviewed_content)
        
        return chunk_file, True
        
    except Exception as e:
        print(f"Error processing {chunk_file}: {e}")
        return chunk_file, False

def redact_with_ollama_simple(text, prompt, model="phi3.5", host="172.25.48.1"):
    """Simple Ollama call for small chunks"""
    url = f"http://{host}:11434/api/generate"
    
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0}
    }
    
    try:
        response = requests.post(url, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            return text
    except Exception:
        return text

def main(model="phi3.5"):
    """Phase 3: Selective AI verification"""
    print(f"=== PHASE 3: SELECTIVE AI VERIFICATION WITH {model.upper()} ===")
    
    whitelist = load_whitelist()
    print(f"Loaded {len(whitelist)} whitelisted words")
    
    input_dir = '/mnt/c/seedJura/contracts/phase2'
    output_dir = '/mnt/c/seedJura/contracts/phase3'
    os.makedirs(output_dir, exist_ok=True)
    
    input_path = Path(input_dir)
    chunk_files = [f.name for f in input_path.glob('page_*.txt')]  # Process page chunks
    
    if not chunk_files:
        print("No chunk files found in phase2")
        return False
    
    print(f"Processing {len(chunk_files)} chunks with selective content extraction...")
    
    processed = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=1) as executor:  # Single worker for local LLM
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
        mapping_data['processing_mode'] = 'selective'
        
        with open(output_mapping, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, indent=2)
    
    print(f"\nSelective processing complete: {processed} chunks processed, {failed} failed")
    return processed > 0

if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "phi3.5"
    print(f"=== PHASE 3: AI REDACTION ===")
    print(f"Model: {model}")
    result = main(model)
    print(f"Phase 3 result: {result}")
