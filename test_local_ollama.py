#!/usr/bin/env python3
import requests
import json

def test_phi35_redaction():
    """Test phi3.5 redaction via local Ollama"""
    
    # Try WSL host IP and local network IP
    hosts = ["172.25.48.1", "192.168.1.145"]
    
    test_text = "John Smith lives at 123 Main Street, Anytown, CA 90210. His email is john@company.com and phone is 555-123-4567."
    
    prompt = f"""Redact all personally identifiable information (PII) from this text by replacing names, addresses, emails, and phone numbers with [REDACT]:

{test_text}

Return only the redacted text."""

    for host in hosts:
        url = f"http://{host}:11434/api/generate"
        
        data = {
            "model": "phi3.5",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0
            }
        }
        
        try:
            print(f"Testing connection to {host}...")
            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                redacted_text = result.get('response', '').strip()
                
                print(f"✓ Connected to Ollama at {host}")
                print(f"Original: {test_text}")
                print(f"Redacted: {redacted_text}")
                return host, redacted_text
                
        except Exception as e:
            print(f"✗ Failed to connect to {host}: {e}")
    
    print("Could not connect to Ollama. Make sure:")
    print("1. Ollama is running on your local machine")
    print("2. The phi3.5 model is installed: ollama pull phi3.5")
    print("3. Ollama is accessible from this environment")
    
    return None, None

if __name__ == "__main__":
    host, result = test_phi35_redaction()
