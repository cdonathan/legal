#!/usr/bin/env python3
"""
Debug AI Calls - Test each call individually
"""

import openai
import os

def test_ai_call():
    """Test a simple AI call to see if it works"""
    try:
        with open('/home/cliff/redact/openai_api_key.txt', 'r') as f:
            api_key = f.read().strip()
        client = openai.OpenAI(api_key=api_key)
        
        print("Testing AI call...")
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'AI is working' and nothing else."}],
            max_tokens=100,
            temperature=0.1
        )
        
        result = response.choices[0].message.content
        print(f"AI Response: {result}")
        
        # Test file creation
        test_file = "/home/cliff/redact/redline_project/test_ai_output.md"
        with open(test_file, 'w') as f:
            f.write(f"# Test AI Output\n\n{result}")
        
        print(f"✓ Created test file: {test_file}")
        
        if os.path.exists(test_file):
            print("✓ File exists and is readable")
        else:
            print("❌ File was not created")
            
    except Exception as e:
        print(f"❌ AI call failed: {e}")

if __name__ == "__main__":
    test_ai_call()
