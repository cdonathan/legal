"""
SeedJura Agreement Summary - Launcher
=======================================
Entry point for the packaged executable.
Starts the FastAPI server and opens the browser.
"""

import os
import sys
import time
import threading
import webbrowser
import socket

# When running as a PyInstaller bundle, adjust paths
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BASE_DIR = sys._MEIPASS
    # Add the bundle dir to path so imports work
    sys.path.insert(0, BASE_DIR)
    os.chdir(BASE_DIR)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, BASE_DIR)
    sys.path.insert(0, os.path.dirname(BASE_DIR))


def find_free_port(start=8083, end=8099):
    """Find a free port in the given range."""
    for port in range(start, end):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', port))
            s.close()
            return port
        except OSError:
            continue
    return start


def open_browser(port, delay=2.0):
    """Open browser after a short delay to let the server start."""
    time.sleep(delay)
    url = f"http://localhost:{port}"
    print(f"\n  Opening browser: {url}")
    print(f"  (If browser doesn't open, navigate to {url} manually)\n")
    webbrowser.open(url)


def main():
    print("=" * 60)
    print("  SeedJura Agreement Summary Tool")
    print("=" * 60)
    print()

    # Auto-deploy template and API key to C:\seedJura\ on first run
    _setup_files()

    # Check dependencies and warn the user
    _check_dependencies()

    port = find_free_port()
    print(f"  Starting server on port {port}...")
    print(f"  Press Ctrl+C to stop.")
    print()

    # Open browser in background thread
    browser_thread = threading.Thread(target=open_browser, args=(port,), daemon=True)
    browser_thread.start()

    # Start uvicorn
    import uvicorn
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        reload=False,
    )


def _check_dependencies():
    """Check for optional dependencies and warn if missing."""
    # Check OCR availability (needed for scanned PDFs)
    try:
        from lease_summary_tool import is_ocr_available
        if is_ocr_available():
            print("  [OK] OCR available (scanned PDFs supported)")
        else:
            print("  [!] OCR NOT available - scanned PDFs cannot be processed.")
            print("      Digital (text-based) PDFs will still work fine.")
            print("      To enable OCR, install Tesseract or use the bundled version.")
    except Exception:
        pass

    # Check API key
    try:
        from lease_summary_tool import API_KEY_FILE
        import os as _os
        has_key = (_os.path.exists(API_KEY_FILE) or
                   _os.environ.get("OPENAI_API_KEY"))
        if has_key:
            print("  [OK] OpenAI API key found")
        else:
            print("  [!] No OpenAI API key found.")
            print(f"      Place your key in: {API_KEY_FILE}")
    except Exception:
        pass

    print()


def _setup_files():
    """Copy template and API key to C:\\seedJura\\ if not already there."""
    import shutil

    # Determine target dir based on OS
    if os.name == "nt" or sys.platform == "win32":
        target_dir = r"C:\seedJura"
    else:
        target_dir = "/mnt/c/seedJura"

    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as e:
        print(f"  Warning: Could not create {target_dir}: {e}")
        return

    # Template
    template_name = "SeedJura_Lease_Summary_FORM.docx"
    target_template = os.path.join(target_dir, template_name)
    if not os.path.exists(target_template):
        # Look for template next to this script or in BASE_DIR
        search_paths = [
            BASE_DIR,
            os.path.dirname(os.path.abspath(__file__)),
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ]
        for search in search_paths:
            source = os.path.join(search, template_name)
            if os.path.exists(source):
                shutil.copy2(source, target_template)
                print(f"  Installed template: {target_template}")
                break
        else:
            print(f"  Warning: Template '{template_name}' not found to install.")

    # API key
    key_name = "openai_api_key.txt"
    target_key = os.path.join(target_dir, key_name)
    if not os.path.exists(target_key):
        search_paths = [
            BASE_DIR,
            os.path.dirname(os.path.abspath(__file__)),
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ]
        for search in search_paths:
            source = os.path.join(search, key_name)
            if os.path.exists(source):
                shutil.copy2(source, target_key)
                print(f"  Installed API key: {target_key}")
                break

    # Output folder
    output_dir = os.path.join(target_dir, "Summary_Output")
    os.makedirs(output_dir, exist_ok=True)
    print(f"  Output folder: {output_dir}")


if __name__ == "__main__":
    main()
