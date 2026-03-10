#!/usr/bin/env python3
from phi35_reviewer import review_for_pii
import time

# Test with a small chunk that has some PII
test_chunk = """
The agreement was signed on January 15, 2024. The buyer John Smith agrees to purchase 
the property for $250,000. Contact information: john@email.com or 555-123-4567.
"""

print("Testing phi3.5 reviewer speed...")
print("Test chunk:", test_chunk.strip())

start_time = time.time()
has_pii, result = review_for_pii(test_chunk)
end_time = time.time()

print(f"\nReview complete in {end_time - start_time:.1f} seconds")
print(f"Has PII: {has_pii}")
print(f"Result: {result}")
