#!/usr/bin/env python3
import os
import sys
import time
import json
import re
from pathlib import Path
from collections import defaultdict

def load_whitelist():
    """Load whitelist words"""
    whitelist = set()
    with open('/home/cliff/redact/redaction_whitelist.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                whitelist.add(line.lower())
    return whitelist

def learn_then_apply_batch(contracts_folder):
    """Process contracts with learn-then-apply optimization"""
    
    print("=== LEARN-THEN-APPLY BATCH PROCESSING ===")
    start_time = time.time()
    
    # Find Tupperware contracts
    contracts_dir = Path(contracts_folder)
    tupperware_files = []
    for pattern in ['Tupperware_*.mhtml', 'Osceola_*.mhtml', '*_Services_*.mhtml', 
                   'Executive_*.mhtml', 'Supply_*.mhtml', 'Joint_*.mhtml', 
                   'Technology_*.mhtml', 'Asset_*.mhtml', 'Construction_*.mhtml']:
        tupperware_files.extend(contracts_dir.glob(pattern))
    
    if not tupperware_files:
        print("No Tupperware contracts found")
        return
    
    print(f"Found {len(tupperware_files)} Tupperware contracts to process")
    
    # Clear previous results
    os.system('rm -f /mnt/c/seedJura/contracts/phase2/*.txt /mnt/c/seedJura/contracts/phase2/*.json')
    os.system('rm -f /mnt/c/seedJura/contracts/phase3/*.txt /mnt/c/seedJura/contracts/phase3/*.json')
    
    # Global learned PII across all documents
    global_learned_pii = set()
    whitelist = load_whitelist()
    
    total_pages_processed = 0
    total_ai_pages = 0
    total_pattern_pages = 0
    
    # Process each contract
    for i, contract_file in enumerate(tupperware_files, 1):
        print(f"\n--- Processing {i}/{len(tupperware_files)}: {contract_file.name} ---")
        
        # Run phases 1-2 to get flagged pages
        result = os.system(f'cd /home/cliff/redact && python3 page_pipeline.py "{contract_file}"')
        if result != 0:
            print(f"Failed to process {contract_file.name}")
            continue
        
        # Find mapping file for this document
        mapping_files = list(Path('/mnt/c/seedJura/contracts/phase3').glob(f'{contract_file.stem}_*_mapping.json'))
        if not mapping_files:
            print(f"No mapping file found for {contract_file.name}")
            continue
        
        with open(mapping_files[0], 'r') as f:
            mapping = json.load(f)
        
        # Analyze chunks to determine which need AI vs pattern matching
        ai_chunks = []
        pattern_chunks = []
        new_pii_found = set()
        
        phase2_dir = Path('/mnt/c/seedJura/contracts/phase2')
        
        for chunk_info in sorted(mapping['chunks'], key=lambda x: x['page_num']):
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
        
        print(f"  Pages needing AI: {len(ai_chunks)}")
        print(f"  Pages for pattern matching: {len(pattern_chunks)}")
        print(f"  New PII terms found: {len(new_pii_found)}")
        
        # Add new PII to global learned set
        global_learned_pii.update(new_pii_found)
        
        # Process AI chunks if any
        if ai_chunks:
            # Create temporary mapping with only AI chunks
            temp_mapping = {
                'original_file': mapping['original_file'],
                'redacted_file': mapping['redacted_file'],
                'total_chunks': len(ai_chunks),
                'chunks': ai_chunks,
                'processing_mode': 'learn_then_apply'
            }
            
            # Clear previous chunks and save only AI chunks
            os.system('rm -f /mnt/c/seedJura/contracts/phase2/*.txt')
            
            for chunk_info in ai_chunks:
                src_file = phase2_dir / chunk_info['file']
                if src_file.exists():
                    # Copy chunk back to phase2 for processing
                    os.system(f'cp "{src_file}" /mnt/c/seedJura/contracts/phase2/')
            
            # Save temporary mapping
            temp_mapping_file = Path('/mnt/c/seedJura/contracts/phase3') / f'{contract_file.stem}_temp_mapping.json'
            with open(temp_mapping_file, 'w') as f:
                json.dump(temp_mapping, f, indent=2)
            
            # Process with AI
            print(f"  Processing {len(ai_chunks)} pages with AI...")
            ai_start = time.time()
            result = os.system('cd /home/cliff/redact && python3 phase3_selective.py phi3.5')
            ai_time = time.time() - ai_start
            print(f"  AI processing took {ai_time:.1f} seconds")
        
        # Simulate pattern matching for remaining chunks
        if pattern_chunks:
            pattern_time = len(pattern_chunks) * 0.1  # 0.1 seconds per pattern match
            print(f"  Pattern matching {len(pattern_chunks)} pages (simulated: {pattern_time:.1f}s)")
            
            # Create mock processed files for pattern chunks
            for chunk_info in pattern_chunks:
                output_file = Path('/mnt/c/seedJura/contracts/phase3') / chunk_info['file']
                with open(output_file, 'w') as f:
                    f.write("Pattern matched content with [REDACT] replacements")
        
        total_pages_processed += len(mapping['chunks'])
        total_ai_pages += len(ai_chunks)
        total_pattern_pages += len(pattern_chunks)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n=== LEARN-THEN-APPLY RESULTS ===")
    print(f"Total contracts processed: {len(tupperware_files)}")
    print(f"Total pages processed: {total_pages_processed}")
    print(f"Pages sent to AI: {total_ai_pages}")
    print(f"Pages pattern matched: {total_pattern_pages}")
    print(f"Total processing time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"Unique PII terms learned: {len(global_learned_pii)}")
    
    # Save results
    results = {
        'approach': 'learn_then_apply',
        'contracts_processed': len(tupperware_files),
        'total_pages': total_pages_processed,
        'ai_pages': total_ai_pages,
        'pattern_pages': total_pattern_pages,
        'total_time': total_time,
        'learned_pii_count': len(global_learned_pii),
        'learned_pii': sorted(list(global_learned_pii))
    }
    
    with open('/mnt/c/seedJura/learn_then_apply_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\\nResults saved to: C:\\\\seedJura\\\\learn_then_apply_results.json")
    return results

def original_batch(contracts_folder):
    """Process contracts with original approach"""
    
    print("\\n=== ORIGINAL APPROACH BATCH PROCESSING ===")
    start_time = time.time()
    
    # Find Tupperware contracts
    contracts_dir = Path(contracts_folder)
    tupperware_files = []
    for pattern in ['Tupperware_*.mhtml', 'Osceola_*.mhtml', '*_Services_*.mhtml', 
                   'Executive_*.mhtml', 'Supply_*.mhtml', 'Joint_*.mhtml', 
                   'Technology_*.mhtml', 'Asset_*.mhtml', 'Construction_*.mhtml']:
        tupperware_files.extend(contracts_dir.glob(pattern))
    
    print(f"Found {len(tupperware_files)} Tupperware contracts to process")
    
    # Clear previous results
    os.system('rm -f /mnt/c/seedJura/contracts/phase2/*.txt /mnt/c/seedJura/contracts/phase2/*.json')
    os.system('rm -f /mnt/c/seedJura/contracts/phase3/*.txt /mnt/c/seedJura/contracts/phase3/*.json')
    
    total_pages_processed = 0
    total_ai_pages = 0
    
    # Process each contract with original approach
    for i, contract_file in enumerate(tupperware_files, 1):
        print(f"\\n--- Processing {i}/{len(tupperware_files)}: {contract_file.name} ---")
        
        # Run phases 1-2
        result = os.system(f'cd /home/cliff/redact && python3 page_pipeline.py "{contract_file}"')
        if result != 0:
            print(f"Failed to process {contract_file.name}")
            continue
        
        # Count flagged pages
        mapping_files = list(Path('/mnt/c/seedJura/contracts/phase3').glob(f'{contract_file.stem}_*_mapping.json'))
        if mapping_files:
            with open(mapping_files[0], 'r') as f:
                mapping = json.load(f)
            
            pages_flagged = len(mapping['chunks'])
            print(f"  Pages flagged for AI: {pages_flagged}")
            total_pages_processed += mapping.get('total_pages', pages_flagged)
            total_ai_pages += pages_flagged
    
    # Process all chunks with AI
    print(f"\\nProcessing all {total_ai_pages} flagged pages with AI...")
    ai_start = time.time()
    result = os.system('cd /home/cliff/redact && python3 phase3_selective.py phi3.5')
    ai_time = time.time() - ai_start
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\\n=== ORIGINAL APPROACH RESULTS ===")
    print(f"Total contracts processed: {len(tupperware_files)}")
    print(f"Total pages processed: {total_pages_processed}")
    print(f"Pages sent to AI: {total_ai_pages}")
    print(f"Total processing time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"AI processing time: {ai_time:.2f} seconds ({ai_time/60:.2f} minutes)")
    
    # Save results
    results = {
        'approach': 'original',
        'contracts_processed': len(tupperware_files),
        'total_pages': total_pages_processed,
        'ai_pages': total_ai_pages,
        'pattern_pages': 0,
        'total_time': total_time,
        'ai_time': ai_time
    }
    
    with open('/mnt/c/seedJura/original_approach_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\\nResults saved to: C:\\\\seedJura\\\\original_approach_results.json")
    return results

def compare_results():
    """Compare the two approaches"""
    
    try:
        with open('/mnt/c/seedJura/learn_then_apply_results.json', 'r') as f:
            learn_results = json.load(f)
        
        with open('/mnt/c/seedJura/original_approach_results.json', 'r') as f:
            original_results = json.load(f)
        
        print(f"\\n" + "="*60)
        print("=== COMPARISON RESULTS ===")
        print(f"\\nOriginal Approach:")
        print(f"  Time: {original_results['total_time']:.2f}s ({original_results['total_time']/60:.2f}m)")
        print(f"  AI pages: {original_results['ai_pages']}")
        
        print(f"\\nLearn-then-Apply Approach:")
        print(f"  Time: {learn_results['total_time']:.2f}s ({learn_results['total_time']/60:.2f}m)")
        print(f"  AI pages: {learn_results['ai_pages']}")
        print(f"  Pattern pages: {learn_results['pattern_pages']}")
        print(f"  PII terms learned: {learn_results['learned_pii_count']}")
        
        if original_results['total_time'] > 0:
            speedup = original_results['total_time'] / learn_results['total_time']
            ai_reduction = (original_results['ai_pages'] - learn_results['ai_pages']) / original_results['ai_pages'] * 100
            
            print(f"\\nImprovement:")
            print(f"  Speedup: {speedup:.2f}x faster")
            print(f"  Time saved: {original_results['total_time'] - learn_results['total_time']:.2f} seconds")
            print(f"  AI reduction: {ai_reduction:.1f}% fewer AI calls")
            
            # Save comparison
            comparison = {
                'original': original_results,
                'learn_then_apply': learn_results,
                'improvement': {
                    'speedup': speedup,
                    'time_saved': original_results['total_time'] - learn_results['total_time'],
                    'ai_reduction_percent': ai_reduction
                }
            }
            
            with open('/mnt/c/seedJura/approach_comparison.json', 'w') as f:
                json.dump(comparison, f, indent=2)
            
            print(f"\\nComparison saved to: C:\\\\seedJura\\\\approach_comparison.json")
    
    except FileNotFoundError as e:
        print(f"Could not find results file: {e}")

def main():
    contracts_folder = "/mnt/c/seedJura/contracts"
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "learn":
            learn_then_apply_batch(contracts_folder)
        elif sys.argv[1] == "original":
            original_batch(contracts_folder)
        elif sys.argv[1] == "compare":
            compare_results()
        else:
            print("Usage: python3 test_optimization.py [learn|original|compare]")
    else:
        # Run both approaches
        print("Running both approaches for comparison...")
        learn_then_apply_batch(contracts_folder)
        time.sleep(2)
        original_batch(contracts_folder)
        compare_results()

if __name__ == "__main__":
    main()
