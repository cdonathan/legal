#!/usr/bin/env python3
from phi35_redactor import redact_with_phi35
import time

# Test with a small chunk
test_chunk = """
This Agreement is entered into between John Smith, a resident of 123 Main Street, 
Anytown, CA 90210, and ABC Corporation, located at 456 Oak Avenue, Business City, 
NY 10001. The purchase price is $250,000.00. Contact John at john@email.com or 
call 555-123-4567 for questions.
"""

print("Testing phi3.5 speed...")
print("Original chunk:")
print(test_chunk)

start_time = time.time()
redacted = redact_with_phi35(test_chunk)
end_time = time.time()

print(f"\nRedacted chunk (took {end_time - start_time:.1f} seconds):")
print(redacted)
