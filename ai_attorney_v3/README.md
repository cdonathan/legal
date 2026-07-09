# AI Attorney v3 — Installation Guide

## What This Does

Upload a legal document and the system will:
1. Redact personal information (never sent to AI)
2. Analyze against 1,807+ approved legal clauses from attorney-reviewed database
3. Suggest changes using ONLY approved clause language (AI never writes legal text)
4. Show you the document with formatting — you can edit directly in the browser
5. Let you select which changes to apply (checkboxes)
6. Generate redlined and clean versions with real Word track changes

---

## Installation

### Step 1: Install Python

**Windows:**
1. Go to https://www.python.org/downloads/
2. Download Python 3.12 (or any 3.10+)
3. Run the installer
4. **CHECK THE BOX** that says "Add python.exe to PATH"
5. Click "Install Now"

**Mac/Linux:**
```
# Mac
brew install python3

# Ubuntu/Debian
sudo apt install python3 python3-venv python3-pip
```

**Verify:**
```
python --version
```
You should see Python 3.10 or higher.

---

### Step 2: Install LibreOffice (Recommended)

LibreOffice enables real Word-compatible track changes and PDF output.

**Download:** https://www.libreoffice.org/download/

Without it, the app still works — you'll get visual redlines (strikethrough + green text) instead of real track changes that Word can accept/reject.

---

### Step 3: Unzip the Package

Extract `ai_attorney_v3.zip` to any folder, for example:
- Windows: `C:\ai_attorney_v3\`
- Mac/Linux: `~/ai_attorney_v3/`

---

### Step 4: Start the Application

**Windows:**
Double-click `start.bat`

**Mac/Linux:**
```
cd ai_attorney_v3
chmod +x start.sh
./start.sh
```

First run will take ~30 seconds to install dependencies. After that you'll see:
```
AI Attorney v3 — Clause Validation Cascade Engine
Starting on http://localhost:8083
```

---

### Step 5: Open in Browser

Go to: **http://localhost:8083**

---

## Using the Application

1. **Select document type** from the dropdown (NDA, PSA, Lease, etc.)
2. **Upload** a .docx, .pdf, .txt, or .mhtml file (drag-and-drop or click to browse)
3. **Wait ~15-45 seconds** for analysis (depends on number of clauses for that document type)
4. **Review** suggested changes on the left panel — click any suggestion to:
   - Expand context showing 150 words before and after
   - Highlight and scroll to that section in the document preview
5. **Edit** the document directly in the preview panel (right side)
   - Use the formatting toolbar for bold, italic, underline, strikethrough
   - Your edits are tracked and included when you apply
6. **Check/uncheck** suggestions to accept or reject individually
7. **Click "Apply Selected"** — generates documents with your approved changes
8. **Click "Download All Files"** — downloads Redlined DOCX, Clean DOCX, and Redlined PDF

---

## Output Files

| File | Description |
|------|-------------|
| `filename_Redlined_timestamp.docx` | Track changes visible — open in Word to accept/reject |
| `filename_Clean_timestamp.docx` | All changes already accepted — final version |
| `filename_Redlined_timestamp.pdf` | PDF version of redlined document |

---

## How It Works (Architecture)

1. **PII Redaction** — Personal info is replaced with tokens before AI sees the document
2. **AI Evaluation** — GPT-4o identifies deficiencies by referencing clause IDs (never writes legal text)
3. **Clause Validation Cascade** — Code verifies all replacement text comes from the clause database:
   - Tier 1: Exact substring match from approved clause
   - Tier 2: Fuzzy match (90%+ similarity) to actual clause text
   - Tier 3: Full clause replacement when section is clearly deficient
   - Tier 4: Flags for manual review if code can't resolve
4. **Rules Engine** — Deterministic patterns (e.g., "attorney's fees" → "reasonable attorney's fees") applied without AI
5. **Provenance Verification** — Final check confirms every replacement traces to the clause database

**Key guarantee:** No AI-generated legal language ever reaches the document. All replacements are attorney-approved.

---

## Stopping the Application

- Windows: Close the command window, or press `Ctrl+C`
- Mac/Linux: Press `Ctrl+C`

---

## Running Again Later

Just double-click `start.bat` (or `./start.sh`). Starts in a few seconds — no reinstall needed.

---

## What's in the Folder

| File | Purpose |
|------|---------|
| `start.bat` | Windows launcher |
| `start.sh` | Mac/Linux launcher |
| `app.py` | Main application server |
| `provisions.db` | 1,807 approved legal clauses |
| `redaction_whitelist.txt` | Words safe from redaction |
| `blacklists/` | Known company names for redaction |
| `static/index.html` | Web interface |
| `requirements.txt` | Python dependencies |
| `openai_api_key.txt` | OpenAI API key |

---

## Cost Per Document

~$0.50–$1.00 per document (uses GPT-4o for analysis, multiple batches for large clause sets).

---

## Supported Document Types

NDA, PSA (Purchase & Sale), Lease, Operating Agreement, Management Agreement, Joint Venture, Subscription Agreement, Guaranty, Earnest Money Agreement, Broker Agreement, Service Agreement

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "python is not recognized" | Reinstall Python, check "Add to PATH" |
| Browser says "can't connect" | Wait a few seconds for server to start |
| "Address already in use" | Another instance is running — close it |
| No changes suggested | Document may already be adequate for that type |
| Slow first time | Normal — installing packages takes ~30 seconds |
| "LibreOffice not found" | Install from libreoffice.org for track changes + PDF |
| Track changes not showing in Word | LibreOffice needed — without it you get visual redlines |
