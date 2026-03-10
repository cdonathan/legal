#!/usr/bin/env python3
import time
import os
import json
from pathlib import Path
from collections import defaultdict
import re

def test_current_approach(document_path):
    """Test current approach - process all flagged pages with AI"""
    print("=== TESTING CURRENT APPROACH ===")
    start_time = time.time()
    
    # Clear previous results
    os.system('rm -f /mnt/c/seedJura/contracts/phase2/*.txt /mnt/c/seedJura/contracts/phase2/*.json')
    os.system('rm -f /mnt/c/seedJura/contracts/phase3/*.txt /mnt/c/seedJura/contracts/phase3/*.json')
    
    # Run current pipeline on single document
    result = os.system(f'cd /home/cliff/redact && python3 page_pipeline.py "{document_path}"')
    if result != 0:
        print("Phase 1-2 failed")
        return None
    
    # Run AI processing
    result = os.system('cd /home/cliff/redact && python3 phase3_selective.py phi3.5')
    if result != 0:
        print("Phase 3 failed")
        return None
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Count pages processed
    phase3_files = list(Path('/mnt/c/seedJura/contracts/phase3').glob('page_*.txt'))
    
    print(f"Current approach completed in {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"Pages processed by AI: {len(phase3_files)}")
    
    return {
        'time': total_time,
        'ai_pages': len(phase3_files),
        'approach': 'current'
    }

def test_learn_then_apply_approach(document_path):
    """Test learn-then-apply approach"""
    print("\n=== TESTING LEARN-THEN-APPLY APPROACH ===")
    start_time = time.time()
    
    # Clear previous results
    os.system('rm -f /mnt/c/seedJura/contracts/phase2/*.txt /mnt/c/seedJura/contracts/phase2/*.json')
    os.system('rm -f /mnt/c/seedJura/contracts/phase3/*.txt /mnt/c/seedJura/contracts/phase3/*.json')
    
    # Step 1: Run phases 1-2 to identify flagged pages
    result = os.system(f'cd /home/cliff/redact && python3 page_pipeline.py "{document_path}"')
    if result != 0:
        print("Phase 1-2 failed")
        return None
    
    # Step 2: Analyze flagged words and group by first occurrence
    mapping_files = list(Path('/mnt/c/seedJura/contracts/phase3').glob('*_mapping.json'))
    if not mapping_files:
        # Look in phase2 for mapping files
        mapping_files = list(Path('/mnt/c/seedJura/contracts/phase2').glob('*_mapping.json'))
    
    if not mapping_files:
        print("No mapping file found in phase2 or phase3")
        return None
    
    with open(mapping_files[0], 'r') as f:
        mapping = json.load(f)
    
    # Load whitelist
    whitelist = set()
    with open('/home/cliff/redact/redaction_whitelist.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                whitelist.add(line.lower())
    
    # Analyze each chunk to find first occurrences
    first_occurrence_pages = set()
    learned_pii = set()
    
    phase2_dir = Path('/mnt/c/seedJura/contracts/phase2')
    
    for chunk_info in sorted(mapping['chunks'], key=lambda x: x['page_num']):
        chunk_file = phase2_dir / chunk_info['file']
        
        if chunk_file.exists():
            with open(chunk_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find non-whitelisted words
            words = re.findall(r'\b[A-Za-z]+\b', content)
            page_has_new_pii = False
            
            for word in words:
                if len(word) > 2 and word.lower() not in whitelist and word.lower() not in learned_pii:
                    page_has_new_pii = True
                    learned_pii.add(word.lower())
            
            if page_has_new_pii:
                first_occurrence_pages.add(chunk_info['file'])
    
    print(f"First occurrence pages to send to AI: {len(first_occurrence_pages)}")
    print(f"Total unique PII terms found: {len(learned_pii)}")
    
    # Step 3: Process only first occurrence pages with AI
    ai_start = time.time()
    
    # Create temporary mapping with only first occurrence pages
    temp_mapping = {
        'original_file': mapping['original_file'],
        'redacted_file': mapping['redacted_file'],
        'total_chunks': len(first_occurrence_pages),
        'chunks': [chunk for chunk in mapping['chunks'] if chunk['file'] in first_occurrence_pages],
        'processing_mode': 'learn_then_apply'
    }
    
    temp_mapping_file = Path('/mnt/c/seedJura/contracts/phase3') / 'temp_mapping.json'
    with open(temp_mapping_file, 'w') as f:
        json.dump(temp_mapping, f, indent=2)
    
    # Process only first occurrence pages
    result = os.system('cd /home/cliff/redact && python3 phase3_selective.py phi3.5')
    
    ai_end = time.time()
    ai_time = ai_end - ai_start
    
    # Step 4: Apply learned patterns to remaining pages (simulate instant pattern matching)
    pattern_pages = len(mapping['chunks']) - len(first_occurrence_pages)
    pattern_time = pattern_pages * 0.1  # Simulate 0.1 seconds per pattern match
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"AI processing time: {ai_time:.2f} seconds")
    print(f"Pattern matching time (simulated): {pattern_time:.2f} seconds")
    print(f"Learn-then-apply completed in {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"Pages processed by AI: {len(first_occurrence_pages)}")
    print(f"Pages processed by pattern matching: {pattern_pages}")
    
    return {
        'time': total_time,
        'ai_pages': len(first_occurrence_pages),
        'pattern_pages': pattern_pages,
        'ai_time': ai_time,
        'pattern_time': pattern_time,
        'approach': 'learn_then_apply'
    }

def main():
    document_path = "/mnt/c/seedJura/contracts/Exhibit.mhtml"
    
    print("Testing both approaches on Exhibit.mhtml (49 pages)")
    print("=" * 60)
    
    # Test current approach
    current_result = test_current_approach(document_path)
    
    # Wait a moment
    time.sleep(2)
    
    # Test learn-then-apply approach  
    learn_result = test_learn_then_apply_approach(document_path)
    
    # Compare results
    if current_result and learn_result:
        print("\n" + "=" * 60)
        print("=== COMPARISON RESULTS ===")
        print(f"Current approach:")
        print(f"  Time: {current_result['time']:.2f}s ({current_result['time']/60:.2f}m)")
        print(f"  AI pages: {current_result['ai_pages']}")
        
        print(f"\nLearn-then-apply approach:")
        print(f"  Time: {learn_result['time']:.2f}s ({learn_result['time']/60:.2f}m)")
        print(f"  AI pages: {learn_result['ai_pages']}")
        print(f"  Pattern pages: {learn_result['pattern_pages']}")
        
        if current_result['time'] > 0:
            speedup = current_result['time'] / learn_result['time']
            ai_reduction = (current_result['ai_pages'] - learn_result['ai_pages']) / current_result['ai_pages'] * 100
            
            print(f"\nImprovement:")
            print(f"  Speedup: {speedup:.2f}x faster")
            print(f"  AI reduction: {ai_reduction:.1f}% fewer AI calls")
            
            # Save results
            with open('/mnt/c/seedJura/approach_comparison.txt', 'w') as f:
                f.write("APPROACH COMPARISON RESULTS\n")
                f.write("=" * 40 + "\n\n")
                f.write(f"Document: Exhibit.mhtml (49 pages)\n\n")
                f.write(f"Current Approach:\n")
                f.write(f"  Time: {current_result['time']:.2f}s ({current_result['time']/60:.2f}m)\n")
                f.write(f"  AI pages: {current_result['ai_pages']}\n\n")
                f.write(f"Learn-then-Apply Approach:\n")
                f.write(f"  Time: {learn_result['time']:.2f}s ({learn_result['time']/60:.2f}m)\n")
                f.write(f"  AI pages: {learn_result['ai_pages']}\n")
                f.write(f"  Pattern pages: {learn_result['pattern_pages']}\n\n")
                f.write(f"Improvement:\n")
                f.write(f"  Speedup: {speedup:.2f}x faster\n")
                f.write(f"  AI reduction: {ai_reduction:.1f}% fewer AI calls\n")
            
            print(f"\nResults saved to: C:\\seedJura\\approach_comparison.txt")

if __name__ == "__main__":
    main()
