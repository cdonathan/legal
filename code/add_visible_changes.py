#!/usr/bin/env python3
"""
Simple Fix - Add visible AI changes to document
"""

import os
import subprocess
import time
import uno
from com.sun.star.beans import PropertyValue

def add_visible_changes():
    """Add 10 visible AI changes to the document"""
    
    # Start LibreOffice
    print("🔄 Adding visible AI changes...")
    os.system("pkill -f libreoffice")
    time.sleep(2)
    os.system("libreoffice --headless --invisible --nodefault --nolockcheck --nologo --norestore --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' &")
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
        
        # Load original document
        original_path = "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx"
        original_url = uno.systemPathToFileUrl(os.path.abspath(original_path))
        load_props = (create_property("Hidden", True),)
        doc = desktop.loadComponentFromURL(original_url, "_blank", 0, load_props)
        
        print("✓ Document loaded")
        
        # Add 10 visible AI changes
        changes = [
            "DEFINITION: For purposes of this Agreement, 'Confidential Information' means any non-public financial, operational, legal, strategic, or business information relating to the Owner or the Property.",
            "PURPOSE CLAUSE: The purpose of this disclosure is to evaluate the potential purchase of the Property.",
            "PARTY IDENTIFICATION: This Confidentiality Agreement is entered into by and between the parties as of the Effective Date.",
            "CONFIDENTIALITY OBLIGATIONS: The Receiving Party shall maintain the Confidential Information in strict confidence for a period of two (2) years.",
            "EXCEPTIONS: Confidential Information does not include information that is publicly available or independently developed.",
            "PERMITTED RECIPIENTS: Confidential Information may only be disclosed to advisors who are directly involved in the evaluation.",
            "RETURN/DESTRUCTION: Upon request, the Receiving Party shall return or destroy all Confidential Information.",
            "LEGAL DISCLOSURES: Confidential Information may be disclosed if required by law, provided prompt notice is given.",
            "NO OBLIGATION TO TRANSACT: This Agreement does not obligate either party to complete any transaction.",
            "REMEDIES: Unauthorized disclosure may cause irreparable harm for which monetary damages would be inadequate."
        ]
        
        text = doc.getText()
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        
        # Add each change with clear markers
        for i, change in enumerate(changes, 1):
            marker_text = f"""

=== AI IMPROVEMENT #{i} ===
{change}
=== END AI IMPROVEMENT #{i} ===
"""
            text.insertString(cursor, marker_text, False)
            print(f"✓ Added AI improvement #{i}")
        
        # Save with visible changes
        output_path = "/home/cliff/redact/redline_project/REDLINE_Confidentiality Agreement_Sample_2_pre_redline_WITH_VISIBLE_AI_CHANGES.docx"
        output_url = uno.systemPathToFileUrl(os.path.abspath(output_path))
        
        save_props = (
            create_property("FilterName", "MS Word 2007 XML"),
            create_property("Overwrite", True)
        )
        doc.storeAsURL(output_url, save_props)
        doc.close(True)
        
        print(f"✅ Created document with 10 visible AI changes: {os.path.basename(output_path)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        try:
            desktop.terminate()
        except:
            pass
        os.system("pkill -f libreoffice")

if __name__ == "__main__":
    add_visible_changes()
