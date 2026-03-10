#!/usr/bin/env python3
import time
import requests
import json

def test_model_speed(model_name, text):
    """Test PII detection speed for a specific model"""
    
    prompt = f"""You are a PII detector. Scan this text for personally identifiable information.

If you find PII, respond with: FOUND: [brief description]
If no PII, respond with: CLEAN

Text: {text}"""

    url = "http://172.25.48.1:11434/api/generate"
    
    data = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "max_tokens": 100
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

# Test text with PII
test_text = """This Purchase Agreement is entered into between John Smith, 
a resident of 123 Main Street, Anytown, CA 90210, and ABC Corp. 
Contact: john@email.com or 555-123-4567. Purchase price: $250,000."""

print("Comparing model speeds for PII detection...")
print(f"Test text: {test_text[:100]}...")

models = ["phi3.5", "llama3.2:1b"]

for model in models:
    print(f"\n--- Testing {model} ---")
    duration, result = test_model_speed(model, test_text)
    
    if duration:
        print(f"✓ Completed in {duration:.1f} seconds")
        print(f"Result: {result[:100]}...")
    else:
        print(f"✗ Failed: {result}")
