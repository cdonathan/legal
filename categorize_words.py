#!/usr/bin/env python3
import re

# Read all flagged words
with open('flagged_words_analysis.txt', 'r') as f:
    content = f.read()

# Extract consolidated words section
lines = content.split('\n')
start_idx = None
for i, line in enumerate(lines):
    if 'CONSOLIDATED FLAGGED WORDS' in line:
        start_idx = i + 2
        break

if start_idx:
    words = [line.strip() for line in lines[start_idx:] if line.strip()]
else:
    words = []

# Categorize words
common_terms = []
proper_nouns = []
abbreviations = []
technical_terms = []
possible_pii = []

# Common English words that should be whitelisted
common_word_patterns = [
    'acknowledging', 'accumulated', 'alleys', 'alleyways', 'allotments', 'altogether', 
    'annualized', 'appoints', 'balancing', 'contruction', 'distress', 'enjoyment',
    'govern', 'heretofore', 'hydrocarbon', 'inaccurate', 'nominee', 'numbered',
    'photovoltaic', 'punished', 'situate', 'taxpayer', 'variances', 'worthless'
]

# Legal/business terms
legal_terms = [
    'acknowledging', 'allotments', 'annualized', 'appoints', 'heretofore', 
    'nominee', 'taxpayer', 'variances', 'situate', 'punished', 'distress',
    'enjoyment', 'govern', 'accumulated', 'worthless', 'inaccurate'
]

for word in words:
    word_lower = word.lower()
    
    # Skip empty lines
    if not word:
        continue
        
    # Check if it's a common/legal term
    if (word_lower in common_word_patterns or 
        word_lower in legal_terms or
        (len(word) > 4 and 
         re.match(r'^[a-z]+$', word) and 
         sum(1 for c in word if c in 'aeiou') >= 2 and  # Has vowels
         not re.match(r'^[a-z]{2,3}[a-z]*$', word_lower))):  # Not just initials
        common_terms.append(word)
    
    # Proper nouns (capitalized, likely names/places)
    elif re.match(r'^[A-Z][a-z]+$', word) and len(word) > 3:
        proper_nouns.append(word)
    
    # All caps (likely abbreviations/companies)
    elif re.match(r'^[A-Z]{2,}$', word):
        abbreviations.append(word)
    
    # Technical terms (mixed case, specific patterns)
    elif re.match(r'^[a-z]+[A-Z]', word) or 'Co' in word or 'LLC' in word:
        technical_terms.append(word)
    
    # Everything else might be PII
    else:
        possible_pii.append(word)

# Write analysis
with open('word_categorization.txt', 'w') as f:
    f.write("WORD CATEGORIZATION ANALYSIS\n")
    f.write("=" * 50 + "\n\n")
    
    f.write(f"COMMON TERMS TO WHITELIST ({len(common_terms)}):\n")
    f.write("-" * 30 + "\n")
    for word in sorted(set(common_terms)):
        f.write(f"{word}\n")
    
    f.write(f"\nPROPER NOUNS - LIKELY PII ({len(proper_nouns)}):\n")
    f.write("-" * 30 + "\n")
    for word in sorted(set(proper_nouns))[:50]:  # Show first 50
        f.write(f"{word}\n")
    
    f.write(f"\nABBREVIATIONS - LIKELY PII ({len(abbreviations)}):\n")
    f.write("-" * 30 + "\n")
    for word in sorted(set(abbreviations))[:30]:  # Show first 30
        f.write(f"{word}\n")

print(f"Analysis complete:")
print(f"Common terms to whitelist: {len(set(common_terms))}")
print(f"Proper nouns (likely PII): {len(set(proper_nouns))}")
print(f"Abbreviations (likely PII): {len(set(abbreviations))}")
print(f"Other possible PII: {len(set(possible_pii))}")
