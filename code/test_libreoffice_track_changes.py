#!/usr/bin/env python3
"""
LibreOffice Track Changes Test
Open document, enable track changes, make edits, save as .docx
"""

import uno
import os
import sys
import time
from com.sun.star.beans import PropertyValue

def create_property_value(name, value):
    """Create a PropertyValue for LibreOffice"""
    prop = PropertyValue()
    prop.Name = name
    prop.Value = value
    return prop

def test_libreoffice_track_changes():
    """Test LibreOffice track changes functionality"""
    
    # Input and output files
    input_file = "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Conf_Agr_Sample1-pre-redline.docx"
    output_file = "/home/cliff/redact/redline_project/LibreOffice_Track_Changes_Test.docx"
    
    print("🔄 Starting LibreOffice track changes test...")
    
    try:
        # Start LibreOffice in headless mode
        os.system("libreoffice --headless --invisible --nodefault --nolockcheck --nologo --norestore --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' &")
        time.sleep(3)  # Wait for LibreOffice to start
        
        # Connect to LibreOffice
        local_context = uno.getComponentContext()
        resolver = local_context.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local_context)
        
        context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)
        
        print("✓ Connected to LibreOffice")
        
        # Convert file path to URL
        input_url = uno.systemPathToFileUrl(os.path.abspath(input_file))
        
        # Load document
        load_props = (create_property_value("Hidden", True),)
        doc = desktop.loadComponentFromURL(input_url, "_blank", 0, load_props)
        
        print("✓ Document loaded")
        
        # Enable track changes
        doc.recordChanges(True)
        print("✓ Track changes enabled")
        
        # Get text cursor
        text = doc.getText()
        cursor = text.createTextCursor()
        
        # Make some changes
        print("Making test changes...")
        
        # Go to end of first paragraph
        cursor.gotoStart(False)
        cursor.gotoEndOfParagraph(False)
        
        # Insert new text (this should be tracked)
        text.insertString(cursor, " [LIBREOFFICE INSERTION: This text was added with track changes enabled]", False)
        
        # Find and replace some text
        replace_desc = doc.createReplaceDescriptor()
        replace_desc.setSearchString("Agreement")
        replace_desc.setReplaceString("CONTRACT")
        doc.replaceAll(replace_desc)
        
        print("✓ Changes made with track changes enabled")
        
        # Save as .docx
        output_url = uno.systemPathToFileUrl(os.path.abspath(output_file))
        save_props = (
            create_property_value("FilterName", "MS Word 2007 XML"),
            create_property_value("Overwrite", True)
        )
        
        doc.storeAsURL(output_url, save_props)
        print(f"✓ Saved as: {os.path.basename(output_file)}")
        
        # Close document
        doc.close(True)
        
        # Shutdown LibreOffice
        desktop.terminate()
        
        print("✅ LibreOffice track changes test complete!")
        print(f"📄 Test file: {output_file}")
        print("🔍 Open this file in Microsoft Word to see if track changes are preserved")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Error: {e}")
        # Try to kill LibreOffice process
        os.system("pkill -f libreoffice")
        return None

if __name__ == "__main__":
    test_libreoffice_track_changes()
