#!/usr/bin/env python3
import os
import re
import json
from pathlib import Path
from redactor import ContractRedactor

def identify_high_risk_sections(text, whitelist):
    """Identify sections that need LLM review"""
    sentences = re.split(r'[.!?]+', text)
    high_risk_sections = []
    
    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if len(sentence) < 20:  # Skip very short sentences
            continue
            
        # Check for non-whitelisted words
        words = re.findall(r'\b[A-Za-z]+\b', sentence)
        has_flagged_word = False
        
        for word in words:
            if len(word) > 2 and word.lower() not in whitelist:
                if not re.match(r'\[.*\]', word):  # Skip already redacted
                    has_flagged_word = True
                    break
        
        # Include opening/closing sections or flagged content
        if i < 10 or i >= len(sentences) - 5 or has_flagged_word:
            high_risk_sections.append(sentence)
    
    return high_risk_sections

def phase1_smart_redact(input_file):
    """Phase 1: Pattern redaction + identify high-risk sections"""
    print("=== PHASE 1: SMART PATTERN REDACTION ===")
    
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
    
    # Identify high-risk sections
    high_risk_sections = identify_high_risk_sections(redacted_text, redactor.whitelist)
    
    # Save redacted file
    input_name = os.path.basename(input_file)
    name_without_ext = os.path.splitext(input_name)[0]
    output_file = os.path.join(output_dir, f"{name_without_ext}_REDACTED.txt")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(redacted_text)
    
    # Save high-risk sections for phase 2
    risk_file = os.path.join(output_dir, f"{name_without_ext}_HIGHRISK.json")
    with open(risk_file, 'w', encoding='utf-8') as f:
        json.dump({
            'original_file': input_name,
            'pattern_redactions': len(pattern_findings),
            'high_risk_sections': high_risk_sections,
            'total_sections': len(high_risk_sections)
        }, f, indent=2)
    
    print(f"Pattern redactions: {len(pattern_findings)}")
    print(f"High-risk sections: {len(high_risk_sections)}")
    print(f"Saved: {output_file}")
    
    return output_file, risk_file

def phase2_smart_chunk(redacted_file, risk_file):
    """Phase 2: Create small chunks only from high-risk sections"""
    print("=== PHASE 2: SMART CHUNKING ===")
    
    output_dir = '/mnt/c/seedJura/contracts/phase2'
    os.makedirs(output_dir, exist_ok=True)
    
    # Load high-risk sections
    with open(risk_file, 'r', encoding='utf-8') as f:
        risk_data = json.load(f)
    
    high_risk_sections = risk_data['high_risk_sections']
    
    if not high_risk_sections:
        print("No high-risk sections found - skipping LLM processing")
        return [], None
    
    # Create small chunks from high-risk sections (max 300 words each)
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for section in high_risk_sections:
        section_words = len(section.split())
        
        if current_word_count + section_words > 300 and current_chunk:
            # Save current chunk
            chunk_content = ' '.join(current_chunk)
            chunk_id = f"risk_{len(chunks):03d}"
            chunk_file = os.path.join(output_dir, f"{chunk_id}.txt")
            
            with open(chunk_file, 'w', encoding='utf-8') as f:
                f.write(chunk_content)
            
            chunks.append({
                'id': chunk_id,
                'file': f"{chunk_id}.txt",
                'word_count': current_word_count
            })
            
            current_chunk = [section]
            current_word_count = section_words
        else:
            current_chunk.append(section)
            current_word_count += section_words
    
    # Save final chunk
    if current_chunk:
        chunk_content = ' '.join(current_chunk)
        chunk_id = f"risk_{len(chunks):03d}"
        chunk_file = os.path.join(output_dir, f"{chunk_id}.txt")
        
        with open(chunk_file, 'w', encoding='utf-8') as f:
            f.write(chunk_content)
        
        chunks.append({
            'id': chunk_id,
            'file': f"{chunk_id}.txt",
            'word_count': current_word_count
        })
    
    # Save mapping
    base_name = os.path.splitext(os.path.basename(redacted_file))[0]
    mapping_file = os.path.join(output_dir, f"{base_name}_mapping.json")
    
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump({
            'original_file': risk_data['original_file'],
            'redacted_file': os.path.basename(redacted_file),
            'total_chunks': len(chunks),
            'chunks': chunks,
            'processing_mode': 'high_risk_only'
        }, f, indent=2)
    
    print(f"Created {len(chunks)} small chunks from high-risk sections")
    return chunks, mapping_file

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 smart_pipeline.py <contract_file>")
        return
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return
    
    # Phase 1: Smart redaction
    redacted_file, risk_file = phase1_smart_redact(input_file)
    
    # Phase 2: Smart chunking
    chunks, mapping_file = phase2_smart_chunk(redacted_file, risk_file)
    
    if chunks:
        print(f"\nReady for Phase 3: {len(chunks)} chunks to process with LLM")
        print("Run: python3 phase3_selective.py")
    else:
        print("\nNo LLM processing needed - document fully redacted by patterns")

if __name__ == "__main__":
    import sys
    main()
