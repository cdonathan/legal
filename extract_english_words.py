#!/usr/bin/env python3
import re
from pathlib import Path
from redactor import ContractRedactor

def is_regular_english_word(word):
    """Check if a word looks like regular English"""
    # Skip if too short or too long
    if len(word) < 3 or len(word) > 20:
        return False
    
    # Skip if contains numbers or special characters
    if re.search(r'[0-9]', word):
        return False
    
    # Skip if all caps (likely acronym)
    if word.isupper() and len(word) > 3:
        return False
    
    # Skip if contains random character patterns (HTML artifacts)
    if re.search(r'[qxz]{2,}|[bcdfghjklmnpqrstvwxyz]{5,}', word.lower()):
        return False
    
    # Skip if looks like encoded text
    if len(set(word.lower())) < 3:  # Too few unique characters
        return False
    
    # Must contain vowels
    if not re.search(r'[aeiou]', word.lower()):
        return False
    
    # Skip if starts/ends with common HTML artifacts
    if word.lower().startswith(('css', 'mhtml', 'http', 'www')):
        return False
    
    return True

def extract_english_words():
    redactor = ContractRedactor()
    contracts_dir = Path.home() / 'redact' / 'contracts'
    
    all_terms = set()
    
    for file_path in contracts_dir.glob('*.mhtml'):
        text = redactor.extract_text_from_mhtml(str(file_path))
        redacted_text, _ = redactor.pattern_redact(text)
        whitelist_findings = redactor.whitelist_redact(redacted_text)
        
        for finding in whitelist_findings:
            word = finding['text'].lower()
            if is_regular_english_word(word):
                all_terms.add(word)
    
    # Sort alphabetically
    english_words = sorted(all_terms)
    
    print(f"Regular English words not in whitelist ({len(english_words)}):")
    print("=" * 60)
    
    for word in english_words:
        print(word)

if __name__ == "__main__":
    extract_english_words()
