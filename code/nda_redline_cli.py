#!/usr/bin/env python3
"""
NDA Redlining CLI with Real-Time Updates
Usage: python3 nda_redline_cli.py input.docx
"""

import sys
import os
import time
from enhanced_nda_processor import EnhancedNDAProcessor

def print_progress(message, step=None, total_steps=5):
    """Print progress with step indicator"""
    if step:
        progress = "█" * step + "░" * (total_steps - step)
        print(f"[{progress}] Step {step}/{total_steps}: {message}")
    else:
        print(f"🔄 {message}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 nda_redline_cli.py <input.docx>")
        print("Example: python3 nda_redline_cli.py my_nda.docx")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"❌ Error: File not found: {input_file}")
        sys.exit(1)
    
    if not input_file.lower().endswith('.docx'):
        print("❌ Error: Input must be a .docx file")
        sys.exit(1)
    
    print("🚀 NDA REDLINING SYSTEM")
    print("=" * 60)
    print(f"📄 Processing: {os.path.basename(input_file)}")
    print("=" * 60)
    
    # Create enhanced processor with real-time updates
    class VerboseNDAProcessor(EnhancedNDAProcessor):
        def extract_text_from_docx(self, docx_path):
            print_progress("Loading Word document...", 1)
            time.sleep(0.5)  # Brief pause for visibility
            result = super().extract_text_from_docx(docx_path)
            print(f"   ✓ Extracted {len(result)} paragraphs")
            return result
        
        def redact_personal_info(self, text):
            print_progress("Scanning for personal information...", 1)
            time.sleep(0.3)
            result = super().redact_personal_info(text)
            print(f"   ✓ Found and redacted {len(self.personal_info)} items")
            for i, (placeholder, original) in enumerate(list(self.personal_info.items())[:3]):
                print(f"   • {original[:30]}... → {placeholder}")
            if len(self.personal_info) > 3:
                print(f"   • ... and {len(self.personal_info) - 3} more items")
            return result
        
        def ai_redline(self, redacted_text):
            print_progress("Sending to AI for legal review...", 2)
            print("   🤖 Analyzing document structure...")
            time.sleep(0.5)
            print("   📋 Comparing against institutional standards...")
            time.sleep(0.5)
            print("   ✏️  Generating redline suggestions...")
            result = super().ai_redline(redacted_text)
            if "[INSERT:" in result or "[DELETE:" in result:
                insert_count = result.count("[INSERT:")
                delete_count = result.count("[DELETE:")
                print(f"   ✓ AI suggested {insert_count} additions, {delete_count} deletions")
            else:
                print("   ✓ AI review complete - minimal changes needed")
            return result
        
        def create_tracked_docx(self, original_paragraphs, redlined_text, output_path):
            step = 3 if "temp" in output_path else 5
            action = "Creating tracked changes document..." if step == 3 else "Generating final Word document..."
            print_progress(action, step)
            time.sleep(0.3)
            super().create_tracked_docx(original_paragraphs, redlined_text, output_path)
            print(f"   ✓ Saved: {os.path.basename(output_path)}")
        
        def restore_personal_info(self, redlined_text):
            print_progress("Restoring personal information...", 4)
            time.sleep(0.3)
            result = super().restore_personal_info(redlined_text)
            print(f"   ✓ Restored {len(self.personal_info)} personal details")
            return result
    
    processor = VerboseNDAProcessor()
    
    try:
        start_time = time.time()
        output_file = processor.process_nda(input_file)
        end_time = time.time()
        
        print("=" * 60)
        print("🎉 REDLINING COMPLETE!")
        print("=" * 60)
        print(f"📄 Original File: {os.path.basename(input_file)}")
        print(f"📝 Redlined File: {os.path.basename(output_file)}")
        print(f"📁 Output Location: {os.path.dirname(output_file)}")
        print(f"⏱️  Processing Time: {end_time - start_time:.1f} seconds")
        print(f"🔍 Personal Items Protected: {len(processor.personal_info)}")
        print("=" * 60)
        print("✅ Ready for legal review!")
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ PROCESSING FAILED")
        print(f"Error: {e}")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
