#!/usr/bin/env python3
import time
from phi35_reviewer import review_for_pii

# Create 3 test chunks
chunks = [
    """This Purchase Agreement is entered into on January 15, 2024, between John Smith, 
a resident of 123 Main Street, Anytown, California 90210, and ABC Real Estate Corp, 
located at 456 Oak Avenue, Business City, New York 10001. The buyer agrees to purchase 
the property for $250,000.00. Contact: john.smith@email.com or 555-123-4567.""",

    """The seller warrants that the property is free and clear of all liens and encumbrances. 
Mary Johnson, the listing agent, can be reached at mary@realty.com or 555-999-8888. 
The property inspection will be conducted by XYZ Inspections at 321 Elm Street, 
Springfield, IL 62701. Payment of $5,000 earnest money is due within 48 hours.""",

    """This agreement shall be governed by the laws of the State of California. 
Any disputes shall be resolved through binding arbitration. The parties acknowledge 
they have read and understood all terms. Signed this day by both buyer and seller 
in the presence of notary public Sarah Williams, commission #12345."""
]

print("Testing 3 chunks in sequence...")

total_start = time.time()
results = []

for i, chunk in enumerate(chunks, 1):
    print(f"\n--- Processing Chunk {i} ---")
    print(f"Length: {len(chunk)} characters")
    
    start_time = time.time()
    try:
        has_pii, result = review_for_pii(chunk)
        end_time = time.time()
        
        duration = end_time - start_time
        results.append((i, duration, has_pii, result[:100]))
        
        print(f"✓ Completed in {duration:.1f} seconds")
        print(f"Has PII: {has_pii}")
        print(f"Result: {result[:100]}...")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append((i, 0, False, str(e)))

total_time = time.time() - total_start

print(f"\n=== SUMMARY ===")
print(f"Total time: {total_time:.1f} seconds")
for chunk_num, duration, has_pii, result in results:
    print(f"Chunk {chunk_num}: {duration:.1f}s, PII: {has_pii}")
print(f"Average per chunk: {total_time/len(chunks):.1f} seconds")
