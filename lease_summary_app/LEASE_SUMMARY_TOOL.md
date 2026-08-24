# SeedJura Lease Summary Tool

## Overview

Automated lease agreement analysis tool that ingests commercial lease documents (PDF/DOCX), scans for PII, uses GPT-4o to extract key terms with source verification, and generates a populated SeedJura Lease Summary document.

The system uses a hybrid AI/code approach: AI identifies relevant clauses, code verifies against the source text and extracts verbatim language at sentence boundaries. A targeted AI retry pass catches anything missed.

Built August 10-11, 2026.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         WEB FRONTEND (port 8083)                          │
│          Drag & Drop Upload -> Processing Animation -> Preview            │
│                      -> Download Completed Summary                         │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │ HTTP (FastAPI)
┌───────────────────────────────────▼──────────────────────────────────────┐
│                           BACKEND API                                     │
│                      lease_summary_app/app.py                             │
│                                                                           │
│  POST /api/upload       - Upload file, run full pipeline                 │
│  GET  /api/preview/:id  - Structured field data for preview              │
│  GET  /api/download/:id - Download generated .docx                       │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼──────────────────────────────────────┐
│                        PIPELINE ENGINE                                     │
│                      lease_summary_tool.py                                │
│                                                                           │
│  Phase 1    Phase 2    Phase 3     Phase 3B      Phase 3C     Phase 4    │
│  INGEST --> PII -----> AI -------> VERIFY -----> AI RETRY --> SAVE       │
│  + Type     Scan       Extract     Source Match   Targeted    Template   │
│  Detect               + Anchors   + Expand       Recovery    Populate   │
└──┬──────────┬──────────┬───────────┬─────────────┬────────────┬─────────┘
   │          │          │           │             │            │
┌──▼──┐  ┌────▼───┐  ┌───▼───┐  ┌───▼────────┐ ┌──▼──┐  ┌─────▼─────┐
│PyMuPDF│ │Contract│  │OpenAI │  │Fuzzy Match │ │OpenAI│  │python-docx│
│+ OCR  │ │Redactor│  │GPT-4o │  │+ Keyword   │ │GPT-4o│  │Template   │
│(Tess.)│ │        │  │       │  │  Anchors   │ │Retry │  │Population │
└───────┘ └────────┘  └───────┘  └────────────┘ └─────┘  └───────────┘
```

---

## Pipeline Phases

### Phase 1: Document Ingestion + Type Detection

**Input:** PDF, DOCX, DOC, or TXT file

**Process:**
- **Digital PDFs**: Text extracted directly via PyMuPDF (~1 second)
- **Scanned PDFs**: Detected automatically (< 200 chars = scanned). OCR via PyMuPDF at 300 DPI + Tesseract. Falls back to Otsu preprocessing for difficult pages.
- **DOCX files**: Paragraphs and table cells extracted via python-docx
- **Document type detection**: Identifies full leases vs amendments/addenda by checking filename and document header text

**Document Types:**
| Type | Detection | Behavior |
|------|-----------|----------|
| `lease` | Default | Full extraction of all 118 fields |
| `amendment` | "Amendment", "First Amendment", etc. in title/header | AI returns "See Original Lease." for fields not modified; skips retry for those |
| `addendum` | "Addendum" in title/header | Same as amendment |

**Output:** Raw text + document type classification

### Phase 2: PII Capture & Scan

**Input:** Raw text from Phase 1

**Process:**
- Uses existing `ContractRedactor` class (redactor.py)
- Pattern-based detection: names, entities, addresses, SSNs, tax IDs, accounts, phone, email, dollar amounts, dates
- PII is logged but NOT redacted (AI needs full context)

**Output:** PII findings log, original text passed through

### Phase 3: AI Analysis & Extraction

**Input:** Full lease text (up to 80,000 chars) + document type

**Process:**
- GPT-4o extracts all 118 fields with strict copy/paste-only instructions
- AI returns TWO things per field:
  - `text`: The extracted verbatim content
  - `anchor`: First 8 words of the source sentence (used for verification)
- Amendment-aware: returns "See Original Lease." for provisions not in amendments
- Temperature: 0.1 / Max tokens: 16,000

**Output:** Field data dict + anchor phrases dict (typically 50-60 anchors provided)

### Phase 3B: Source Verification (Hybrid AI/Code)

**Input:** AI extraction + anchor phrases + raw source text

**Process (priority order per field):**
1. **"None." / "See Original Lease."** - Accepted as-is (unless keyword anchors find the text)
2. **AI anchor verification** - Code finds the anchor phrase in source, extracts at sentence boundaries. Validates content matches field's keyword patterns.
3. **Exact match** - Normalized AI text found verbatim in source
4. **Fuzzy match + sentence expansion** - Longest matching substring located, expanded to sentence start/end
5. **Keyword fallback** - Regex patterns from `field_anchors.json` locate the clause, with fuzzy matching (thefuzz) for OCR-garbled text
6. **Short fields** - Names, amounts, yes/no accepted without expansion

**Sentence boundary detection:**
- Backwards: finds period/newline followed by capital letter or section number
- Forwards: finds period followed by new sentence, paragraph break, or section header
- OCR noise stripping: removes leading page numbers/stray digits
- Safety cap: 600 chars max per field

**Output:** Verified field data + flagged fields list + verification report

### Phase 3C: Targeted AI Retry

**Input:** Fields flagged as suspect + expected fields still showing "None."

**Triggers (rare - only when needed):**
- Fields where anchor validation detected wrong-section content
- Fields in `EXPECTED_FIELDS` that are "None." but should exist in most leases
- NOT triggered for "See Original Lease." (amendments)

**Process:**
- Sends a focused second prompt with field-specific hints (where to look in the document)
- OCR-tolerant: instructs AI to find text even with spelling errors
- Verifies recovered text exists in source before accepting

**Output:** Recovered fields (typically 0-6 per lease)

### Phase 4: Template Population & Save

**Input:** Final verified field data + DOCX template

**Process:**
- Loads `SeedJura_Lease_Summary_FORM.docx` template
- Replaces all `[!@FieldName]` and `[*FieldName]` placeholders
- Handles split runs across DOCX XML elements
- Saves DOCX + JSON sidecar

**Output:** Completed summary DOCX + audit JSON

---

## Verification System Detail

### Three-Layer Safety Net

```
Layer 1: AI Anchor Verification
   AI provides "first 8 words" of source sentence
   Code finds those words in source -> extracts surrounding sentence
   Validates extracted content contains field-relevant keywords

