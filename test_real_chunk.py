#!/usr/bin/env python3
import time
from phi35_reviewer import review_for_pii

# Test with actual pipeline chunk
chunk_file = "/mnt/c/seedJura/contracts/phase2/c5df265cbed1.txt"

print("Testing with actual pipeline chunk...")

with open(chunk_file, 'r', encoding='utf-8') as f:
    chunk_content = f.read()

print(f"Chunk length: {len(chunk_content)} characters")
print(f"Word count: {len(chunk_content.split())} words")
print(f"First 200 chars: {chunk_content[:200]}...")

print("\nProcessing with phi3.5...")
start_time = time.time()

try:
    has_pii, result = review_for_pii(chunk_content)
    end_time = time.time()
    
    print(f"✓ Completed in {end_time - start_time:.1f} seconds")
    print(f"Has PII: {has_pii}")
    print(f"Result: {result[:200]}...")
    
except Exception as e:
    print(f"✗ Error: {e}")
