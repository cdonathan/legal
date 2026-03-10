#!/usr/bin/env python3
"""
Quick Fix - Add visible markers to LibreOffice changes
"""

import os
import sys
import subprocess
import json
import re
import openai
import time
import uno
from com.sun.star.beans import PropertyValue

def fix_libreoffice_visibility():
    """Add visible markers to make changes obvious"""
    
    # Get the latest Call4 implementation
    implementation_file = "/home/cliff/redact/redline_project/REDLINE_Confidentiality Agreement_Sample_2_pre_redline_Call4_Implementation.md"
    
    with open(implementation_file, 'r') as f:
        content = f.read()
    
    # Extract JSON
    json_start = content.find('[')
    json_end = content.rfind(']') + 1
    if json_start >= 0 and json_end > json_start:
        json_str = content[json_start:json_end]
        instructions = json.loads(json_str)
    else:
        print("No instructions found")
        return
    
    # Start LibreOffice
    print("🔄 Starting LibreOffice with visible markers...")
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
        
        # Add visible markers for each change
        implemented_count = 0
        
        for i, inst in enumerate(instructions):
            try:
                change_type = inst.get('change_type', '')
                
                if 'insert' in change_type:
                    insert_text = inst.get('insert_text', '')
                    
                    # Create highly visible marker
                    marker_text = f"""

=== AI CHANGE #{i+1}: {change_type.upper()} ===
{insert_text}
=== END AI CHANGE #{i+1} ===

"""
                    
                    text = doc.getText()
                    cursor = text.createTextCursor()
                    cursor.gotoEnd(False)
                    text.insertString(cursor, marker_text, False)
                    
                    implemented_count += 1
                    print(f"✓ Added visible change #{i+1}: {change_type}")
                
                elif 'replace' in change_type:
                    find_text = inst.get('find_text', '')
                    replace_text = inst.get('replace_with', '')
                    
                    if find_text:
                        # Create visible replacement marker
                        marked_replace = f"[REPLACED BY AI: {find_text}] → {replace_text}"
                        
                        replace_desc = doc.createReplaceDescriptor()
                        replace_desc.setSearchString(find_text)
                        replace_desc.setReplaceString(marked_replace)
                        
                        replaced = doc.replaceAll(replace_desc)
                        if replaced > 0:
                            implemented_count += 1
                            print(f"✓ Replaced with visible marker: {find_text}")
            
            except Exception as e:
                print(f"❌ Failed change #{i+1}: {e}")
        
        # Save with visible markers
        output_path = "/home/cliff/redact/redline_project/REDLINE_Confidentiality Agreement_Sample_2_pre_redline_VISIBLE_CHANGES.docx"
        output_url = uno.systemPathToFileUrl(os.path.abspath(output_path))
        
        save_props = (
            create_property("FilterName", "MS Word 2007 XML"),
            create_property("Overwrite", True)
        )
        doc.storeAsURL(output_url, save_props)
        doc.close(True)
        
        print(f"✅ Created document with visible changes: {os.path.basename(output_path)}")
        print(f"🎯 Added {implemented_count}/{len(instructions)} visible changes")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        try:
            desktop.terminate()
        except:
            pass
        os.system("pkill -f libreoffice")

if __name__ == "__main__":
    fix_libreoffice_visibility()