Layer 2: Keyword Fallback (field_anchors.json)
   Configurable regex patterns per field (no code changes needed)
   Exact regex match first, then fuzzy sliding-window match (thefuzz)
   Handles OCR errors: "1NSURANCE" still matches "insurance" pattern

Layer 3: Targeted AI Retry
   Only for flagged/suspect fields (rare occurrence)
   Field-specific hints guide AI to correct section
   Result verified against source before accepting
```

### field_anchors.json

External config file with regex patterns per field. Edit without touching code:

```json
{
  "Permitted_Use_Description": [
    "use of premises.*medical",
    "tenant shall use the",
    "premises shall be used",
    "for the sole purpose of"
  ],
  "Tenant_Insurance": [
    "insurance.*at all times during the term.*tenant will carry",
    "tenant will carry and maintain.*insurance",
    "insurance.*general requirements"
  ]
}
```

Patterns are tried in order. First match wins. Fuzzy matching (80% threshold) handles OCR artifacts.

---

## File Structure

```
~/redact/
├── lease_summary_tool.py              # Core pipeline engine (CLI + library)
├── lease_summary_app/
│   ├── app.py                         # FastAPI web backend
│   ├── static/
│   │   └── index.html                 # Single-page web frontend
│   ├── field_anchors.json             # Keyword anchor patterns (editable config)
│   └── LEASE_SUMMARY_TOOL.md          # This document
├── redactor.py                        # PII detection patterns (existing)
├── openai_api_key.txt                 # API key storage
└── compare_output.py                  # Quality comparison utility
```

---

## Input

### Supported File Types
| Type | Method | Speed |
|------|--------|-------|
| Digital PDF | PyMuPDF text extraction | ~1 second |
| Scanned PDF | PyMuPDF 300 DPI + Tesseract OCR | ~2-3 min (40 pages) |
| DOCX/DOC | python-docx extraction | ~1 second |
| TXT | Direct file read | Instant |

### Supported Document Types
| Type | Example | Behavior |
|------|---------|----------|
| Full Lease | "Commercial Lease Agreement.pdf" | Full extraction |
| Amendment | "IVF Florida 1st Amendment.pdf" | Only modified provisions; "See Original Lease." for the rest |
| Addendum | "Lease Addendum - Parking.pdf" | Same as amendment |

### Template
- **File:** `SeedJura_Lease_Summary_FORM.docx`
- **Structure:** Header paragraphs + 3 tables (Basic Info: 40 rows, OPEX: 6 rows, Other Provisions: 35 rows)
- **Placeholders:** 117 fields using `[!@FieldName]` and `[*FieldName]` syntax

---

## Output

### Generated Files

For each processed lease:

1. **`{lease_name}_summary_{date}.docx`** - Populated lease summary document
2. **`{lease_name}_summary_{date}_data.json`** - Audit trail containing:
   - Source filename and document type
   - Generation timestamp
   - PII count and types
   - Verification report (anchor/exact/expanded/flagged counts)
   - All field values

### Output Filename Convention
- Input: `Cooper Orthodontics KTJZ III GMP Lease Agreement - FULLY EXECUTED.pdf`
- Output: `Cooper_Orthodontics_KTJZ_III_GMP_Lease_Agreement_summary_08-10-26.docx`

---

## Web Application

### Running the App

```bash
cd ~/redact/lease_summary_app
uvicorn app:app --host 0.0.0.0 --port 8083 --reload
```

Open: http://localhost:8083

### User Flow

1. **Upload** - Drag & drop or click to browse (PDF/DOCX)
2. **Configure** - Optionally fill "Prepared By" and "Purpose"
3. **Process** - Click "Generate Lease Summary". Progress shows all phases.
4. **Preview** - All 118 fields in 18 sections. Stats: fields extracted, PII count, verification breakdown.
5. **Download** - One-click .docx download

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload + process, returns job_id and results |
| GET | `/api/preview/{job_id}` | All fields grouped by section |
| GET | `/api/download/{job_id}` | Download generated DOCX |

### Design System
- Matches SeedJura portal: Inter font, dark header (#0F172A), teal accent (#089498)
- Card-based layout, responsive, vanilla JS (no framework)

---

## CLI Usage

```bash
# Single lease
python3 lease_summary_tool.py "path/to/lease.pdf" \
  --preparer "Phyllis Shuster" \
  --purpose "For the purchase of the Margate, FL Property" \
  -o "/path/to/output"

