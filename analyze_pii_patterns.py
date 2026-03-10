#!/usr/bin/env python3
import re
from collections import defaultdict
from pathlib import Path

def analyze_pii_introduction_patterns():
    """Analyze when new PII is introduced vs repeated in documents"""
    
    # Load whitelist
    whitelist = set()
    with open('/home/cliff/redact/redaction_whitelist.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                whitelist.add(line.lower())
    
    results = {}
    
    # Analyze each document
    contracts_dir = Path('/mnt/c/seedJura/contracts')
    for contract_file in contracts_dir.glob('*.mhtml'):
        print(f"\nAnalyzing: {contract_file.name}")
        
        # Read and extract text
        with open(contract_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Simple text extraction (remove HTML tags)
        text = re.sub(r'<[^>]+>', ' ', content)
        text = re.sub(r'\s+', ' ', text)
        
        # Split into pages (approximate - every 1000 words)
        words = text.split()
        pages = []
        for i in range(0, len(words), 1000):
            page_text = ' '.join(words[i:i+1000])
            pages.append(page_text)
        
        # Track PII introduction
        seen_pii = set()
        page_analysis = []
        
        for page_num, page_text in enumerate(pages, 1):
            # Find non-whitelisted words
            page_words = re.findall(r'\b[A-Za-z]+\b', page_text)
            new_pii = []
            repeated_pii = []
            
            for word in page_words:
                if len(word) > 2 and word.lower() not in whitelist:
                    if word.lower() not in seen_pii:
                        new_pii.append(word)
                        seen_pii.add(word.lower())
                    else:
                        repeated_pii.append(word)
            
            if new_pii or repeated_pii:
                page_analysis.append({
                    'page': page_num,
                    'new_pii': list(set(new_pii)),
                    'repeated_pii': list(set(repeated_pii)),
                    'new_count': len(set(new_pii)),
                    'repeated_count': len(set(repeated_pii))
                })
        
        results[contract_file.name] = page_analysis
        
        # Summary for this document
        total_new = sum(p['new_count'] for p in page_analysis)
        total_repeated = sum(p['repeated_count'] for p in page_analysis)
        
        print(f"  Total pages with PII: {len(page_analysis)}")
        print(f"  New PII introductions: {total_new}")
        print(f"  Repeated PII instances: {total_repeated}")
        if total_new + total_repeated > 0:
            print(f"  New vs Repeated ratio: {total_new/(total_new + total_repeated):.2%} new")
    
    # Overall analysis
    print(f"\n=== OVERALL ANALYSIS ===")
    all_new = 0
    all_repeated = 0
    early_introduction_count = 0
    
    for doc_name, analysis in results.items():
        doc_new = sum(p['new_count'] for p in analysis)
        doc_repeated = sum(p['repeated_count'] for p in analysis)
        all_new += doc_new
        all_repeated += doc_repeated
        
        # Check if most new PII is introduced early
        if analysis:
            first_half_pages = len(analysis) // 2
            early_new = sum(p['new_count'] for p in analysis[:first_half_pages])
            if doc_new > 0 and early_new / doc_new > 0.7:  # 70% introduced in first half
                early_introduction_count += 1
    
    print(f"Total new PII across all docs: {all_new}")
    print(f"Total repeated PII: {all_repeated}")
    print(f"Documents with early PII introduction: {early_introduction_count}/{len(results)}")
    
    if all_new + all_repeated > 0:
        print(f"Overall new vs repeated: {all_new/(all_new + all_repeated):.2%} new")
    
    return results

if __name__ == "__main__":
    analyze_pii_introduction_patterns()
