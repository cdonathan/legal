# SeedJura Agreement Summary App

## What It Does

The SeedJura Agreement Summary App takes legal agreements (PDFs or Word documents), reads them using AI, and produces a structured summary document. It extracts every key term — parties, dates, rent, options, obligations — directly from the source text and populates a formatted Word template.

The app handles two modes:

- **Single File** — Upload one lease and get a complete summary.
- **Multi-File (Folder)** — Point it at a folder containing an original lease plus all its amendments, and get a single merged summary showing the current state of every provision, with historical changes annotated.

All output is saved automatically to a configured folder in three formats: Word (.docx), XML (GlobalFormVars), and JSON (audit data).

---

## How It Works

### Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  1. INGEST          Extract text from PDF or DOCX               │
│                     (OCR for scanned documents)                  │
├─────────────────────────────────────────────────────────────────┤
│  2. PII SCAN        Detect sensitive data (names, SSNs, etc.)   │
│                     Log findings, pass full text to AI           │
├─────────────────────────────────────────────────────────────────┤
│  3. AI EXTRACT      GPT-4o reads the document and extracts      │
│                     118 fields with verbatim source text         │
├─────────────────────────────────────────────────────────────────┤
│  4. VERIFY          Code checks AI output against source text   │
│                     Fuzzy matching handles OCR errors            │
├─────────────────────────────────────────────────────────────────┤
│  5. RETRY           Targeted second AI pass for any fields      │
│                     that were missed or flagged as suspect       │
├─────────────────────────────────────────────────────────────────┤
│  6. OUTPUT          Populate Word template + generate XML/JSON   │
│                     Auto-save to configured output folder        │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-File Mode (Additional Steps)

When processing a folder:

1. All documents in the folder are ingested
2. Each document is classified (lease, amendment, omnibus, termination, etc.)
3. Each document is independently analyzed by AI
4. Documents are sorted chronologically by execution date
5. Fields are merged: the latest document's value becomes "current," earlier values become history
6. Output shows the current state with change history annotations

---

## Key Features

### Verbatim Extraction
The AI copies exact language from the document. It does not summarize or paraphrase. Every value in the output can be traced back to a specific sentence in the source.

### Source Verification
After the AI extracts fields, code verifies each value actually exists in the source text using:
- Anchor phrase matching (AI provides the first 8 words of where it found the text)
- Fuzzy string matching (handles OCR errors, formatting differences)
- Keyword pattern fallback (configurable regex patterns per field)

### Date Normalization
Date fields return both:
- A normalized `mm/dd/yyyy` value for systems
- The full verbatim language for legal context (including conditional dates)

### Handwritten Date Correction
Scanned leases often have handwritten dates that OCR garbles (e.g., "Bias" instead of "1st"). The app detects and corrects common OCR misreads before AI processing.

### Amendment Awareness
The AI understands document types. Amendments only report fields they actually modify. The merge engine tracks what changed and when.

### Historical Change Tracking (Multi-File)
When a provision changes across amendments, the output shows:

```
[Current - SEVENTH AMENDMENT (02/01/2019)]:
Lease term extended through January 31, 2024.

[Prior - FIFTH AMENDMENT (07/30/2015)]:
Lease term extended through January 31, 2020.

[Prior - LEASE AGREEMENT (03/15/2003)]:
Initial term of sixty (60) months commencing April 1, 2003.
```

### Agreement Type System
The app uses a pluggable configuration system. Each agreement type (lease, NDA, purchase agreement, etc.) is defined by a JSON config file specifying:
- Which fields to extract
- AI prompt rules
- Verification patterns
- Template path
- UI section layout

New agreement types can be added by creating a config file — no code changes needed.

---

## Architecture

```
lease_summary_app/
├── app.py                          FastAPI web server + API endpoints
├── engine.py                       Generic AI extraction pipeline
├── multi_file.py                   Multi-document merge engine
├── xml_export.py                   GlobalFormVars XML output
├── launcher.py                     Entry point (starts server + browser)
├── agreement_types/
│   ├── __init__.py                 Type registry + auto-detection
│   ├── base.py                     AgreementType data model
│   └── lease/
│       ├── config.json             All lease-specific fields, prompts, rules
│       └── field_anchors.json      Keyword patterns for source verification
├── static/
│   └── index.html                  Web frontend (vanilla JS)
├── SeedJura_Lease_Summary_FORM.docx  Word template
├── requirements.txt                Python dependencies
├── BUILD.bat                       Windows executable build script
└── build_exe.py                    PyInstaller configuration
```

**Supporting files (parent directory):**
- `lease_summary_tool.py` — Core utility functions (ingestion, OCR, text processing)
- `redactor.py` — PII detection patterns
- `openai_api_key.txt` — API key

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/agreement-types` | List available agreement types |
| GET | `/api/settings` | Get user settings (output folder) |
| PUT | `/api/settings` | Update output folder |
| GET | `/api/browse-folders?path=C:\` | List subdirectories for folder picker |
| POST | `/api/upload` | Single-file processing |
| POST | `/api/upload-folder` | Multi-file folder processing |
| GET | `/api/preview/{job_id}` | Get structured preview of results |
| GET | `/api/download/{job_id}` | Download generated DOCX |
| GET | `/api/download-xml/{job_id}` | Download GlobalFormVars XML |

---

## Output Files

For each processed document or folder:

| File | Format | Contents |
|------|--------|----------|
| `{name}_summary_{date}.docx` | Word | Populated summary template |
| `{name}_GlobalFormVars.xml` | XML | Structured field data with normalized dates |
| `{name}_data.json` | JSON | Full extraction data, audit trail, PII counts |

### XML Format

The XML uses the `<GlobalFormVars>` schema compatible with the existing form system:

```xml
<?xml version="1.0" encoding="utf-8"?>
<GlobalFormVars>
  <Tenant_Name>ALDO GROUP INC.</Tenant_Name>
  <Date_Commencement normalized_date="04/01/2003">
    The term shall commence on the 1st day of April, 2003
  </Date_Commencement>
  <Rent_BaseRent_Monthly>$4,500.00</Rent_BaseRent_Monthly>
  ...
