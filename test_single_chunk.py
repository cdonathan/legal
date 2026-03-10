#!/usr/bin/env python3
import time
from phi35_reviewer import review_for_pii

# Create a 1000 character test chunk
test_chunk = """
This Purchase Agreement is entered into on January 15, 2024, between John Smith, 
a resident of 123 Main Street, Anytown, California 90210, and ABC Real Estate Corp, 
located at 456 Oak Avenue, Business City, New York 10001. The buyer agrees to purchase 
the property located at 789 Pine Road for the sum of Two Hundred Fifty Thousand Dollars 
($250,000.00). The closing date shall be February 28, 2024. Contact information for 
the buyer is john.smith@email.com or telephone 555-123-4567. The seller can be reached 
at seller@abcrealty.com or 555-987-6543. This agreement is binding upon execution by 
both parties and their respective heirs and assigns.
""".strip()

print(f"Test chunk length: {len(test_chunk)} characters")
print(f"Test chunk: {test_chunk[:100]}...")

print("\nTesting phi3.5 reviewer...")
start_time = time.time()

try:
    has_pii, result = review_for_pii(test_chunk)
    end_time = time.time()
    
    print(f"✓ Review completed in {end_time - start_time:.1f} seconds")
    print(f"Has PII: {has_pii}")
    print(f"Result: {result}")
    
except Exception as e:
    print(f"✗ Error: {e}")
