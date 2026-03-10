#!/usr/bin/env python3
"""
Headless LibreOffice with Real Track Changes
"""

import os
import subprocess
import time
import uno
from com.sun.star.beans import PropertyValue

def create_headless_track_changes():
    """Use headless LibreOffice with real track changes"""
    
    # Start LibreOffice in headless mode
    print("🔄 Starting LibreOffice headless with track changes...")
    os.system("pkill -f libreoffice")
    time.sleep(2)
    
    os.system("libreoffice --headless --invisible --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' &")
    time.sleep(5)
    
    try:
        # Connect to headless LibreOffice
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
        original_path = "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx"
        original_url = uno.systemPathToFileUrl(os.path.abspath(original_path))
        
        doc = desktop.loadComponentFromURL(original_url, "_blank", 0, (create_property("Hidden", True),))
        
        print("✓ Document loaded in headless LibreOffice")
        
        # Enable track changes
        doc.RecordChanges = True
        print("✓ Track changes enabled in headless mode")
        
        # Make changes with track changes
        changes = [
            ("Informational Materials", "Confidential Information"),
            ("XXXXXXX", "Disclosing Party"),
            ("XXXXXX", "Receiving Party"),
        ]
        
        implemented_count = 0
        
        # Make replacements
        for find_text, replace_text in changes:
            try:
                replace_desc = doc.createReplaceDescriptor()
                replace_desc.setSearchString(find_text)
                replace_desc.setReplaceString(replace_text)
                
                replaced = doc.replaceAll(replace_desc)
                if replaced > 0:
                    implemented_count += 1
                    print(f"✓ Headless track change: {find_text} → {replace_text}")
            except Exception as e:
                print(f"❌ Failed: {e}")
        
        # Add new content
        text = doc.getText()
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        
        new_clauses = [
            "\n\nDEFINITION: For purposes of this Agreement, 'Confidential Information' means any non-public information relating to the Property.",
            "\n\nPURPOSE: The purpose of this disclosure is to evaluate a potential transaction involving the Property.",
            "\n\nOBLIGATIONS: The Receiving Party shall maintain all Confidential Information in strict confidence.",
            "\n\nEXCEPTIONS: This obligation does not apply to information that is publicly available.",
            "\n\nRETURN: Upon request, all Confidential Information shall be returned or destroyed.",
        ]
        
        for clause in new_clauses:
            text.insertString(cursor, clause, False)
            implemented_count += 1
            print(f"✓ Headless inserted clause with track changes")
        
        # Save with track changes
        output_path = "/home/cliff/redact/redline_project/REDLINE_Confidentiality Agreement_Sample_2_pre_redline_HEADLESS_TRACK_CHANGES.docx"
        output_url = uno.systemPathToFileUrl(os.path.abspath(output_path))
        
        save_props = (
            create_property("FilterName", "MS Word 2007 XML"),
            create_property("Overwrite", True)
        )
        doc.storeAsURL(output_url, save_props)
        
        print(f"✅ Created headless document with REAL track changes: {os.path.basename(output_path)}")
        print(f"🎯 Made {implemented_count} changes with track changes")
        
        # Close LibreOffice
        doc.close(True)
        desktop.terminate()
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        os.system("pkill -f libreoffice")

if __name__ == "__main__":
    create_headless_track_changes()
