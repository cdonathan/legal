#!/usr/bin/env python3
import time
import requests

def test_llama_1000_chars(text):
    """Test llama3.2:1b with 1000 character chunk"""
    
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
            "max_tokens": 200
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

# Create a 1000 character test chunk with lots of PII
test_chunk = """This Purchase Agreement is entered into on January 15, 2024, between John Smith, a resident of 123 Main Street, Anytown, California 90210, and ABC Real Estate Corp, located at 456 Oak Avenue, Business City, New York 10001. The buyer agrees to purchase the property for $250,000.00. Contact: john.smith@email.com or 555-123-4567. The seller warrants that the property is free and clear of all liens and encumbrances. Mary Johnson, the listing agent, can be reached at mary@realty.com or 555-999-8888. The property inspection will be conducted by XYZ Inspections at 321 Elm Street, Springfield, IL 62701. Payment of $5,000 earnest money is due within 48 hours. This agreement shall be governed by the laws of the State of California. Any disputes shall be resolved through binding arbitration. The parties acknowledge they have read and understood all terms. Signed this day by both buyer and seller in the presence of notary public Sarah Williams, commission #12345."""[:1000]

print(f"Testing llama3.2:1b with 1000-character chunk...")
print(f"Chunk length: {len(test_chunk)} characters")
print(f"Sample: {test_chunk[:100]}...")

duration, result = test_llama_1000_chars(test_chunk)

if duration:
    print(f"\n✓ Completed in {duration:.1f} seconds")
    print(f"Result: {result}")
else:
    print(f"\n✗ Failed: {result}")
