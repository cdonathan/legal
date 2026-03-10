#!/usr/bin/env python3
import requests
import json

def review_for_pii(text, host="172.25.48.1"):
    """Use qwen2.5:3b as a PII reviewer - scan and flag potential issues"""
    
    prompt = f"""Analyze this document text and identify any personally identifiable information that should be redacted for privacy compliance.

Look for: names, addresses, phone numbers, email addresses, financial amounts.

If PII found, respond with: FOUND: [list items]
If no PII, respond with: CLEAN

Text: {text}"""

    url = f"http://{host}:11434/api/generate"
    
    data = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "max_tokens": 200
        }
    }
    
    try:
        response = requests.post(url, json=data, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            review_result = result.get('response', '').strip()
            
            # Check if PII was found
            if review_result.upper().startswith('FOUND'):
                return True, review_result
            else:
                return False, "CLEAN"
                
        else:
            return False, f"Error: {response.status_code}"
            
    except Exception as e:
        return False, f"Review error: {e}"

if __name__ == "__main__":
    # Test the reviewer
    test_text = "The agreement was signed on the effective date. The buyer agrees to the terms."
    
    has_pii, result = review_for_pii(test_text)
    print(f"Has PII: {has_pii}")
    print(f"Result: {result}")
