#!/usr/bin/env python3
import os
import sys
import re
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import redactor class
from redactor import ContractRedactor

# Import phase 5 formatting
def phase5_format(final_files):
    """Phase 5: Create formatted PDF output"""
    try:
        import subprocess
        formatted_files = []
        
        for file_path in final_files:
            print(f"Creating PDF: {os.path.basename(file_path)}")
            result = subprocess.run([
                'python3', '/home/cliff/redact/simple_pdf.py', file_path
            ], capture_output=True, text=True, cwd='/home/cliff/redact', timeout=30)
            
            if result.returncode == 0:
                # Look for the created PDF file
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                pdf_file = f"/mnt/c/seedJura/contracts/phase4/{base_name}.pdf"
                if os.path.exists(pdf_file):
                    formatted_files.append(pdf_file)
                    print(f"✓ PDF created: {os.path.basename(pdf_file)}")
                else:
                    formatted_files.append(file_path)  # Keep original if PDF failed
                    print(f"⚠️  PDF not found, keeping text file")
            else:
                print(f"✗ PDF creation failed: {result.stderr}")
                formatted_files.append(file_path)  # Keep original if PDF failed
        
        print(f"Phase 5 complete: {len(formatted_files)} files ready")
        return formatted_files
        
    except Exception as e:
        print(f"Phase 5 error: {e}")
        return final_files

def phase1_redact(input_file):
    """Phase 1: Pattern-based redaction"""
    print("=== PHASE 1: PATTERN REDACTION ===")
    
    redactor = ContractRedactor()
    output_dir = '/mnt/c/seedJura/contracts/phase1'
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Processing: {os.path.basename(input_file)}")
    
    # Extract text from file
    if input_file.endswith('.mhtml'):
        text = redactor.extract_text_from_mhtml(input_file)
    else:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    
    # Apply pattern-based redaction with [REDACTED]
    redacted_text = text
    pattern_findings = []
    
    for pattern, label in redactor.patterns:
        matches = list(re.finditer(pattern, redacted_text, re.IGNORECASE))
        for match in matches:
            pattern_findings.append({
                'type': 'pattern',
                'label': label,
                'text': match.group(),
                'start': match.start(),
                'end': match.end()
            })
            redacted_text = redacted_text.replace(match.group(), '[REDACTED]', 1)
    
    # Apply whitelist-based redaction
    redacted_text, whitelist_findings = redactor.whitelist_redact(redacted_text)
    
    # Create output filename
    input_name = os.path.basename(input_file)
    name_without_ext = os.path.splitext(input_name)[0]
    output_file = os.path.join(output_dir, f"{name_without_ext}_REDACTED.txt")
    
    # Save redacted version
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(redacted_text)
        f.write("\n\n" + "=" * 50)
        f.write("\n=== REDACTION SUMMARY ===\n")
        f.write(f"Original file: {input_name}\n")
        f.write(f"Pattern redactions: {len(pattern_findings)}\n")
        f.write(f"Flagged terms: {len(whitelist_findings)}\n")
    
    print(f"Phase 1 complete: {len(pattern_findings)} redactions, {len(whitelist_findings)} flagged terms")
    return output_file

def phase2_chunk(redacted_file):
    """Phase 2: Chunk into random hash files"""
    print("\n=== PHASE 2: CHUNKING ===")
    
    import hashlib
    import random
    import string
    
    def generate_random_hash():
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        return hashlib.md5(random_string.encode()).hexdigest()[:12]
    
    output_dir = '/mnt/c/seedJura/contracts/phase2'
    os.makedirs(output_dir, exist_ok=True)
    
    # Read the file
    with open(redacted_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split into characters instead of words for faster AI processing
    chunk_size = 1000  # characters
    content_length = len(content)
    
    # Get base filename
    base_name = os.path.splitext(os.path.basename(redacted_file))[0]
    
    # Create chunks with random hash IDs
    chunks_info = []
    chunk_files = []
    
    for i in range(0, content_length, chunk_size):
        chunk_content = content[i:i + chunk_size]
        chunk_hash = generate_random_hash()
        chunk_order = len(chunks_info) + 1
        
        # Save chunk with hash ID as filename
        chunk_filename = f"{chunk_hash}.txt"
        chunk_path = os.path.join(output_dir, chunk_filename)
        
        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write(chunk_content)
        
        # Store mapping information
        chunks_info.append({
            'hash_id': chunk_hash,
            'filename': chunk_filename,
            'order': chunk_order,
            'char_count': len(chunk_content),
            'start_char': i + 1,
            'end_char': min(i + chunk_size, content_length)
        })
        
        chunk_files.append(chunk_path)
        print(f"Created chunk {chunk_order}: {chunk_hash}.txt ({len(chunk_content)} chars)")
    
    # Create mapping file
    mapping = {
        'original_file': os.path.basename(redacted_file),
        'total_chunks': len(chunks_info),
        'total_chars': content_length,
        'chunk_size': chunk_size,
        'chunks': chunks_info
    }
    
    mapping_filename = f"{base_name}_mapping.json"
    mapping_path = os.path.join(output_dir, mapping_filename)
    
    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2)
    
    print(f"Phase 2 complete: {len(chunk_files)} chunks created")
    return chunk_files, mapping_path

