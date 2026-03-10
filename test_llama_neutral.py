#!/usr/bin/env python3
import time
import requests

def test_llama_neutral_prompt(text):
    """Test llama3.2 with neutral document analysis prompt"""
    
    prompt = f"""Analyze this document text and identify any specific names, addresses, phone numbers, or email addresses that should be redacted for privacy.

Text: {text}

List any specific identifiers found:"""

    url = "http://172.25.48.1:11434/api/generate"
    
    data = {
        "model": "llama3.2:1b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "max_tokens": 150
        }
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=data, timeout=120)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            return end_time - start_time, result.get('response', '').strip()
        else:
            return None, f"Error: {response.status_code}"
            
    except Exception as e:
        return None, f"Error: {e}"

test_text = """This Purchase Agreement is entered into between John Smith, 
a resident of 123 Main Street, Anytown, CA 90210, and ABC Corp. 
Contact: john@email.com or 555-123-4567. Purchase price: $250,000."""

print("Testing llama3.2:1b with neutral prompt...")
duration, result = test_llama_neutral_prompt(test_text)

if duration:
    print(f"✓ Completed in {duration:.1f} seconds")
    print(f"Result: {result}")
else:
    print(f"✗ Failed: {result}")
