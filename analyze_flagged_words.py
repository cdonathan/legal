#!/usr/bin/env python3
import os
from pathlib import Path
from redactor import ContractRedactor
import re

def is_random_artifact(word):
    """Check if a word is likely a random code/artifact"""
    # Skip very short words
    if len(word) < 3:
        return True
    
    # Base64-like patterns (mixed case with specific patterns)
    if re.match(r'^[A-Z]{2,4}[a-z]{1,4}[A-Z]*$', word):  # Like AAktlp, AEvhi
        return True
    if re.match(r'^[A-Z]{2,}[a-z]{1,2}$', word):  # Like AAMm, AAIk
        return True
    if re.match(r'^[A-Z]{4,}$', word) and len(word) <= 6:  # Like AKXN, AGVrt
        return True
    
    # Random strings with mixed case patterns
    if re.match(r'^[a-z]+[A-Z]+[a-z]*$', word) or re.match(r'^[A-Z]+[a-z]+[A-Z]+', word):
        return True
    
    # Words with numbers mixed in
    if re.search(r'[0-9]', word):
        return True
    
    # Very long strings (likely encoded)
    if len(word) > 15:
        return True
    
    # High consonant-to-vowel ratio (random strings)
    vowels = sum(1 for c in word.lower() if c in 'aeiou')
    consonants = len(word) - vowels
    if len(word) > 4 and vowels == 0:  # No vowels
        return True
    if len(word) > 6 and consonants / len(word) > 0.8:  # >80% consonants
        return True
    
    # Common artifact patterns
    artifact_patterns = [
        r'^[a-z]{1,3}[A-Z]{1,3}[a-z]*$',  # Mixed case short patterns
        r'^[bcdfghjklmnpqrstvwxyz]{4,}$',  # All consonants
        r'^[a-z]{2}[A-Z][a-z]{2}$',       # Specific mixed patterns
    ]
    
    for pattern in artifact_patterns:
        if re.match(pattern, word):
            return True
    
    return False

def extract_flagged_words_from_file(file_path, redactor):
    """Extract all flagged words from a single file, filtering HTML artifacts and random codes"""
    print(f"Processing: {os.path.basename(file_path)}")
    
    if file_path.endswith('.mhtml'):
        text = redactor.extract_text_from_mhtml(file_path)
    else:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    
    # Get all words and find non-whitelisted ones
    words = re.findall(r'\b[A-Za-z]+\b', text)
    flagged_words = []
    
    # HTML/MHTML artifacts to filter out
    html_artifacts = {
        'charset', 'mhtml', 'multipart', 'boundary', 'content', 'type', 'location', 
        'transfer', 'encoding', 'quoted', 'printable', 'webkit', 'chrome', 'extension',
        'font', 'face', 'src', 'url', 'format', 'woff', 'weight', 'style', 'normal',
        'italic', 'family', 'optimist', 'wikibuy', 'iconfont', 'assets', 'chatgpt',
        'cid', 'htm', 'https', 'www', 'com', 'archives', 'edgar', 'data', 'utm',
        'source', 'snapshot', 'subject', 'exhibit', 'mime', 'version', 'related',
        'multipartboundary', 'kHGLMxja', 'oJOdslQGX', 'xfpAhCi', 'PwouCKpwumPz'
    }
    
    for word in words:
        word_lower = word.lower()
        if (word_lower not in redactor.whitelist and 
            len(word) > 2 and 
            word_lower not in html_artifacts and
            not re.match(r'\[.*\]', word) and  # Skip already redacted
            not is_random_artifact(word)):  # Skip random codes/artifacts
            flagged_words.append(word)
    
    # Return unique flagged words
    return list(set(flagged_words))

def main():
    input_dir = Path("/mnt/c/seedJura/contracts")
    output_file = "flagged_words_analysis.txt"
    
    redactor = ContractRedactor()
    print(f"Loaded {len(redactor.whitelist)} whitelisted words")
    
    all_flagged_words = {}
    
    # Process all contract files
    for file_path in input_dir.glob("*.mhtml"):
        if file_path.is_file():
            flagged_words = extract_flagged_words_from_file(str(file_path), redactor)
            all_flagged_words[file_path.name] = flagged_words
            print(f"  Found {len(flagged_words)} flagged words")
    
    # Write results to file
    with open(output_file, 'w') as f:
        f.write("FLAGGED WORDS ANALYSIS\n")
        f.write("=" * 50 + "\n\n")
        
        # Write by file
        for filename, words in all_flagged_words.items():
            f.write(f"FILE: {filename}\n")
            f.write("-" * 40 + "\n")
            if words:
                for word in sorted(words):
                    f.write(f"{word}\n")
            else:
                f.write("No flagged words found.\n")
            f.write("\n")
        
        # Write consolidated list
        f.write("\nCONSOLIDATED FLAGGED WORDS (UNIQUE)\n")
        f.write("=" * 50 + "\n")
        all_words = set()
        for words in all_flagged_words.values():
            all_words.update(words)
        
        for word in sorted(all_words, key=str.lower):
            f.write(f"{word}\n")
    
    print(f"\nAnalysis complete. Results written to {output_file}")
    print(f"Total unique flagged words: {len(all_words)}")

if __name__ == "__main__":
    main()
