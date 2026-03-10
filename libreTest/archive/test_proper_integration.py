#!/usr/bin/env python3
"""
Fix Attorney Integration - Proper Document Integration
"""

import os
import time
import uno
from com.sun.star.beans import PropertyValue

print("🔄 Testing proper attorney integration...")

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
    
    # Enable track changes
    doc.RecordChanges = True
    print(f"✓ Track changes enabled: {doc.RecordChanges}")
    
    # Test 1: Insert exclusions RIGHT AFTER "Informational Materials" definition
    print("🔄 Test 1: Insert exclusions after definition...")
    try:
        # Find where to insert exclusions (after first mention of Informational Materials)
        search = doc.createSearchDescriptor()
        search.setSearchString("Informational Materials on the property such as financial information.")
        found = doc.findFirst(search)
        
        if found:
            text = doc.getText()
            cursor = text.createTextCursor()
            cursor.gotoRange(found.getEnd(), False)  # Go to end of found text
            
            # Insert exclusions right after
            exclusions = " However, Informational Materials does not include: (i) information already in Potential Purchaser's possession; (ii) information publicly available; (iii) information independently developed; (iv) information received from third parties without confidentiality obligations."
            cursor.setString(exclusions)
            print("   ✓ Inserted exclusions after definition")
        else:
            print("   ❌ Definition text not found")
    except Exception as e:
        print(f"   ❌ Exclusions insertion failed: {e}")
    
    # Test 2: Add term limitation to Section 6 (governance section)
    print("🔄 Test 2: Add term limit to governance section...")
    try:
        search = doc.createSearchDescriptor()
        search.setSearchString("This Agreement shall be governed and construed in accordance with the laws of the State of Ohio.")
        found = doc.findFirst(search)
        
        if found:
            text = doc.getText()
            cursor = text.createTextCursor()
            cursor.gotoRange(found.getEnd(), False)
            
            # Add term limitation right after governance
            term_limit = " This Agreement shall expire one (1) year from the date of execution."
            cursor.setString(term_limit)
            print("   ✓ Added term limit to governance section")
        else:
            print("   ❌ Governance text not found")
    except Exception as e:
        print(f"   ❌ Term limit addition failed: {e}")
    
    # Test 3: Modify signature section for electronic signatures
    print("🔄 Test 3: Add electronic signature provision...")
    try:
        search = doc.createSearchDescriptor()
        search.setSearchString("Your signature below constitutes Agreement with the foregoing.")
        found = doc.findFirst(search)
        
        if found:
            text = doc.getText()
            cursor = text.createTextCursor()
            cursor.gotoRange(found, False)
            cursor.gotoRange(found.getEnd(), True)  # Select the text
            
            # Replace with enhanced signature language
            enhanced_sig = "Your signature below (including electronic signatures) constitutes Agreement with the foregoing. This Agreement may be executed in counterparts."
            cursor.setString(enhanced_sig)
            print("   ✓ Enhanced signature section")
        else:
            print("   ❌ Signature text not found")
    except Exception as e:
        print(f"   ❌ Signature enhancement failed: {e}")
    
    # Save document
    output_path = "/home/cliff/redact/redline_project/libreTest/Properly_Integrated_Changes.docx"
    output_url = uno.systemPathToFileUrl(os.path.abspath(output_path))
    
    save_props = (
        create_property("FilterName", "MS Word 2007 XML"),
        create_property("Overwrite", True)
    )
    doc.storeAsURL(output_url, save_props)
    doc.close(True)
    
    print(f"✅ Saved: {os.path.basename(output_path)}")
    print("📋 Changes should be properly integrated into document structure")

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
