#!/usr/bin/env python3
import re
from collections import defaultdict

def analyze_actual_flagged_pages():
    """Analyze the specific pages that were flagged in our pipeline"""
    
    # From the log, these are the pages that were actually flagged:
    flagged_data = {
        "Agreement of Sale and Purchase": [9, 10],
        "Agreement of Sale and Purchase2": [9, 10], 
        "brhc10022920_ex99-1": [9, 10],
        "Exhibit": [2, 3, 12, 15, 18, 23, 27, 28, 45, 46, 47, 48],
        "materialcontracts": [3, 4, 9, 11, 12, 15, 16, 22],
        "Real Estate Purchase Agreement": [24, 27],
        "Real Estate Purchase and Sale Agreement3": [],  # No specific pages listed
        "Sale and Purchase Agreement": [],  # No specific pages listed  
        "tv503983_ex10-21": []  # No specific pages listed
    }
    
    # From the log, these are the actual flagged words we saw:
    flagged_words = {
        "Agreement of Sale and Purchase": ["Spokane", "Esquire", "Simons", "Hartman", "Spielman", "Klawitter", "Keytronic", "ADEVCO"],
        "Exhibit": ["Declarant", "TBC", "Tupperware", "Traurig", "Greenberg", "Fidelity", "Greenwald", "Centerview", "Osceola", "SDP", "Gatorland", "Blossom", "SFWMD", "Lowe", "Wickes", "Ivey", "Roehlk", "Deerfield", "Sheppard", "Connor", "DEERFIELD", "DART", "CONNOR", "TUPPERWARE", "Sheehan", "tupperware", "OSCEOLA", "Kissimmee", "Trailside", "SSN", "Crosslands", "Terre", "Cinque", "Rapallo", "Brightview", "TOD", "TBCOM", "Venezia", "Solitude", "Mgmt", "Toho", "Lakeside", "Miranda", "SBA", "Parkway"],
        "materialcontracts": ["Celata", "Alden", "Lukas", "Drinker", "Reath", "Biddle", "Dorothy", "Kivi", "Purolator", "Bolinsky", "HCo", "Bray", "Whaler", "Deli", "OSE"]
    }
    
    print("=== ANALYSIS OF ACTUAL FLAGGED CONTENT ===")
    
    # Analyze patterns
    for doc, words in flagged_words.items():
        print(f"\n{doc}:")
        print(f"  Flagged pages: {flagged_data.get(doc, [])}")
        print(f"  Unique flagged words: {len(set(words))}")
        print(f"  Word types:")
        
        # Categorize words
        person_names = []
        company_names = []
        locations = []
        other = []
        
        for word in set(words):
            word_lower = word.lower()
            if word_lower in ['spokane', 'osceola', 'kissimmee']:
                locations.append(word)
            elif word_lower in ['tupperware', 'adevco', 'keytronic', 'dart', 'sfwmd']:
                company_names.append(word)
            elif word_lower in ['esquire', 'simons', 'hartman', 'spielman', 'klawitter', 'traurig', 'greenberg', 'roehlk', 'sheppard', 'connor', 'sheehan', 'celata', 'alden', 'lukas', 'dorothy', 'kivi', 'bolinsky']:
                person_names.append(word)
            else:
                other.append(word)
        
        if person_names:
            print(f"    Person names: {person_names}")
        if company_names:
            print(f"    Companies: {company_names}")
        if locations:
            print(f"    Locations: {locations}")
        if other:
            print(f"    Other: {other}")
    
    # Key insight
    print(f"\n=== KEY INSIGHTS ===")
    print("1. Most flagged words are legitimate PII (names, companies, locations)")
    print("2. Words like 'Tupperware', 'ADEVCO' appear multiple times but are company names")
    print("3. Person names like 'Connor', 'Sheppard' appear in different contexts")
    print("4. The repetition is mostly the SAME entities being referenced multiple times")
    print("\n=== OPTIMIZATION OPPORTUNITY ===")
    print("Once we identify 'Tupperware' as a company name on page 2,")
    print("we could auto-redact it on pages 3, 12, 23, 27, 45, 46, 47, 48")
    print("without sending those pages to AI - just pattern match!")

if __name__ == "__main__":
    analyze_actual_flagged_pages()
