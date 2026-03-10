#!/usr/bin/env python3
"""
LibreOffice Track Changes Test - Manual Changes
"""

import os
import time
import uno
from com.sun.star.beans import PropertyValue

print("🔄 LibreOffice Track Changes Test...")

# Test changes to make
test_changes = [
    {"type": "delete", "find": "highly sensitive, confidential and proprietary", "desc": "Delete excessive adjectives"},
    {"type": "replace", "find": "attorney's fees", "replace": "reasonable attorney's fees", "desc": "Add reasonable qualifier"},
    {"type": "add", "text": "This Agreement expires one (1) year from execution.", "desc": "Add term limit"}
]

# Start LibreOffice
print("🔄 Starting LibreOffice...")
os.system("pkill -f libreoffice")
time.sleep(2)
os.system("libreoffice --headless --invisible --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' &")
time.sleep(5)

try:
    # Connect
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_context)
    context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
    desktop = context.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", context)
    
    print("✓ Connected to LibreOffice")
    
    def create_property(name, value):
        prop = PropertyValue()
        prop.Name = name
        prop.Value = value
        return prop
    
    # Load document
    doc_path = "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx"
    doc_url = uno.systemPathToFileUrl(os.path.abspath(doc_path))
    doc = desktop.loadComponentFromURL(doc_url, "_blank", 0, (create_property("Hidden", True),))
    
    print("✓ Document loaded")
    
    # Enable track changes
    print("🔄 Enabling track changes...")
    try:
        doc.RecordChanges = True
        print(f"✓ Track changes enabled: {doc.RecordChanges}")
    except Exception as e:
        print(f"❌ Track changes failed: {e}")
    
    # Make test changes
    changes_made = 0
    
    for i, change in enumerate(test_changes, 1):
        print(f"🔄 Change {i}: {change['desc']}")
        
        try:
            if change['type'] == 'delete':
                replace_desc = doc.createReplaceDescriptor()
                replace_desc.setSearchString(change['find'])
                replace_desc.setReplaceString("")
                deleted = doc.replaceAll(replace_desc)
                if deleted > 0:
                    changes_made += 1
                    print(f"   ✓ Deleted: {change['find']}")
                else:
                    print(f"   ❌ Text not found: {change['find']}")
            
            elif change['type'] == 'replace':
                replace_desc = doc.createReplaceDescriptor()
                replace_desc.setSearchString(change['find'])
                replace_desc.setReplaceString(change['replace'])
                replaced = doc.replaceAll(replace_desc)
                if replaced > 0:
                    changes_made += 1
                    print(f"   ✓ Replaced: {change['find']} → {change['replace']}")
                else:
                    print(f"   ❌ Text not found: {change['find']}")
            
            elif change['type'] == 'add':
                text = doc.getText()
                cursor = text.createTextCursor()
                cursor.gotoEnd(False)
                text.insertString(cursor, f"\n\n{change['text']}", False)
                changes_made += 1
                print(f"   ✓ Added: {change['text']}")
        
        except Exception as e:
            print(f"   ❌ Change failed: {e}")
    
    # Save document
    output_path = "/home/cliff/redact/redline_project/libreTest/Track_Changes_Test.docx"
    output_url = uno.systemPathToFileUrl(os.path.abspath(output_path))
    
    save_props = (
        create_property("FilterName", "MS Word 2007 XML"),
        create_property("Overwrite", True)
    )
    doc.storeAsURL(output_url, save_props)
    doc.close(True)
    
    print(f"✅ Test complete: {changes_made} changes made")
    print(f"📝 Saved: {os.path.basename(output_path)}")

except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()

finally:
    try:
        desktop.terminate()
    except:
        pass
    os.system("pkill -f libreoffice")
    print("🔄 LibreOffice stopped")