# Batch mode
python3 lease_summary_tool.py "/path/to/leases/" --batch \
  --preparer "Phyllis Shuster"

# Minimal
python3 lease_summary_tool.py "lease.pdf"
```

| Argument | Short | Description |
|----------|-------|-------------|
| `input` | - | File path or directory (batch) |
| `--output-dir` | `-o` | Output directory |
| `--preparer` | `-p` | Name of preparer |
| `--purpose` | - | Summary purpose |
| `--batch` | `-b` | Process all files in directory |

---

## Cost

| Document Type | API Cost | Time |
|---------------|----------|------|
| Digital PDF (no retry) | ~$0.05-0.08 | ~30 seconds |
| Digital PDF (with retry) | ~$0.10-0.12 | ~45 seconds |
| Scanned PDF (no retry) | ~$0.08-0.10 | ~3 minutes |
| Scanned PDF (with retry) | ~$0.12-0.15 | ~3.5 minutes |

Model: GPT-4o. Typical token usage: 15K-25K input + 4K-8K output per call.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| python-docx | 1.2.0 | Read/write DOCX template |
| pymupdf | 1.27.1 | PDF text extraction + OCR rasterization |
| openai | 1.100.2 | GPT-4o API |
| pytesseract | 0.3.13 | OCR interface |
| Pillow | - | Image handling for OCR |
| opencv-python | 4.13.0 | Image preprocessing for difficult scans |
| thefuzz | 0.22.1 | Fuzzy string matching for OCR tolerance |
| tesseract-ocr | 5.3.4 | System OCR engine (apt) |
| fastapi | 0.115.0 | Web API |
| uvicorn | 0.30.6 | ASGI server |
| python-multipart | 0.0.30 | File upload handling |

---

## Test Results

### Batch Run (August 10, 2026) - 4 Target Leases

| Lease | Type | Phase 3B | Phase 3C | Result |
|-------|------|----------|----------|--------|
| Commercial Lease (2805 DSMC) | Digital PDF | 12 anchor, 5 exact, 7 expanded | 5 recovered | All key fields OK |
| Cooper Orthodontics | Scanned (40pp) | 17 anchor, 3 exact, 8 expanded | 4 recovered | All key fields OK |
| Breathe Free (2805) | Digital PDF | 17 anchor, 4 exact, 6 expanded | 6 recovered | All key fields OK |
| GMP Total Dental | Digital PDF | 15 anchor, 5 exact, 7 expanded | 3 recovered | All key fields OK |
| IVF Florida 1st Amendment | Digital PDF | 3 anchor, 2 exact, 10 expanded | 1 recovered | Correctly identified as amendment |

### Key Fields Verified Across All Leases:
- Permitted Use - Full clause language with "Tenant shall use..."
- OPEX Inclusions - Complete itemized lists
- Tenant Insurance - Section references + coverage requirements
- Landlord/Tenant Repair - Full obligation clauses
- Assignment (3rd parties + affiliates) - Complete provisions
- Holdover Rent - Rate percentages with section references
- Commencement Date - Full conditional language (A/B/C options)
- Options (ROFR, ROFO, etc.) - "None." when not applicable

### Content Quality Standard
The tool produces output matching the hand-crafted Margate example:
- Verbatim lease language (not AI summaries)
- Section references included
- Full conditional clauses for dates/terms
- Explicit "None." for inapplicable provisions
- "See Original Lease." for amendment documents
