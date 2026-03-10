#!/usr/bin/env python3
"""
Test Visible Track Changes in LibreOffice
"""

import os
import time
import uno
from com.sun.star.beans import PropertyValue

print("🔄 Testing VISIBLE track changes...")

# Start LibreOffice
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
    
    # Enable track changes BEFORE making changes
    doc.RecordChanges = True
    print(f"✓ Track changes enabled: {doc.RecordChanges}")
    
    # Method 1: Try using cursor with track changes
    print("🔄 Method 1: Using text cursor with track changes...")
    try:
        text = doc.getText()
        cursor = text.createTextCursor()
        
        # Find specific text to replace
        search = doc.createSearchDescriptor()
        search.setSearchString("attorney's fees")
        found = doc.findFirst(search)
        
        if found:
            # Select the found text
            cursor.gotoRange(found, False)
            cursor.gotoRange(found.getEnd(), True)  # Select the range
            
            # Replace with tracked change
            cursor.setString("reasonable attorney's fees")
            print("   ✓ Replaced 'attorney's fees' with cursor method")
        else:
            print("   ❌ Text 'attorney's fees' not found")
    
    except Exception as e:
        print(f"   ❌ Cursor method failed: {e}")
    
    # Method 2: Try using redline API directly
    print("🔄 Method 2: Using redline API...")
    try:
        # Get redlines (track changes)
        redlines = doc.getRedlines()
        print(f"   📊 Current redlines count: {redlines.getCount()}")
        
        # Make a simple insertion that should create a redline
        text = doc.getText()
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        
        # Insert text that should be tracked
        cursor.setString("\n\nTEST TRACKED INSERTION: This text should appear as a tracked change.")
        
        # Check redlines again
        redlines_after = doc.getRedlines()
        print(f"   📊 Redlines after insertion: {redlines_after.getCount()}")
        
    except Exception as e:
        print(f"   ❌ Redline API method failed: {e}")
    
    # Save document
    output_path = "/home/cliff/redact/redline_project/libreTest/Visible_Track_Changes_Test.docx"
    output_url = uno.systemPathToFileUrl(os.path.abspath(output_path))
    
    save_props = (
        create_property("FilterName", "MS Word 2007 XML"),
        create_property("Overwrite", True)
    )
    doc.storeAsURL(output_url, save_props)
    doc.close(True)
    
    print(f"✅ Saved: {os.path.basename(output_path)}")
    print("📋 Open this file in Word to check if track changes are visible")

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
