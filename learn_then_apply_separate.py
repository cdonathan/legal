#!/usr/bin/env python3
import os
import sys
import time
import json
import re
from pathlib import Path

def learn_then_apply_pipeline(contracts_folder):
    """Learn-then-apply batch processing using separate directories"""
    
    print("=== LEARN-THEN-APPLY PIPELINE ===")
    start_time = time.time()
    
    # Use separate directories for learn-then-apply approach
    base_dir = "/mnt/c/seedJura/contracts_learn"
    phase1_dir = f"{base_dir}/phase1"
    phase2_dir = f"{base_dir}/phase2" 
    phase3_dir = f"{base_dir}/phase3"
    phase4_dir = f"{base_dir}/phase4"
    phase5_dir = f"{base_dir}/phase5"
    
    # Create directories
    for dir_path in [phase1_dir, phase2_dir, phase3_dir, phase4_dir, phase5_dir]:
        os.makedirs(dir_path, exist_ok=True)
    
    # Clear previous results
    os.system(f'rm -f {phase2_dir}/*.txt {phase2_dir}/*.json')
    os.system(f'rm -f {phase3_dir}/*.txt {phase3_dir}/*.json')
    os.system(f'rm -f {phase4_dir}/*.txt')
    
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
        
        # Create temporary script to run page pipeline with custom directories
        temp_script = f"""#!/usr/bin/env python3
import os
import sys
sys.path.append('/home/cliff/redact')
from page_redactor import PageRedactor

def main():
    redactor = PageRedactor()
    redactor.phase1_dir = "{phase1_dir}"
    redactor.phase2_dir = "{phase2_dir}"
    redactor.phase3_dir = "{phase3_dir}"
    redactor.process_document("{contract_file}")

if __name__ == "__main__":
    main()
"""
        
        with open('/tmp/temp_page_pipeline.py', 'w') as f:
            f.write(temp_script)
        
        # Run phases 1-2 with custom directories
        result = os.system('cd /home/cliff/redact && python3 /tmp/temp_page_pipeline.py > /dev/null 2>&1')
        if result != 0:
            # Fallback: run original pipeline and copy results
            result = os.system(f'cd /home/cliff/redact && python3 page_pipeline.py "{contract_file}" > /dev/null 2>&1')
            if result == 0:
                # Copy results to learn directories
                os.system(f'cp /mnt/c/seedJura/contracts/phase1/{contract_file.stem}_REDACTED.txt {phase1_dir}/ 2>/dev/null')
                os.system(f'cp /mnt/c/seedJura/contracts/phase2/*.txt {phase2_dir}/ 2>/dev/null')
                os.system(f'cp /mnt/c/seedJura/contracts/phase3/*_mapping.json {phase3_dir}/ 2>/dev/null')
        
        # Find mapping file
        mapping_files = list(Path(phase3_dir).glob(f'{contract_file.stem}_*_mapping.json'))
        if not mapping_files:
            print(f"  No flagged pages")
            continue
        
        with open(mapping_files[0], 'r') as f:
            mapping = json.load(f)
        
        # Analyze chunks for new vs known PII
        ai_chunks = []
        pattern_chunks = []
        new_pii_found = set()
        
        for chunk_info in mapping['chunks']:
            chunk_file_path = Path(phase2_dir) / chunk_info['file']
            
            if chunk_file_path.exists():
                with open(chunk_file_path, 'r', encoding='utf-8') as f:
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
            os.system(f'rm -f {phase2_dir}/*.txt')
            
            for chunk_info in ai_chunks:
                src_file = Path(phase2_dir) / chunk_info['file']
                if src_file.exists():
                    os.system(f'cp "{src_file}" {phase2_dir}/')
            
            # Create temp mapping for AI chunks only
            temp_mapping = {
                'original_file': mapping['original_file'],
                'redacted_file': mapping['redacted_file'], 
                'total_chunks': len(ai_chunks),
                'chunks': ai_chunks,
                'processing_mode': 'learn_then_apply'
            }
            
            temp_mapping_file = Path(phase3_dir) / f'{contract_file.stem}_temp_mapping.json'
            with open(temp_mapping_file, 'w') as f:
                json.dump(temp_mapping, f, indent=2)
            
            # Create temporary phase3 script with custom directories
            temp_phase3_script = f"""#!/usr/bin/env python3
import os
import sys
sys.path.append('/home/cliff/redact')

# Override directories
os.environ['PHASE2_DIR'] = '{phase2_dir}'
os.environ['PHASE3_DIR'] = '{phase3_dir}'

# Run phase3 with custom directories
os.system('cd /home/cliff/redact && python3 phase3_selective.py phi3.5')
"""
            
            with open('/tmp/temp_phase3.py', 'w') as f:
                f.write(temp_phase3_script)
            
            print(f"  Processing {len(ai_chunks)} pages with AI...")
            ai_start = time.time()
            ai_result = os.system('python3 /tmp/temp_phase3.py > /dev/null 2>&1')
            ai_time = time.time() - ai_start
            
            if ai_result == 0:
                print(f"  ✓ AI processing completed ({ai_time:.1f}s)")
            else:
                print(f"  ✗ AI processing failed")
        
        # Pattern matching for known PII chunks
        if pattern_chunks:
            print(f"  Pattern matching {len(pattern_chunks)} pages...")
            
            # Apply pattern replacements for known PII
            for chunk_info in pattern_chunks:
                src_file = Path(phase2_dir) / chunk_info['file']
                output_file = Path(phase3_dir) / chunk_info['file']
                
                if src_file.exists():
                    with open(src_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Apply pattern replacements for known PII
                    for pii_term in global_learned_pii:
                        if len(pii_term) > 2:
                            content = re.sub(rf'\\b{re.escape(pii_term)}\\b', '[REDACT]', content, flags=re.IGNORECASE)
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(content)
            
            print(f"  ✓ Pattern matching completed")
        
        total_ai_pages += len(ai_chunks)
        total_pattern_pages += len(pattern_chunks)
    
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
        'learned_pii': sorted(list(global_learned_pii))[:50]  # First 50 terms
    }
    
    with open('/mnt/c/seedJura/learn_then_apply_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\\nResults saved to: C:\\\\seedJura\\\\learn_then_apply_results.json")
    
    # Show learned PII examples
    if global_learned_pii:
        pii_list = sorted(list(global_learned_pii))
        print(f"\\nSample learned PII terms:")
        print(f"  {', '.join(pii_list[:15])}...")
    
    return results

if __name__ == "__main__":
    contracts_folder = "/mnt/c/seedJura/contracts"
    learn_then_apply_pipeline(contracts_folder)
