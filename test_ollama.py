#!/usr/bin/env python3
import requests
import time

def test_ollama():
    url = "http://172.25.48.1:11434/api/generate"
    
    data = {
        "model": "llama3.2:1b",
        "prompt": "Say hello",
        "stream": False
    }
    
    print("Testing Ollama connection...")
    start = time.time()
    
    try:
        response = requests.post(url, json=data, timeout=10)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success in {elapsed:.1f}s: {result.get('response', '')[:50]}")
        else:
            print(f"Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_ollama()
