#!/usr/bin/env python3
"""
Simple LibreOffice Test
"""

print("🔄 Starting simple LibreOffice test...")

try:
    import uno
    print("✓ UNO import successful")
except Exception as e:
    print(f"❌ UNO import failed: {e}")
    exit(1)

import os
import time

print("🔄 Testing LibreOffice connection...")

# Start LibreOffice
os.system("pkill -f libreoffice")
time.sleep(2)
os.system("libreoffice --headless --invisible --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' &")
time.sleep(5)

try:
    local_context = uno.getComponentContext()
    print("✓ Got UNO context")
    
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_context)
    print("✓ Created resolver")
    
    context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
    print("✓ Connected to LibreOffice")
    
    desktop = context.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", context)
    print("✓ Got desktop")
    
    print("✅ LibreOffice connection successful!")
    
except Exception as e:
    print(f"❌ LibreOffice connection failed: {e}")

finally:
    os.system("pkill -f libreoffice")
    print("🔄 Cleaned up LibreOffice processes")

print("✅ Simple test complete")
