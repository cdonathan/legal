#!/usr/bin/env python3
import os
import sys
import time
import json
import re
from pathlib import Path

def learn_then_apply_pipeline(contracts_folder):
    """Learn-then-apply batch processing"""
    
    print("=== LEARN-THEN-APPLY PIPELINE ===")
    start_time = time.time()
    
    # Clear previous results
    os.system('rm -f /mnt/c/seedJura/contracts/phase2/*.txt /mnt/c/seedJura/contracts/phase2/*.json')
    os.system('rm -f /mnt/c/seedJura/contracts/phase3/*.txt /mnt/c/seedJura/contracts/phase3/*.json')
    os.system('rm -f /mnt/c/seedJura/contracts/phase4/*.txt')
    
    # Load whitelist
    whitelist = set()
    with open('/home/cliff/redact/redaction_whitelist.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                whitelist.add(line.lower())
    
    # Find all contracts
    contracts_dir = Path(contracts_folder)
    contract_files = list(contracts_dir.glob('*.mhtml'))
    contract_files = [f for f in contract_files if not any(suffix in f.name for suffix in ['_REDACTED', '_FORMATTED'])]
    
    print(f"Processing {len(contract_files)} contracts with learn-then-apply optimization")
    
    # Global learned PII
    global_learned_pii = set()
    total_ai_pages = 0
    total_pattern_pages = 0
    
    # Process each contract
    for i, contract_file in enumerate(contract_files, 1):
        print(f"\n--- Contract {i}/{len(contract_files)}: {contract_file.name} ---")
        
        # Run phases 1-2
        result = os.system(f'cd /home/cliff/redact && python3 page_pipeline.py "{contract_file}" > /dev/null 2>&1')
        if result != 0:
            print(f"Failed phases 1-2 for {contract_file.name}")
            continue
        
        # Find mapping file
        mapping_files = list(Path('/mnt/c/seedJura/contracts/phase3').glob(f'{contract_file.stem}_*_mapping.json'))
        if not mapping_files:
            print(f"No flagged pages for {contract_file.name}")
            continue
        
        with open(mapping_files[0], 'r') as f:
            mapping = json.load(f)
        
        # Analyze chunks for new vs known PII
        ai_chunks = []
        pattern_chunks = []
        new_pii_found = set()
        
        phase2_dir = Path('/mnt/c/seedJura/contracts/phase2')
        
        for chunk_info in mapping['chunks']:
            chunk_file = phase2_dir / chunk_info['file']
            
            if chunk_file.exists():
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find non-whitelisted words
                words = re.findall(r'\\b[A-Za-z]+\\b', content)
                has_new_pii = False
                
                for word in words:
                    if len(word) > 2 and word.lower() not in whitelist:
                        if word.lower() not in global_learned_pii:
                            has_new_pii = True
                            new_pii_found.add(word.lower())
                
                if has_new_pii:
                    ai_chunks.append(chunk_info)
                else:
                    pattern_chunks.append(chunk_info)
        
        print(f"  AI needed: {len(ai_chunks)} pages")
        print(f"  Pattern match: {len(pattern_chunks)} pages")
        print(f"  New PII terms: {len(new_pii_found)}")
        
        # Update global learned PII
        global_learned_pii.update(new_pii_found)
        
        # Process AI chunks if any
        if ai_chunks:
            # Clear phase2 and copy only AI chunks
            os.system('rm -f /mnt/c/seedJura/contracts/phase2/*.txt')
            
            for chunk_info in ai_chunks:
                src_file = phase2_dir / chunk_info['file']
                if src_file.exists():
                    os.system(f'cp "{src_file}" /mnt/c/seedJura/contracts/phase2/')
            
            # Create temp mapping for AI chunks only
            temp_mapping = {
                'original_file': mapping['original_file'],
                'redacted_file': mapping['redacted_file'],
                'total_chunks': len(ai_chunks),
                'chunks': ai_chunks,
                'processing_mode': 'learn_then_apply'
            }
            
            temp_mapping_file = Path('/mnt/c/seedJura/contracts/phase3') / f'{contract_file.stem}_temp_mapping.json'
            with open(temp_mapping_file, 'w') as f:
                json.dump(temp_mapping, f, indent=2)
            
            # Process with AI
            print(f"  Processing {len(ai_chunks)} pages with AI...")
            ai_result = os.system('cd /home/cliff/redact && python3 phase3_selective.py phi3.5 > /dev/null 2>&1')
            
            if ai_result == 0:
                print(f"  ✓ AI processing completed")
            else:
                print(f"  ✗ AI processing failed")
        
        # Simulate pattern matching for known PII chunks
        if pattern_chunks:
            print(f"  Pattern matching {len(pattern_chunks)} pages...")
            
            # Create mock processed files for pattern chunks
            for chunk_info in pattern_chunks:
                output_file = Path('/mnt/c/seedJura/contracts/phase3') / chunk_info['file']
                
                # Read original chunk and apply known pattern replacements
                src_file = phase2_dir / chunk_info['file']
                if src_file.exists():
                    with open(src_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Apply pattern replacements for known PII
                    for pii_term in global_learned_pii:
                        if len(pii_term) > 2:
                            # Replace case-insensitive
                            content = re.sub(rf'\\b{re.escape(pii_term)}\\b', '[REDACT]', content, flags=re.IGNORECASE)
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(content)
            
            print(f"  ✓ Pattern matching completed")
        
        total_ai_pages += len(ai_chunks)
        total_pattern_pages += len(pattern_chunks)
    
    # Run phases 4-5 on all processed documents
    print(f"\\n=== PHASE 4: REASSEMBLING DOCUMENTS ===")
    os.system('cd /home/cliff/redact && python3 phase4_reassemble.py > /dev/null 2>&1')
    
    print(f"=== PHASE 5: FORMATTING DOCUMENTS ===")
    os.system('cd /home/cliff/redact && python3 phase5_format_new.py > /dev/null 2>&1')
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\\n=== LEARN-THEN-APPLY RESULTS ===")
    print(f"Contracts processed: {len(contract_files)}")
    print(f"Pages sent to AI: {total_ai_pages}")
    print(f"Pages pattern matched: {total_pattern_pages}")
    print(f"Total pages processed: {total_ai_pages + total_pattern_pages}")
    print(f"Unique PII terms learned: {len(global_learned_pii)}")
    print(f"Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    
    # Calculate efficiency
    if total_ai_pages + total_pattern_pages > 0:
        ai_percentage = (total_ai_pages / (total_ai_pages + total_pattern_pages)) * 100
        print(f"AI processing: {ai_percentage:.1f}% of pages")
        print(f"Pattern matching: {100-ai_percentage:.1f}% of pages")
    
    # Save results
    results = {
        'approach': 'learn_then_apply',
        'contracts_processed': len(contract_files),
        'total_pages': total_ai_pages + total_pattern_pages,
        'ai_pages': total_ai_pages,
        'pattern_pages': total_pattern_pages,
        'total_time': total_time,
        'learned_pii_count': len(global_learned_pii),
        'learned_pii': sorted(list(global_learned_pii))
    }
    
    with open('/mnt/c/seedJura/learn_then_apply_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\\nResults saved to: C:\\\\seedJura\\\\learn_then_apply_results.json")
    
    # Show some learned PII examples
    if global_learned_pii:
        pii_list = sorted(list(global_learned_pii))
        print(f"\\nSample learned PII terms:")
        print(f"  {', '.join(pii_list[:20])}...")
    
    return results

if __name__ == "__main__":
    contracts_folder = "/mnt/c/seedJura/contracts"
    learn_then_apply_pipeline(contracts_folder)
