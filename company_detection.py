#!/usr/bin/env python3
import os
import sys
import time
import json
import re
from pathlib import Path
import requests

def call_ollama_for_company_detection(document_text, model="phi3.5", host="172.25.48.1"):
    """Use AI to find company names with whitelisted suffixes"""
    
    # Load company suffixes
    company_suffixes = []
    with open('/home/cliff/redact/company_suffixes.txt', 'r') as f:
        company_suffixes = [line.strip() for line in f if line.strip()]
    
    # Create focused prompt
    suffixes_list = ', '.join(company_suffixes)
    
    prompt = f"""Find company names in the text that end with these business terms:

BUSINESS TERMS: {suffixes_list}

Look for patterns like:
- [Name] + [Business Term] (e.g., "Smith Industries", "Connor LLC")
- [Name] + [Name] + [Business Term] (e.g., "Smith Johnson Corp")

Return ONLY the complete company names found, one per line. No explanations.

TEXT:
{document_text[:3000]}"""  # Limit to 3000 chars for speed

    url = f"http://{host}:11434/api/generate"
    
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 300
        }
    }
    
    try:
        response = requests.post(url, json=data, timeout=45)
        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('response', '').strip()
            
            # Extract company names from response
            company_names = []
            for line in ai_response.split('\n'):
                line = line.strip()
                # Filter out explanatory text and keep only potential company names
                if line and not line.startswith(('I ', 'The ', 'Here ', 'Based ', 'Looking ')):
                    # Remove common prefixes
                    line = re.sub(r'^[-•*]\s*', '', line)
                    if len(line) > 3 and len(line) < 100:
                        company_names.append(line)
            
            return company_names
        else:
            print(f"Ollama API error: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return []

def apply_company_redactions(document_text, company_names):
    """Apply redactions for found company names"""
    
    redacted_text = document_text
    redactions_made = 0
    
    for company_name in company_names:
        if len(company_name) > 3:
            # Create pattern to match the company name
            pattern = re.escape(company_name)
            matches = re.findall(rf'\\b{pattern}\\b', redacted_text, re.IGNORECASE)
            
            if matches:
                redacted_text = re.sub(rf'\\b{pattern}\\b', '[REDACT]', redacted_text, flags=re.IGNORECASE)
                redactions_made += len(matches)
                print(f"    Redacted: {company_name} ({len(matches)} occurrences)")
    
    return redacted_text, redactions_made

def process_with_company_detection():
    """Process documents using AI company name detection"""
    
    print("=== COMPANY NAME DETECTION OPTIMIZATION ===")
    start_time = time.time()
    
    # Find all processed documents from phase1
    phase1_dir = Path('/mnt/c/seedJura/contracts/phase1')
    redacted_files = list(phase1_dir.glob('*_REDACTED.txt'))
    
    if not redacted_files:
        print("No phase1 files found. Run phases 1-2 first.")
        return
    
    print(f"Processing {len(redacted_files)} documents for company names")
    
    total_companies_found = 0
    total_redactions_made = 0
    total_ai_time = 0
    
    for i, redacted_file in enumerate(redacted_files, 1):
        print(f"\\n--- Document {i}/{len(redacted_files)}: {redacted_file.name} ---")
        
        # Read the document
        with open(redacted_file, 'r', encoding='utf-8') as f:
            document_text = f.read()
        
        # Use AI to find company names
        print(f"  Searching for company names with AI...")
        ai_start = time.time()
        company_names = call_ollama_for_company_detection(document_text)
        ai_time = time.time() - ai_start
        total_ai_time += ai_time
        
        print(f"  AI processing time: {ai_time:.1f}s")
        
        if company_names:
            print(f"  Company names found: {len(company_names)}")
            for name in company_names[:5]:  # Show first 5
                print(f"    - {name}")
            if len(company_names) > 5:
                print(f"    ... and {len(company_names) - 5} more")
            
            # Apply redactions
            print(f"  Applying redactions...")
            updated_text, redactions_made = apply_company_redactions(document_text, company_names)
            
            if redactions_made > 0:
                # Save updated document
                base_name = redacted_file.stem.replace('_REDACTED', '')
                output_file = phase1_dir / f"{base_name}_COMPANY_REDACTED.txt"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(updated_text)
                
                print(f"  ✓ Applied {redactions_made} company name redactions")
                print(f"  ✓ Saved: {output_file.name}")
                
                total_redactions_made += redactions_made
            else:
                print(f"  No additional redactions needed")
        else:
            print(f"  No company names found")
        
        total_companies_found += len(company_names) if company_names else 0
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\\n=== COMPANY DETECTION RESULTS ===")
    print(f"Documents processed: {len(redacted_files)}")
    print(f"Total company names found: {total_companies_found}")
    print(f"Total redactions applied: {total_redactions_made}")
    print(f"Total AI processing time: {total_ai_time:.2f}s")
    print(f"Total time: {total_time:.2f}s ({total_time/60:.2f}m)")
    print(f"Average AI time per document: {total_ai_time/len(redacted_files):.1f}s")
    
    # Save results
    results = {
        'approach': 'company_detection',
        'documents_processed': len(redacted_files),
        'total_companies_found': total_companies_found,
        'total_redactions_made': total_redactions_made,
        'total_ai_time': total_ai_time,
        'total_time': total_time,
        'avg_ai_time_per_doc': total_ai_time/len(redacted_files) if redacted_files else 0
    }
    
    with open('/mnt/c/seedJura/company_detection_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\\nResults saved to: C:\\\\seedJura\\\\company_detection_results.json")
    
    return results

if __name__ == "__main__":
    process_with_company_detection()
