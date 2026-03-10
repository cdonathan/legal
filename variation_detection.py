#!/usr/bin/env python3
import os
import sys
import time
import json
import re
from pathlib import Path
import requests

def find_flagged_words_from_summary(summary_file):
    """Extract flagged words from phase1 summary"""
    flagged_words = set()
    
    if os.path.exists(summary_file):
        with open(summary_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract words from "Non-whitelisted words:" lines
        for line in content.split('\n'):
            if 'Non-whitelisted words:' in line:
                words_part = line.split('Non-whitelisted words:')[1].strip()
                words = [w.strip() for w in words_part.split(',')]
                flagged_words.update(words)
    
    return list(flagged_words)

def call_ollama_for_variations(document_text, flagged_words, model="phi3.5", host="172.25.48.1"):
    """Use AI to find variations of flagged words"""
    
    if not flagged_words:
        return []
    
    # Create focused prompt
    flagged_list = ', '.join(flagged_words[:20])  # Limit to first 20 words
    
    prompt = f"""Find variations of these flagged entities in the text below:

FLAGGED ENTITIES: {flagged_list}

Look for:
- Possessive forms (Connor's, Tupperware's)
- With titles (Mr. Connor, Dr. Smith)  
- Different cases (TUPPERWARE, tupperware)
- Compound forms (Tupperware Corp, Connor Industries)
- Abbreviations (T. Smith, J. Connor)

Return ONLY the variations found, one per line. No explanations.

TEXT:
{document_text[:2000]}"""  # Limit text to 2000 chars for speed

    url = f"http://{host}:11434/api/generate"
    
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 200
        }
    }
    
    try:
        response = requests.post(url, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('response', '').strip()
            
            # Extract variations from response
            variations = []
            for line in ai_response.split('\n'):
                line = line.strip()
                if line and not line.startswith('I ') and len(line) < 50:
                    variations.append(line)
            
            return variations
        else:
            print(f"Ollama API error: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return []

def process_with_variation_detection():
    """Process documents using flagged word variation detection"""
    
    print("=== VARIATION DETECTION OPTIMIZATION ===")
    start_time = time.time()
    
    # Find all processed documents from phase1
    phase1_dir = Path('/mnt/c/seedJura/contracts/phase1')
    redacted_files = list(phase1_dir.glob('*_REDACTED.txt'))
    
    if not redacted_files:
        print("No phase1 files found. Run phases 1-2 first.")
        return
    
    print(f"Processing {len(redacted_files)} documents for variations")
    
    total_variations_found = 0
    total_processing_time = 0
    
    for i, redacted_file in enumerate(redacted_files, 1):
        print(f"\n--- Document {i}/{len(redacted_files)}: {redacted_file.name} ---")
        
        # Read the redacted document
        with open(redacted_file, 'r', encoding='utf-8') as f:
            document_text = f.read()
        
        # Find corresponding summary file to get flagged words
        base_name = redacted_file.stem.replace('_REDACTED', '')
        summary_file = phase1_dir / f"{base_name}_SUMMARY.txt"
        
        # Extract flagged words from summary
        flagged_words = find_flagged_words_from_summary(summary_file)
        
        if not flagged_words:
            print(f"  No flagged words found")
            continue
        
        print(f"  Original flagged words: {len(flagged_words)}")
        print(f"  Sample: {', '.join(flagged_words[:5])}...")
        
        # Use AI to find variations
        print(f"  Searching for variations with AI...")
        ai_start = time.time()
        variations = call_ollama_for_variations(document_text, flagged_words)
        ai_time = time.time() - ai_start
        
        print(f"  AI processing time: {ai_time:.1f}s")
        
        if variations:
            print(f"  Variations found: {len(variations)}")
            print(f"  Examples: {', '.join(variations[:3])}...")
            
            # Apply additional redactions for variations
            updated_text = document_text
            redactions_made = 0
            
            for variation in variations:
                if len(variation) > 2 and variation not in flagged_words:
                    # Redact the variation
                    pattern = re.escape(variation)
                    matches = re.findall(rf'\b{pattern}\b', updated_text, re.IGNORECASE)
                    if matches:
                        updated_text = re.sub(rf'\b{pattern}\b', '[REDACT]', updated_text, flags=re.IGNORECASE)
                        redactions_made += len(matches)
            
            if redactions_made > 0:
                # Save updated document
                output_file = phase1_dir / f"{base_name}_VARIATION_REDACTED.txt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(updated_text)
                
                print(f"  ✓ Applied {redactions_made} additional redactions")
                print(f"  ✓ Saved: {output_file.name}")
            else:
                print(f"  No additional redactions needed")
        else:
            print(f"  No variations found")
        
        total_variations_found += len(variations) if variations else 0
        total_processing_time += ai_time
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n=== VARIATION DETECTION RESULTS ===")
    print(f"Documents processed: {len(redacted_files)}")
    print(f"Total variations found: {total_variations_found}")
    print(f"Total AI processing time: {total_processing_time:.2f}s")
    print(f"Total time: {total_time:.2f}s ({total_time/60:.2f}m)")
    print(f"Average AI time per document: {total_processing_time/len(redacted_files):.1f}s")
    
    # Save results
    results = {
        'approach': 'variation_detection',
        'documents_processed': len(redacted_files),
        'total_variations_found': total_variations_found,
        'total_ai_time': total_processing_time,
        'total_time': total_time,
        'avg_ai_time_per_doc': total_processing_time/len(redacted_files) if redacted_files else 0
    }
    
    with open('/mnt/c/seedJura/variation_detection_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: C:\\seedJura\\variation_detection_results.json")
    
    return results

if __name__ == "__main__":
    process_with_variation_detection()
