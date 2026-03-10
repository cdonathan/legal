#!/usr/bin/env python3
import os
import re
import json
from pathlib import Path
from redactor import ContractRedactor

def split_into_pages(text, words_per_page=500):
    """Split document into logical pages"""
    words = text.split()
    pages = []
    
    for i in range(0, len(words), words_per_page):
        page_content = ' '.join(words[i:i + words_per_page])
        pages.append({
            'page_num': len(pages) + 1,
            'content': page_content,
            'word_start': i + 1,
            'word_end': min(i + words_per_page, len(words))
        })
    
    return pages

def find_pii_pages(pages, redactor):
    """Find pages that contain PII based on pattern matching or non-whitelisted terms"""
    pii_pages = []
    
    for page in pages:
        has_pii = False
        flagged_reasons = []
        
        # Skip pages that are clearly HTML/CSS artifacts
        if is_garbage_page(page['content']):
            continue
        
        # Check for pattern matches (addresses, phones, emails, etc.)
        for pattern, label in redactor.patterns:
            if re.search(pattern, page['content'], re.IGNORECASE):
                has_pii = True
                flagged_reasons.append(f"Pattern: {label}")
                break
        
        # Check for non-whitelisted words (same logic as whitelist_redact)
        if not has_pii:
            words = re.findall(r'\b[A-Za-z]+\b', page['content'])
            flagged_words = []
            
            for word in words:
                if word.lower() not in redactor.whitelist and len(word) > 2:
                    if not re.match(r'\[.*\]', word):  # Skip already redacted
                        flagged_words.append(word)
            
            # Only flag page if it has multiple non-whitelisted words (reduces false positives)
            if len(set(flagged_words)) >= 3:
                has_pii = True
                flagged_reasons.append(f"Non-whitelisted words: {', '.join(list(set(flagged_words)))}")
        
        if has_pii:
            page['flagged_reasons'] = flagged_reasons
            pii_pages.append(page)
            print(f"  Page {page['page_num']}: {', '.join(flagged_reasons)}")
    
    return pii_pages

def is_garbage_page(content):
    """Check if page contains HTML/CSS artifacts or base64 data"""
    content_lower = content.lower()
    
    # Check for base64 patterns (long strings of random alphanumeric)
    base64_pattern = r'[A-Za-z0-9+/]{50,}'
    if re.search(base64_pattern, content):
        return True
    
    # Check for CSS/HTML artifacts
    css_indicators = [
        '@font-face', 'chrome-extension', 'multipartboundary', 
        'content-type:', 'content-location:', 'woff2', 'format("woff")',
        'font-family:', 'font-weight:', 'font-style:'
    ]
    
    for indicator in css_indicators:
        if indicator in content_lower:
            return True
    
    # Check if page is mostly random characters (base64 encoded)
    words = re.findall(r'\b[A-Za-z]+\b', content)
    if len(words) > 10:
        random_words = sum(1 for word in words if len(word) > 8 and not re.match(r'^[a-z]+$', word.lower()))
        if random_words / len(words) > 0.5:  # More than 50% random-looking words
            return True
    
    return False

def phase1_page_redact(input_file):
    """Phase 1: Pattern redaction + identify PII pages"""
    print("=== PHASE 1: PAGE-BASED PATTERN REDACTION ===")
    
    redactor = ContractRedactor()
    output_dir = '/mnt/c/seedJura/contracts/phase1'
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract text
    if input_file.endswith('.mhtml'):
        text = redactor.extract_text_from_mhtml(input_file)
    else:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    
    # Apply pattern redaction
    redacted_text, pattern_findings = redactor.pattern_redact(text)
    
    # Split into pages
    pages = split_into_pages(redacted_text, words_per_page=500)
    
    # Always include first page and last page
    selected_pages = []
    if pages:
        selected_pages.append(pages[0])  # First page
        
        # Find pages with PII (excluding first page to avoid duplicates)
        pii_pages = find_pii_pages(pages[1:-1], redactor)  # Skip first and last
        selected_pages.extend(pii_pages)
        
        # Add last page if it's different from first
        if len(pages) > 1:
            selected_pages.append(pages[-1])  # Last page
    
    # Save redacted file
    input_name = os.path.basename(input_file)
    name_without_ext = os.path.splitext(input_name)[0]
    output_file = os.path.join(output_dir, f"{name_without_ext}_REDACTED.txt")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(redacted_text)
    
    # Save selected pages for phase 2
    pages_file = os.path.join(output_dir, f"{name_without_ext}_PAGES.json")
    with open(pages_file, 'w', encoding='utf-8') as f:
        json.dump({
            'original_file': input_name,
            'total_pages': len(pages),
            'selected_pages': len(selected_pages),
            'pattern_redactions': len(pattern_findings),
            'pages': selected_pages
        }, f, indent=2)
    
    print(f"Total pages: {len(pages)}")
    print(f"Selected pages for LLM: {len(selected_pages)}")
    print(f"Pattern redactions: {len(pattern_findings)}")
    print(f"Saved: {output_file}")
    
    return output_file, pages_file

def phase2_page_chunk(redacted_file, pages_file):
    """Phase 2: Create chunks only from selected pages"""
    print("=== PHASE 2: PAGE-BASED CHUNKING ===")
    
    output_dir = '/mnt/c/seedJura/contracts/phase2'
    os.makedirs(output_dir, exist_ok=True)
    
    # Load selected pages
    with open(pages_file, 'r', encoding='utf-8') as f:
        pages_data = json.load(f)
    
    selected_pages = pages_data['pages']
    
    if not selected_pages:
        print("No pages selected for LLM processing")
        return [], None
    
    # Create one chunk per page
    chunks = []
    
    for i, page in enumerate(selected_pages):
        chunk_id = f"page_{page['page_num']:03d}"
        chunk_file = os.path.join(output_dir, f"{chunk_id}.txt")
        
        with open(chunk_file, 'w', encoding='utf-8') as f:
            f.write(page['content'])
        
        chunks.append({
            'id': chunk_id,
            'file': f"{chunk_id}.txt",
            'page_num': page['page_num'],
            'word_count': len(page['content'].split())
        })
    
    # Save mapping
    base_name = os.path.splitext(os.path.basename(redacted_file))[0]
    mapping_file = os.path.join(output_dir, f"{base_name}_mapping.json")
    
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump({
            'original_file': pages_data['original_file'],
            'redacted_file': os.path.basename(redacted_file),
            'total_chunks': len(chunks),
            'chunks': chunks,
            'processing_mode': 'page_based'
        }, f, indent=2)
    
    print(f"Created {len(chunks)} page-based chunks")
    return chunks, mapping_file

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 page_pipeline.py <contract_file>")
        return
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return
    
    # Phase 1: Page-based redaction
    redacted_file, pages_file = phase1_page_redact(input_file)
    
    # Phase 2: Page-based chunking
    chunks, mapping_file = phase2_page_chunk(redacted_file, pages_file)
    
    if chunks:
        print(f"\nReady for Phase 3: {len(chunks)} page chunks to process with LLM")
        print("Run: python3 phase3_selective.py")
    else:
        print("\nNo LLM processing needed - document fully redacted by patterns")

if __name__ == "__main__":
    import sys
    main()
