#!/usr/bin/env python3
import sys
sys.path.append('/home/cliff/redact')
from redactor import ContractRedactor

def test_title_redaction():
    """Test the new title-based redaction logic"""
    
    # Sample text with title + name combinations
    test_text = """
    This agreement is signed by Dr. Johnson, the medical director.
    Mr. Smith will serve as the project manager.
    Mrs. Williams, CEO of the company, approves this contract.
    The Vice President Anderson will oversee operations.
    Attorney Brown represents the plaintiff.
    Professor Davis conducted the research.
    Ms. Garcia, CFO, signed the documents.
    """
    
    print("=== TESTING TITLE-BASED REDACTION ===")
    print("Original text:")
    print(test_text)
    
    # Create redactor and process
    redactor = ContractRedactor()
    redacted_text, findings = redactor.pattern_redact(test_text)
    
    print("\\nRedacted text:")
    print(redacted_text)
    
    print("\\nRedaction findings:")
    for item in findings:
        print(f"  {item['type']}: {item['original']}")
    
    print(f"\\nTotal redactions: {len(findings)}")

if __name__ == "__main__":
    test_title_redaction()
