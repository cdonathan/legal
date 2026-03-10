#!/usr/bin/env python3
import time
from phi35_reviewer import review_for_pii

# Create 3 test chunks of 1000 characters each
chunks = [
    """This Purchase Agreement is entered into on January 15, 2024, between John Smith, a resident of 123 Main Street, Anytown, California 90210, and ABC Real Estate Corp, located at 456 Oak Avenue, Business City, New York 10001. The buyer agrees to purchase the property for $250,000.00. Contact: john.smith@email.com or 555-123-4567. The seller warrants that the property is free and clear of all liens and encumbrances. Mary Johnson, the listing agent, can be reached at mary@realty.com or 555-999-8888. The property inspection will be conducted by XYZ Inspections at 321 Elm Street, Springfield, IL 62701. Payment of $5,000 earnest money is due within 48 hours. This agreement shall be governed by the laws of the State of California. Any disputes shall be resolved through binding arbitration. The parties acknowledge they have read and understood all terms. Signed this day by both buyer and seller in the presence of notary public Sarah Williams, commission #12345."""[:1000],

    """The closing date is February 28, 2024. All contingencies must be satisfied by February 15, 2024. The buyer has the right to inspect the property within 10 business days of signing this agreement. The seller agrees to provide clear title and deliver all necessary documents at closing. The buyer's attorney is David Brown at brown@lawfirm.com or 555-444-3333. The seller's attorney is Lisa Green at lisa.green@legal.com or 555-777-8888. The property is located at 789 Pine Road, Riverside, CA 92501. The loan amount is $200,000 from First National Bank. The buyer's social security number is 123-45-6789. The seller's tax ID is 98-7654321. All parties must sign in the presence of witnesses. The earnest money deposit of $10,000 will be held in escrow by Title Company Inc at 555 Business Blvd, Suite 200, Commerce City, CA 90210."""[:1000],

    """Additional terms and conditions apply to this real estate transaction. The buyer Michael Davis and seller Jennifer Wilson agree to all provisions herein. The property includes all fixtures, appliances, and improvements. The buyer's employment verification shows income of $75,000 annually at Tech Corp, 123 Innovation Drive, Silicon Valley, CA 94000. The seller's contact during escrow is jennifer.wilson@email.com or mobile 555-222-1111. The property appraisal will be conducted by Certified Appraisers LLC. The home warranty will be provided by Home Shield Services for one year. The buyer's down payment of $50,000 will be verified by bank statements. The closing costs are estimated at $8,500. The property taxes for the current year are $4,200. The homeowner's insurance policy number is HO-987654321 with Premium Insurance Co."""[:1000]
]

print("Testing 3 sequential 1000-character chunks...")

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
        results.append((i, duration, has_pii, result[:80]))
        
        print(f"✓ Completed in {duration:.1f} seconds")
        print(f"Has PII: {has_pii}")
        print(f"Result: {result[:80]}...")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append((i, 0, False, str(e)))

total_time = time.time() - total_start

print(f"\n=== SUMMARY ===")
print(f"Total time: {total_time:.1f} seconds")
for chunk_num, duration, has_pii, result in results:
    print(f"Chunk {chunk_num}: {duration:.1f}s, PII: {has_pii}")
print(f"Average per chunk: {total_time/len(chunks):.1f} seconds")
