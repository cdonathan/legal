#!/usr/bin/env python3

def find_company_suffixes_in_whitelist():
    """Find all words in whitelist that could be part of company names"""
    
    # Common company suffixes and business terms
    company_terms = [
        # Legal entity types
        'company', 'companies', 'corp', 'corporation', 'incorporated', 'inc',
        'limited', 'ltd', 'llc', 'liability', 'partnership', 'partners',
        'association', 'group', 'holdings', 'enterprises', 'venture', 'ventures',
        'co', 'cos', 'firm', 'firms', 'business', 'businesses',
        
        # Business descriptors
        'industries', 'industrial', 'manufacturing', 'services', 'solutions',
        'systems', 'technologies', 'tech', 'consulting', 'consultants',
        'development', 'developers', 'construction', 'builders', 'building',
        'management', 'investments', 'capital', 'financial', 'finance',
        'insurance', 'realty', 'real', 'estate', 'properties', 'property',
        'retail', 'wholesale', 'trading', 'sales', 'marketing', 'media',
        'communications', 'telecom', 'networks', 'software', 'hardware',
        'engineering', 'research', 'laboratories', 'labs', 'medical',
        'healthcare', 'pharmaceutical', 'energy', 'power', 'utilities',
        'transportation', 'logistics', 'shipping', 'aviation', 'automotive',
        'manufacturing', 'production', 'operations', 'international', 'global',
        'national', 'regional', 'local', 'public', 'private', 'general',
        'specialty', 'specialty', 'professional', 'commercial', 'residential',
        
        # Geographic/organizational terms
        'north', 'south', 'east', 'west', 'central', 'american', 'united',
        'states', 'national', 'international', 'global', 'worldwide',
        'regional', 'local', 'metropolitan', 'urban', 'suburban', 'rural',
        
        # Common business words
        'trust', 'fund', 'funds', 'bank', 'banking', 'credit', 'union',
        'mutual', 'federal', 'state', 'county', 'city', 'municipal',
        'authority', 'commission', 'board', 'council', 'committee',
        'foundation', 'institute', 'center', 'centre', 'office', 'bureau',
        'agency', 'department', 'division', 'unit', 'branch', 'subsidiary',
        'affiliate', 'alliance', 'network', 'chain', 'franchise',
        
        # Industry-specific terms
        'hospital', 'clinic', 'medical', 'health', 'care', 'wellness',
        'school', 'college', 'university', 'education', 'learning',
        'church', 'ministry', 'religious', 'charitable', 'nonprofit',
        'club', 'society', 'organization', 'league', 'union', 'guild'
    ]
    
    # Load whitelist
    whitelist = set()
    with open('/home/cliff/redact/redaction_whitelist.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                whitelist.add(line.lower())
    
    # Find which company terms are in the whitelist
    whitelisted_company_terms = []
    for term in company_terms:
        if term.lower() in whitelist:
            whitelisted_company_terms.append(term)
    
    # Sort and display results
    whitelisted_company_terms.sort()
    
    print("=== COMPANY TERMS FOUND IN WHITELIST ===")
    print(f"Total terms checked: {len(company_terms)}")
    print(f"Terms found in whitelist: {len(whitelisted_company_terms)}")
    print()
    
    # Group by category for better readability
    legal_entities = []
    business_descriptors = []
    geographic_terms = []
    other_terms = []
    
    for term in whitelisted_company_terms:
        if term in ['company', 'companies', 'corp', 'corporation', 'incorporated', 'inc', 'limited', 'ltd', 'llc', 'liability', 'partnership', 'co', 'firm', 'business']:
            legal_entities.append(term)
        elif term in ['industries', 'services', 'systems', 'technologies', 'development', 'construction', 'management', 'consulting', 'solutions']:
            business_descriptors.append(term)
        elif term in ['north', 'south', 'east', 'west', 'central', 'national', 'international', 'global', 'american', 'united', 'states']:
            geographic_terms.append(term)
        else:
            other_terms.append(term)
    
    if legal_entities:
        print("LEGAL ENTITY TYPES:")
        for i in range(0, len(legal_entities), 8):
            print(f"  {', '.join(legal_entities[i:i+8])}")
        print()
    
    if business_descriptors:
        print("BUSINESS DESCRIPTORS:")
        for i in range(0, len(business_descriptors), 6):
            print(f"  {', '.join(business_descriptors[i:i+6])}")
        print()
    
    if geographic_terms:
        print("GEOGRAPHIC TERMS:")
        for i in range(0, len(geographic_terms), 8):
            print(f"  {', '.join(geographic_terms[i:i+8])}")
        print()
    
    if other_terms:
        print("OTHER BUSINESS TERMS:")
        for i in range(0, len(other_terms), 6):
            print(f"  {', '.join(other_terms[i:i+6])}")
        print()
    
    # Save to file for use in optimization
    with open('/home/cliff/redact/company_suffixes.txt', 'w') as f:
        for term in whitelisted_company_terms:
            f.write(f"{term}\n")
    
    print(f"Company suffixes saved to: /home/cliff/redact/company_suffixes.txt")
    
    return whitelisted_company_terms

if __name__ == "__main__":
    find_company_suffixes_in_whitelist()
