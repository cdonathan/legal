#!/usr/bin/env python3

def test_ollama():
    """Test phi3.5 via Ollama"""
    try:
        import requests
        
        url = "http://localhost:11434/api/generate"
        data = {
            "model": "phi3.5",
            "prompt": "Redact PII from this text: John Smith lives at 123 Main St.",
            "stream": False
        }
        
        response = requests.post(url, json=data)
        if response.status_code == 200:
            result = response.json()
            print("Ollama response:", result.get('response', 'No response'))
            return True
        else:
            print(f"Ollama error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Ollama failed: {e}")
        return False

def test_transformers():
    """Test phi3.5 via transformers library"""
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        
        model_name = "microsoft/Phi-3.5-mini-instruct"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
        
        prompt = "Redact PII from this text: John Smith lives at 123 Main St."
        inputs = tokenizer(prompt, return_tensors="pt")
        
        with torch.no_grad():
            outputs = model.generate(**inputs, max_length=100, do_sample=False)
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print("Transformers response:", response)
        return True
        
    except Exception as e:
        print(f"Transformers failed: {e}")
        return False

def test_local_api():
    """Test phi3.5 via local API server"""
    try:
        import requests
        
        # Common local API endpoints
        endpoints = [
            "http://localhost:8000/v1/chat/completions",
            "http://localhost:5000/generate",
            "http://127.0.0.1:8080/completion"
        ]
        
        for url in endpoints:
            try:
                data = {
                    "messages": [{"role": "user", "content": "Redact PII: John Smith, 123 Main St."}],
                    "model": "phi3.5"
                }
                
                response = requests.post(url, json=data, timeout=5)
                if response.status_code == 200:
                    print(f"Local API working at {url}")
                    print("Response:", response.json())
                    return True
                    
            except requests.exceptions.RequestException:
                continue
                
        print("No local API found")
        return False
        
    except Exception as e:
        print(f"Local API test failed: {e}")
        return False

def main():
    print("Testing phi3.5 access methods...")
    
    methods = [
        ("Ollama", test_ollama),
        ("Transformers", test_transformers), 
        ("Local API", test_local_api)
    ]
    
    for name, test_func in methods:
        print(f"\n=== Testing {name} ===")
        if test_func():
            print(f"✓ {name} works!")
            break
        else:
            print(f"✗ {name} failed")
    else:
        print("\nNo working method found. How do you run phi3.5?")

if __name__ == "__main__":
    main()
