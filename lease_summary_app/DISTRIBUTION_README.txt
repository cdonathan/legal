============================================================
  SeedJura Agreement Summary Tool
  Distribution Package
============================================================

REQUIREMENTS
------------
- Windows 10/11 (64-bit)
- Internet connection (for OpenAI API calls)
- OpenAI API key

SETUP (First Time)
------------------
1. Unzip the SeedJura folder to any location (e.g., C:\SeedJura\)

2. Place your OpenAI API key in ONE of these locations:
   - C:\seedJura\openai_api_key.txt  (just the key, nothing else)
   - Or set environment variable: OPENAI_API_KEY=sk-...

3. Place the lease summary template file:
   - C:\seedJura\SeedJura_Lease_Summary_FORM.docx
   - (Or place it next to SeedJura.exe)

RUNNING
-------
1. Double-click SeedJura.exe
2. Your browser will open to http://localhost:8083
3. Select agreement type, set output folder, upload a file
4. Results are automatically saved to your configured output folder

OUTPUT FILES (per document)
---------------------------
- {name}_summary_{date}.docx    - Populated summary document
- {name}_GlobalFormVars.xml     - Structured data in XML format
- {name}_data.json              - Full extraction data + audit trail

NOTES
-----
- Keep the console window open while using the app
- Press Ctrl+C in the console to stop the server
- The output folder setting is remembered between sessions
- Scanned PDFs take 2-3 minutes (OCR processing)
- Digital PDFs take ~30 seconds

BUILDING FROM SOURCE
--------------------
If you need to rebuild the executable:

1. Install Python 3.10+ (python.org)
2. Open Command Prompt in the lease_summary_app folder
3. Run: BUILD.bat

This installs dependencies and creates dist\SeedJura\

TROUBLESHOOTING
---------------
- "No OpenAI API key found" -> Place key in C:\seedJura\openai_api_key.txt
- "Template not found" -> Place .docx template in C:\seedJura\
- Permission denied on output -> Close the file in Word first
- Port 8083 in use -> The app will try 8084-8099 automatically

============================================================
