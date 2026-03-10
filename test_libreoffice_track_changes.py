#!/usr/bin/env python3
"""
LibreOffice Track Changes Test
Manual change instructions to test all change types
"""

import os
import time
import uno
from com.sun.star.beans import PropertyValue

def test_libreoffice_track_changes():
    """Test all types of track changes in LibreOffice"""
    
    print("🔄 Starting LibreOffice Track Changes Test...")
    
    # Manual test instructions - no AI
    test_changes = [
        {
            "type": "delete",
            "find_text": "highly sensitive, confidential and proprietary",
            "description": "Delete excessive adjectives"
        },
        {
            "type": "replace",
            "find_text": "attorney's fees",
            "replace_with": "reasonable attorney's fees",
            "description": "Add reasonable qualifier"
        },
        {
            "type": "add_text",
            "location": "after_paragraph_2",
            "add_text": "Notwithstanding the above, Confidential Information does not include information that is publicly available.",
            "description": "Add exclusions clause"
        },
        {
            "type": "bold",
            "find_text": "CONFIDENTIALITY AGREEMENT",
            "description": "Make title bold"
        },
        {
            "type": "insert_at_end",
            "add_text": "This Agreement shall expire one (1) year from the Effective Date.",
            "description": "Add term limitation"
        }
    ]
    
    print("🔄 Testing LibreOffice Track Changes...")
    
    # Kill any existing LibreOffice
    os.system("pkill -f libreoffice")
    time.sleep(2)
    
    # Start LibreOffice
    os.system("libreoffice --headless --invisible --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' &")
    time.sleep(5)
    
    try:
        # Connect to LibreOffice
        local_context = uno.getComponentContext()
        resolver = local_context.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local_context)
        
        context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)
        
        def create_property(name, value):
            prop = PropertyValue()
            prop.Name = name
            prop.Value = value
            return prop
        
        # Load Sample 2
        original_path = "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx"
        original_url = uno.systemPathToFileUrl(os.path.abspath(original_path))
        doc = desktop.loadComponentFromURL(original_url, "_blank", 0, (create_property("Hidden", True),))
        
        print("   ✓ Document loaded")
        
        # Try different methods to enable track changes
        print("   🔄 Testing track changes methods...")
        
        try:
            doc.RecordChanges = True
            print("   ✓ Method 1: doc.RecordChanges = True")
        except Exception as e:
            print(f"   ❌ Method 1 failed: {e}")
        
        try:
            doc.recordChanges(True)
            print("   ✓ Method 2: doc.recordChanges(True)")
        except Exception as e:
            print(f"   ❌ Method 2 failed: {e}")
        
        # Check if track changes is enabled
        try:
            is_recording = doc.RecordChanges
            print(f"   📊 Track changes status: {is_recording}")
        except:
            print("   ❌ Cannot check track changes status")
        
        # Test each change type
        changes_made = 0
        
        for i, change in enumerate(test_changes, 1):
            try:
                print(f"   🔄 Testing change {i}: {change['type']}")
                
                if change['type'] == 'delete':
                    # Test deletion
                    find_text = change['find_text']
                    replace_desc = doc.createReplaceDescriptor()
                    replace_desc.setSearchString(find_text)
                    replace_desc.setReplaceString("")  # Delete by replacing with empty
                    
                    deleted = doc.replaceAll(replace_desc)
                    if deleted > 0:
                        changes_made += 1
                        print(f"   ✓ Deleted: {find_text}")
                    else:
                        print(f"   ❌ Could not find text to delete: {find_text}")
                
                elif change['type'] == 'replace':
                    # Test replacement
                    find_text = change['find_text']
                    replace_text = change['replace_with']
                    
                    replace_desc = doc.createReplaceDescriptor()
                    replace_desc.setSearchString(find_text)
                    replace_desc.setReplaceString(replace_text)
                    
                    replaced = doc.replaceAll(replace_desc)
                    if replaced > 0:
                        changes_made += 1
                        print(f"   ✓ Replaced: {find_text} → {replace_text}")
                    else:
                        print(f"   ❌ Could not find text to replace: {find_text}")
                
                elif change['type'] == 'add_text' or change['type'] == 'insert_at_end':
                    # Test text insertion
                    add_text = change['add_text']
                    
                    text = doc.getText()
                    cursor = text.createTextCursor()
                    cursor.gotoEnd(False)
                    text.insertString(cursor, f"\n\n{add_text}", False)
                    
                    changes_made += 1
                    print(f"   ✓ Added text: {add_text[:50]}...")
                
                elif change['type'] == 'bold':
                    # Test formatting (this is more complex in LibreOffice)
                    print(f"   ⚠️ Bold formatting test skipped (complex in headless mode)")
                
            except Exception as e:
                print(f"   ❌ Change {i} failed: {e}")
        
        # Save the test document
        output_path = "/home/cliff/redact/redline_project/libreTest/Sample2_LibreOffice_Track_Changes_Test.docx"
        output_url = uno.systemPathToFileUrl(os.path.abspath(output_path))
        
        save_props = (
            create_property("FilterName", "MS Word 2007 XML"),
            create_property("Overwrite", True)
        )
        doc.storeAsURL(output_url, save_props)
        doc.close(True)
        
        print(f"   ✅ Test complete: {changes_made} changes made")
        print(f"   📝 Saved: {os.path.basename(output_path)}")
        
        return output_path
        
    except Exception as e:
        print(f"   ❌ LibreOffice test error: {e}")
        return None
    
    finally:
        try:
            desktop.terminate()
        except:
            pass
        os.system("pkill -f libreoffice")

if __name__ == "__main__":
    test_libreoffice_track_changes()
