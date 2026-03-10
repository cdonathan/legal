#!/usr/bin/env python3
"""
Simple LibreOffice Test - Get it working first
"""

import os
import sys
import time
import subprocess

def test_libreoffice_basic():
    """Test basic LibreOffice functionality"""
    print("🔄 Testing LibreOffice basic functionality...")
    
    # Test 1: Check if LibreOffice is installed
    print("\n1. Checking LibreOffice installation...")
    result = subprocess.run(['which', 'libreoffice'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   ✓ LibreOffice found at: {result.stdout.strip()}")
    else:
        print("   ❌ LibreOffice not found in PATH")
        return False
    
    # Test 2: Check LibreOffice version
    print("\n2. Checking LibreOffice version...")
    result = subprocess.run(['libreoffice', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   ✓ {result.stdout.strip()}")
    else:
        print("   ❌ Could not get LibreOffice version")
    
    # Test 3: Test headless mode
    print("\n3. Testing headless conversion...")
    test_input = "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx"
    test_output = "/home/cliff/redact/redline_project/test_conversion.txt"
    
    if os.path.exists(test_input):
        cmd = [
            'libreoffice', 
            '--headless', 
            '--convert-to', 'txt',
            '--outdir', '/home/cliff/redact/redline_project',
            test_input
        ]
        
        print(f"   Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✓ Headless conversion successful")
            print(f"   Output: {result.stdout}")
            
            # Check if output file was created
            expected_output = "/home/cliff/redact/redline_project/REDLINE_Confidentiality Agreement_Sample_2_pre_redline.txt"
            if os.path.exists(expected_output):
                print(f"   ✓ Output file created: {expected_output}")
                
                # Show first few lines
                with open(expected_output, 'r') as f:
                    lines = f.readlines()[:10]
                    print("   First 10 lines:")
                    for i, line in enumerate(lines, 1):
                        print(f"   {i:2d}: {line.strip()}")
                
                return True
            else:
                print(f"   ❌ Expected output file not found: {expected_output}")
        else:
            print(f"   ❌ Conversion failed: {result.stderr}")
    else:
        print(f"   ❌ Test input file not found: {test_input}")
    
    return False

def test_libreoffice_uno():
    """Test LibreOffice UNO API"""
    print("\n🔄 Testing LibreOffice UNO API...")
    
    try:
        import uno
        print("   ✓ UNO module imported successfully")
        
        # Start LibreOffice in server mode
        print("   Starting LibreOffice server...")
        cmd = [
            'libreoffice',
            '--headless',
            '--invisible',
            '--nodefault',
            '--nolockcheck',
            '--nologo',
            '--norestore',
            '--accept=socket,host=localhost,port=2002;urp;StarOffice.ServiceManager'
        ]
        
        # Start in background
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(5)  # Wait for startup
        
        # Try to connect
        local_context = uno.getComponentContext()
        resolver = local_context.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local_context)
        
        context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)
        
        print("   ✓ UNO connection successful!")
        
        # Clean up
        desktop.terminate()
        process.terminate()
        
        return True
        
    except ImportError:
        print("   ❌ UNO module not available - install python3-uno")
        return False
    except Exception as e:
        print(f"   ❌ UNO connection failed: {e}")
        # Clean up
        try:
            process.terminate()
        except:
            pass
        return False

def main():
    print("LibreOffice Diagnostic Test")
    print("=" * 50)
    
    basic_works = test_libreoffice_basic()
    uno_works = test_libreoffice_uno()
    
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"Basic LibreOffice: {'✓ WORKING' if basic_works else '❌ FAILED'}")
    print(f"UNO API: {'✓ WORKING' if uno_works else '❌ FAILED'}")
    
    if basic_works and not uno_works:
        print("\nRECOMMENDATION: Use basic LibreOffice commands instead of UNO API")
    elif not basic_works:
        print("\nRECOMMENDATION: Fix LibreOffice installation first")
    else:
        print("\nRECOMMENDATION: LibreOffice is ready to use!")

if __name__ == "__main__":
    main()