def phase3_ai_redact():
    """Phase 3: AI-based PII review with phi3.5"""
    print("\n=== PHASE 3: AI PII REVIEW WITH QWEN2.5:3B ===")
    
    from phi35_reviewer import review_for_pii
    import time
    
    start_time = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] Starting AI review with qwen2.5:3b...")
    
    # Directories
    input_dir = '/mnt/c/seedJura/contracts/phase2'
    output_dir = '/mnt/c/seedJura/contracts/phase3'
    os.makedirs(output_dir, exist_ok=True)
    
    # Find chunk files
    input_path = Path(input_dir)
    chunk_files = [f for f in input_path.glob('*.txt') if not f.name.endswith('_mapping.json')]
    
    if not chunk_files:
        print("No chunk files found in phase2")
        return False
    
    print(f"Reviewing {len(chunk_files)} chunks with qwen2.5:3b...")
    
    review_results = []
    
    for i, chunk_file in enumerate(chunk_files, 1):
        chunk_start = time.time()
        print(f"[{time.strftime('%H:%M:%S')}] Processing chunk {i}/{len(chunk_files)}: {chunk_file.name}")
        
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                chunk_content = f.read()
            
            # Review for PII
            has_pii, result = review_for_pii(chunk_content)
            
            # Copy chunk to output (unchanged)
            output_file = os.path.join(output_dir, chunk_file.name)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(chunk_content)
            
            # Store review result
            review_results.append({
                'chunk': chunk_file.name,
                'has_pii': has_pii,
                'review': result
            })
            
            chunk_time = time.time() - chunk_start
            status = "⚠️  PII FOUND" if has_pii else "✓ Clean"
            print(f"  {status} ({chunk_time:.1f}s)")
            
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            review_results.append({
                'chunk': chunk_file.name,
                'has_pii': False,
                'review': f"Error: {e}"
            })
    
    # Copy mapping files and add review results
    for mapping_file in input_path.glob('*_mapping.json'):
        output_mapping = os.path.join(output_dir, mapping_file.name)
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        mapping_data['phase3_processed'] = True
        mapping_data['ai_model'] = 'qwen2.5:3b'
        mapping_data['pii_review'] = review_results
        
        with open(output_mapping, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, indent=2)
    
    # Summary
    total_time = time.time() - start_time
    flagged_chunks = sum(1 for r in review_results if r['has_pii'])
    print(f"\n[{time.strftime('%H:%M:%S')}] Phase 3 COMPLETE!")
    print(f"Total time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print(f"Summary: {len(chunk_files)} chunks reviewed, {flagged_chunks} flagged for PII")
    
    if flagged_chunks > 0:
        print("⚠️  Manual review recommended for flagged chunks")
    
    return True

def phase4_reassemble():
    """Phase 4: Reassemble final document"""
    print("\n=== PHASE 4: REASSEMBLY ===")
    
    input_dir = '/mnt/c/seedJura/contracts/phase3'
    output_dir = '/mnt/c/seedJura/contracts/phase4'
    os.makedirs(output_dir, exist_ok=True)
    
    # Find mapping files
    input_path = Path(input_dir)
    mapping_files = list(input_path.glob('*_mapping.json'))
    
    if not mapping_files:
        print("No mapping files found in phase3")
        return None
    
    final_files = []
    for mapping_file in mapping_files:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        
        # Sort chunks by order
        sorted_chunks = sorted(mapping['chunks'], key=lambda x: x['order'])
        
        # Reassemble content
        reassembled_content = []
        for chunk_info in sorted_chunks:
            chunk_path = os.path.join(input_dir, chunk_info['filename'])
            if os.path.exists(chunk_path):
                with open(chunk_path, 'r', encoding='utf-8') as f:
                    chunk_content = f.read()
                    reassembled_content.append(chunk_content)
        
        # Create final file
        original_name = mapping['original_file']
        base_name = os.path.splitext(original_name)[0]
        output_filename = f"{base_name}_FINAL.txt"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(' '.join(reassembled_content))
        
        final_files.append(output_path)
        print(f"✓ Reassembled: {output_filename}")
    
    print(f"Phase 4 complete: {len(final_files)} final files created")
    return final_files

def run_pipeline(input_file):
    """Run complete 4-phase pipeline"""
    print(f"Starting 4-phase redaction pipeline for: {input_file}")
    print("=" * 60)
    
    try:
        # Phase 1: Pattern redaction
        redacted_file = phase1_redact(input_file)
        
        # Phase 2: Chunking
        chunk_files, mapping_file = phase2_chunk(redacted_file)
        
        # Phase 3: AI redaction
        if not phase3_ai_redact():
            print("Phase 3 failed - stopping pipeline")
            return None
        
        # Phase 4: Reassembly
        final_files = phase4_reassemble()
        
        # Phase 5: Document Building (PDF Formatting)
        print("\n=== PHASE 5: DOCUMENT BUILDING ===")
        formatted_files = phase5_format(final_files)
        
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE!")
        if formatted_files:
            print(f"Final formatted files: {[os.path.basename(f) for f in formatted_files]}")
        
        return formatted_files
        
    except Exception as e:
        print(f"Pipeline failed: {e}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 pipeline.py <input_file>")
        print("Example: python3 pipeline.py /mnt/c/seedJura/contracts/contract.mhtml")
        return
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        return
    
    run_pipeline(input_file)

if __name__ == "__main__":
    main()
