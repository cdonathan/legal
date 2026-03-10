#!/usr/bin/env python3
import requests
import json

def redact_with_phi35(text, host="172.25.48.1"):
    """Redact text using local phi3.5 via Ollama"""
    
    prompt = f"""You are a document redaction specialist. Replace ALL personally identifiable information with [REDACT].

REDACT these types of information:
- Personal names (first, last, full names)
- Company names and business entities
- Addresses, street names, building names
- Phone numbers, fax numbers, email addresses
- Dollar amounts and financial figures
- Dates that could be identifying
- Geographic locations (cities, states, zip codes)
- Account numbers, ID numbers
- Any other identifying information

PRESERVE legal terminology, generic business terms, and document structure.

Text to redact:
{text}

Return ONLY the redacted text with sensitive information replaced by [REDACT]."""

    url = f"http://{host}:11434/api/generate"
    
    data = {
        "model": "phi3.5",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "top_p": 0.1
        }
    }
    
    try:
        response = requests.post(url, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            redacted_text = result.get('response', '').strip()
            
            # Clean up any extra explanatory text
            lines = redacted_text.split('\n')
            # Find the main redacted content (usually the longest meaningful line)
            content_lines = [line.strip() for line in lines if line.strip() and not line.startswith('Return') and not line.startswith('Here')]
            
            if content_lines:
                return content_lines[0] if len(content_lines) == 1 else '\n'.join(content_lines)
            else:
                return redacted_text
                
        else:
            print(f"Ollama error: {response.status_code}")
            return text  # Return original on error
            
    except Exception as e:
        print(f"Redaction error: {e}")
        return text  # Return original on error

if __name__ == "__main__":
    # Test the function
    test_text = "John Smith from ABC Corp lives at 123 Main Street, Anytown, CA 90210. Contact: john@abc.com, 555-123-4567."
    
    print("Original:", test_text)
    redacted = redact_with_phi35(test_text)
    print("Redacted:", redacted)