</GlobalFormVars>
```

Date fields include a `normalized_date` attribute with the `mm/dd/yyyy` value.

---

## Fields Extracted (Lease Agreement)

118 fields organized into sections:

| Section | Fields | Examples |
|---------|--------|----------|
| Summary Info | 3 | Preparer, Date, Purpose |
| Property & Owner | 9 | Property name, address, owner entity |
| Tenant | 11 | Name, entity type, DBA, address, contact |
| Premises & Term | 11 | Unit, sq ft, commencement, expiration, renewals |
| Base Rent | 6 | Amount, PSF, monthly, annual increase |
| Rent Abatement | 6 | Start, end, duration, qualifiers |
| Additional Rent | 5 | Percentage share, TI allowance |
| Use & Parking | 9 | Permitted use, parking spaces/fees, guarantor |
| Broker & Improvements | 3 | Brokers, TI description |
| Options & Rights | 10 | ROFR, ROFO, expansion, early termination, purchase |
| OPEX | 5 | Inclusions, exclusions, utilities, management fees |
| Insurance & Maintenance | 3 | Tenant insurance, landlord/tenant repair |
| Assignment & Sublease | 9 | 3rd party, affiliates, consent, profits, recapture |
| Holdover & Estoppel | 3 | Holdover rent, estoppel details |
| SNDA | 5 | Existing/future mortgages, ground leases |
| Relocation | 5 | Rights, notice, cost, termination |
| Signage | 6 | Allowed, location, type, approval |
| Other | 1 | Additional rights |

---

## Document Types Handled

### Single-File Mode

| Type | Detection | Behavior |
|------|-----------|----------|
| Full Lease | Default / "Lease Agreement" in title | Full 118-field extraction |
| Amendment | "Amendment" in title/header | Only extracts modified provisions |
| Addendum | "Addendum" in title/header | Same as amendment |

### Multi-File Mode (all documents in folder)

| Type | Example | Handling |
|------|---------|----------|
| Lease Agreement | Original lease | Full extraction, base layer |
| Amendment (1st-Nth) | Extension and Fifth Amendment | Only modified fields extracted |
| COVID-19 Amendment | COVID-19 Agreement to Amend | Rent relief, term changes |
| Omnibus Agreement | Omnibus Agreement | Cross-lease modifications |
| JDE Change Request | JDE Change Request | Name/address changes |
| Termination Notice | Termination Notice | Termination date/terms |
| Settlement Agreement | Settlement Agreement | Resolution terms |
| Estoppel Certificate | Tenant's Estoppel | Factual confirmations |

---

## Technology

| Component | Technology |
|-----------|-----------|
| AI Model | OpenAI GPT-4o |
| Backend | Python, FastAPI, Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| PDF Processing | PyMuPDF (text extraction) + Tesseract (OCR) |
| Word Documents | python-docx |
| Fuzzy Matching | thefuzz (Levenshtein distance) |
| Packaging | PyInstaller (standalone Windows exe) |

---

## Cost Per Document

| Scenario | API Cost | Time |
|----------|----------|------|
| Digital PDF, single file | ~$0.05–0.10 | ~30 seconds |
| Scanned PDF, single file | ~$0.08–0.15 | ~3 minutes |
| Multi-file folder (10 docs) | ~$0.50–1.00 | ~5 minutes |

---

## Installation & Running

### Quick Start

1. Unzip the package anywhere
2. Install Python 3.10+
3. Open command prompt in the unzipped folder
4. `python -m pip install -r lease_summary_app\requirements.txt`
5. `cd lease_summary_app && python launcher.py`

On first launch, the app automatically:
- Creates `C:\seedJura\`
- Installs the Word template
- Installs the API key
- Creates the output folder
- Opens the browser

### Building a Standalone Executable

```
cd lease_summary_app
BUILD.bat
```

Produces `dist\SeedJura\SeedJura.exe` — a single-folder distribution that runs without Python installed.

---

## Configuration

### Output Folder
Set via the UI. Persisted in `user_settings.json`. Default: `C:\seedJura\Summary_Output`

### API Key
Searched in order:
1. `C:\seedJura\openai_api_key.txt`
2. Next to the script files
3. User home directory
4. `OPENAI_API_KEY` environment variable

### Template
Searched in order:
1. `C:\seedJura\SeedJura_Lease_Summary_FORM.docx`
2. Next to the app files
3. Agreement type config path

### Adding New Agreement Types

Create a folder in `agreement_types/` with a `config.json`:

```
agreement_types/
└── nda/
    ├── config.json
    └── field_anchors.json (optional)
```

The config defines fields, prompts, verification rules, and UI sections. The app discovers new types automatically on startup.
