#!/usr/bin/env python3

def extract_company_terms_from_whitelist():
    """Extract company-related terms that are actually in the whitelist"""
    
    # Load whitelist
    whitelist = set()
    with open('/home/cliff/redact/redaction_whitelist.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                whitelist.add(line.lower())
    
    # Define potential company terms to check
    potential_company_terms = [
        'company', 'companies', 'corp', 'corporation', 'incorporated', 'inc',
        'limited', 'ltd', 'llc', 'liability', 'partnership', 'partners',
        'association', 'group', 'groups', 'holdings', 'enterprises', 
        'co', 'firm', 'firms', 'business', 'businesses',
        'industries', 'services', 'systems', 'technologies', 'solutions',
        'consulting', 'development', 'management', 'operations',
        'international', 'national', 'global', 'trust', 'fund', 'funds'
    ]
    
    # Find which terms are actually in whitelist
    whitelisted_company_terms = []
    for term in potential_company_terms:
        if term.lower() in whitelist:
            whitelisted_company_terms.append(term)
    
    # Sort for consistency
    whitelisted_company_terms.sort()
    
    print("=== COMPANY TERMS FOUND IN WHITELIST ===")
    print(f"Terms found: {len(whitelisted_company_terms)}")
    print()
    
    # Display in groups of 8 for readability
    for i in range(0, len(whitelisted_company_terms), 8):
        print(f"  {', '.join(whitelisted_company_terms[i:i+8])}")
    
    # Save to file for AI prompt
    with open('/home/cliff/redact/company_suffixes.txt', 'w') as f:
        for term in whitelisted_company_terms:
            f.write(f"{term}\n")
    
    print(f"\nSaved to: /home/cliff/redact/company_suffixes.txt")
    
    # Create AI prompt template
    prompt_template = f"""Look for company names in the text that end with these whitelisted business terms:

BUSINESS TERMS: {', '.join(whitelisted_company_terms)}

Find patterns like:
- [Name] + [Business Term] (e.g., "Smith Industries", "Johnson LLC")
- [Name] + [Name] + [Business Term] (e.g., "Smith Johnson Corp")

Return ONLY the complete company names found, one per line. No explanations.

Examples of what to find:
- Connor Industries
- Smith LLC  
- Johnson Development
- Williams Group

TEXT:
[DOCUMENT_TEXT_HERE]"""

    with open('/home/cliff/redact/company_detection_prompt.txt', 'w') as f:
        f.write(prompt_template)
    
    print(f"AI prompt template saved to: /home/cliff/redact/company_detection_prompt.txt")
    
    return whitelisted_company_terms

if __name__ == "__main__":
    extract_company_terms_from_whitelist()
