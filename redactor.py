#!/usr/bin/env python3
import re
import os
from pathlib import Path

class ContractRedactor:
    def __init__(self, whitelist_file="redaction_whitelist.txt"):
        self.whitelist = self.load_whitelist(whitelist_file)
        
        # Pattern-based redaction rules
        self.patterns = [
            # Title + Name patterns - redact names following titles
            (r'\b(Dr|Mr|Mrs|Ms|Miss|Prof|Professor|President|CEO|CFO|CTO|Director|Manager|Attorney|Lawyer|Esquire|Esq)\.?\s+([A-Z][a-z]+)', 'TITLE_NAME'),
            (r'\b(Vice\s+President|Senior\s+Vice\s+President|Executive\s+Vice\s+President)\s+([A-Z][a-z]+)', 'VP_NAME'),
            
            # Entity names between specific phrases
            (r'between\s+([^,]+),?\s+a\s+\w+\s+\w+(?:\s+\w+)?,?\s+and\s+([^,]+),?\s+a\s+\w+\s+\w+(?:\s+\w+)?', 'ENTITY'),
            (r'by and between\s+([^,]+),?\s+and\s+([^,]+)', 'ENTITY'),
            
            # City, State, Zipcode patterns
            (r'\b[A-Z][a-zA-Z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b', 'CITY_STATE_ZIP'),
            (r'\b[A-Z][a-zA-Z\s]+\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?\b', 'CITY_STATE_ZIP'),
            (r'\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b', 'STATE_ZIP'),
            
            # Comprehensive address pattern - numbers within 10 words before street suffixes
            (r'\b(?:\w+\s+){0,9}\d+\s+(?:\w+\s+)*(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Boulevard|Blvd\.?|Lane|Ln\.?|Drive|Dr\.?|Way|Circle|Cir\.?|Court|Ct\.?|Place|Pl\.?|Parkway|Pkwy\.?|Highway|Hwy\.?|Terrace|Ter\.?|Trail|Square|Sq\.?)\b', 'ADDRESS'),
            
            # Existing address patterns
            (r'having an address at\s+([^.]+)', 'ADDRESS'),
            (r'located at\s+([^,\n]+)', 'ADDRESS'),
            
            # Social Security Numbers
            (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),
            (r'\b\d{9}\b', 'SSN'),
            
            # Tax ID Numbers (EIN)
            (r'\b\d{2}-\d{7}\b', 'TAX_ID'),
            
            # Account Numbers
            (r'\b(?:Account|Acct)\.?\s*#?\s*\d+\b', 'ACCOUNT'),
            (r'\b(?:Account|Acct)\.?\s*[Nn]umber:?\s*\d+\b', 'ACCOUNT'),
            
            # Credit Card Numbers
            (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', 'CREDIT_CARD'),
            (r'\b\d{16}\b', 'CREDIT_CARD'),
            
            # Bank Routing Numbers (9 digits)
            (r'\b(?:Routing|ABA)\.?\s*#?\s*\d{9}\b', 'ROUTING'),
            
            # Driver's License (varies by state, common patterns)
            (r'\b[A-Z]\d{7,8}\b', 'DRIVERS_LICENSE'),
            (r'\b\d{8,9}\b', 'DRIVERS_LICENSE'),
            
            # Specific dollar amounts
            (r'\$[\d,]+(?:\.\d{2})?', 'AMOUNT'),
            (r'[A-Z][a-z]+\s+[A-Z][a-z]+\s+(?:and\s+\d+/100\s+)?[Dd]ollars?\s+\(\$[\d,]+(?:\.\d{2})?\)', 'AMOUNT'),
            
            # Phone numbers
            (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', 'PHONE'),
            
            # Email addresses
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL'),
            
            # Limited Partnership entities
            (r'\b([A-Z][a-zA-Z\s&]+)\s+Limited Partnership\b', 'LIMITED_PARTNERSHIP'),
            
            # Dates in contracts
            (r'this\s+\d{1,2}(?:st|nd|rd|th)?\s+day of\s+\w+,?\s+\d{4}', 'DATE'),
        ]
    
    def load_whitelist(self, filename):
        """Load whitelist from text file"""
        whitelist = set()
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        whitelist.add(line.lower())
        except FileNotFoundError:
            print(f"Warning: {filename} not found. Using empty whitelist.")
        
        return whitelist
    
    def extract_text_from_mhtml(self, file_path):
        """Extract readable text from MHTML files, excluding base64 sections"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Split content by MIME boundaries and process only text sections
        lines = content.split('\n')
        text_lines = []
        skip_section = False
        
        for line in lines:
            # Skip base64 encoded sections
            if 'Content-Transfer-Encoding: base64' in line:
                skip_section = True
                continue
            elif line.startswith('------') and 'Boundary' in line:
                skip_section = False  # New section, reset
                continue
            elif skip_section:
                continue  # Skip this line if we're in a base64 section
            
            # Skip other binary/encoded content indicators
            if any(indicator in line.lower() for indicator in [
                'content-type: image', 'content-type: application', 
                'content-type: font', 'webkit-', 'chrome-extension']):
                skip_section = True
                continue
                
            text_lines.append(line)
        
        # Rejoin the filtered content
        filtered_content = '\n'.join(text_lines)
        
        # Fix quoted-printable encoding first (before removing HTML)
        text = re.sub(r'=\r?\n', '', filtered_content)  # Remove soft line breaks
        text = re.sub(r'=([0-9A-F]{2})', lambda m: chr(int(m.group(1), 16)), text)  # Decode hex chars
        
        # Remove HTML tags and decode entities
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        
        return text
    
    def pattern_redact(self, text):
        """First pass: Pattern-based redaction"""
        redacted_text = text
        findings = []
        
        for pattern, label in self.patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                findings.append({
                    'type': 'pattern',
                    'label': label,
                    'text': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })
                # Actually redact the matched text
                redacted_text = redacted_text.replace(match.group(), '[REDACT]')
                redacted_text = redacted_text.replace(match.group(), f'[{label}]', 1)
        
        # Post-process: If a word is redacted and followed by "Title", "Insurance", or "Company", redact those too
        redacted_text = re.sub(r'\[REDACT\]\s+(Title|Insurance|Company)', '[REDACT] [REDACT]', redacted_text, flags=re.IGNORECASE)
        
        return redacted_text, findings
    
    def whitelist_redact(self, text):
        """Second pass: Whitelist-based redaction"""
        redacted_text = text
        words = re.findall(r'\b[A-Za-z]+\b', text)
        findings = []
        
        for word in words:
            if word.lower() not in self.whitelist and len(word) > 2:
                # Skip if already redacted
                if not re.match(r'\[.*\]', word):
                    findings.append({
                        'type': 'whitelist',
                        'label': 'NON_WHITELISTED',
                        'text': word
                    })
                    # Actually redact the word
                    redacted_text = re.sub(r'\b' + re.escape(word) + r'\b', '[REDACT]', redacted_text)
        
        return redacted_text, findings
    
    def redact_file(self, file_path):
        """Process a single file"""
        print(f"\n=== Processing: {os.path.basename(file_path)} ===")
        
        if file_path.endswith('.mhtml'):
            text = self.extract_text_from_mhtml(file_path)
        elif file_path.endswith('.pdf'):
            print("PDF processing not implemented yet")
            return
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        
        # First pass: Pattern-based redaction
        redacted_text, pattern_findings = self.pattern_redact(text)
        
        # Second pass: Whitelist-based redaction
        redacted_text, whitelist_findings = self.whitelist_redact(redacted_text)
        
        # Report findings
        print(f"\nPattern-based findings ({len(pattern_findings)}):")
        for finding in pattern_findings[:10]:  # Show first 10
            print(f"  {finding['label']}: {finding['text'][:50]}...")
        
        print(f"\nNon-whitelisted words ({len(whitelist_findings)}):")
        unique_words = list(set([f['text'] for f in whitelist_findings]))[:20]
        print(f"  {', '.join(unique_words)}")
        
        return pattern_findings, whitelist_findings

def main():
    redactor = ContractRedactor()
    contracts_dir = Path.home() / 'redact' / 'contracts'
    
    print(f"Loaded {len(redactor.whitelist)} words from whitelist")
    
    for file_path in contracts_dir.glob('*.mhtml'):
        redactor.redact_file(str(file_path))

if __name__ == "__main__":
    main()
