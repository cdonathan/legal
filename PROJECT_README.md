# NDA AI Redlining System — Project Documentation

**Last Updated:** March 26, 2026
**Primary Developer:** Cliff (with Kiro AI assistance)
**Repository:** git@github.com:cdonathan/legal.git

## Overview

AI-powered system that redlines Non-Disclosure Agreements (NDAs) to protect purchaser interests in real estate transactions. Uses a 2-call OpenAI scoring system with deterministic Python threshold enforcement, PII redaction/reconstruction, and LibreOffice headless document processing with track changes.

## System Architecture

```
Step 1: File Conversion (to DOCX)
Step 2: PII Redaction (hex mapping, preserves formatting)
Step 3: AI Analysis (Call 1: Score → Python: Threshold → Call 2: Changes)
Step 4: Redline Application + Output Creation (4 documents)
Step 5: PII Reconstruction (restore original names/addresses)
```

## Pipeline Workflow

### Step 1: File Conversion
- Converts input to DOCX if needed
- Supports: `.docx` (native), `.doc`, `.txt`, `.mhtml`
- **PDF limitation:** LibreOffice PDF→DOCX puts text in drawing frames, not paragraphs. `pdftotext` extracts text fine but redlines can't be applied back. Needs `pdf2docx` library for proper support (not yet implemented).

### Step 2: PII Redaction
- Copies original DOCX, replaces PII with hex placeholders in-place (preserves formatting)
- Patterns detected: EMAIL, PHONE, ADDRESS, STREET, ZIP, COMPANY, DATE, PERSON
- COMPANY regex capped at 30 chars before suffix to prevent sentence-fragment matches
- PERSON whitelist check: skips only if ALL words are whitelisted (not ANY)
- Whitelist: ~16,000 legal/business terms. 294 common first/last names removed to improve PII detection.
- Mapping saved as JSON for later reconstruction

### Step 3: AI Analysis (2-Call System)

**Call 1 — Analysis & Scoring** (`prompt_call1_analysis.md`)
- Model: `gpt-4o`
- Identifies document terminology (confidential info term, recipient, discloser, representatives)
- Quotes exact language from NDA for each category
- Scores 9 core categories + 9 circumstantial categories

**Python Threshold Enforcement** (deterministic, not AI):
- Score 8-10: ALWAYS change
- Score 5-7: Change IF total_score >= 15, OR 3+ items score 5-7, OR any item scores 8-10
- Score 1-4: Change ONLY IF total_score >= 20, OR 2+ items score 8-10
- Score 0: NEVER change
- Builds explicit list of qualifying items, passes to Call 2

**Call 2 — Generate Changes** (`prompt_call2_changes.md`)
- Model: `gpt-4o`
- Receives: Call 1 analysis + Python's "ITEMS TO CHANGE" list + line-numbered NDA
- Core categories (1-9): Full replacement with proper legal language
- Circumstantial categories (C1-C9): Minimal surgical edits (fewest words possible)
- Output: JSON with `original_text` (exact match from NDA) + `replacement_text`

### Step 4: Redline Application + Output Creation
- LibreOffice headless with UNO API
- Track changes enabled before modifications
- Text matching: exact → normalized (tabs→spaces) → regex (flexible whitespace) → 8-word partial match
- **Post-processing rule:** "attorney's fees" → "reasonable attorney's fees" (deterministic, runs every time)
- Produces 4 output documents (see Output section)

### Step 5: PII Reconstruction
- Restores hex placeholders → original PII values using mapping JSON
- Run-level replacement with paragraph-merge fallback for split placeholders

## Scoring Categories

### 9 Core Categories (scored with ranges, full replacement)

| # | Category | Score Range | What It Checks |
|---|----------|:-----------:|----------------|
| 1 | Confidential Info Carve-outs | 0-10 | 3 required exclusions: possession, public, independent |
| 2 | Representatives Breadth | 0-10 | Financial players (investors, partners, members, managers, directors) are essential |
| 3 | Sub-Agreement Requirements | 0-9 | Sign separate agreement (9) → informed of nature (0) |
| 4 | Return/Destroy | 0-8 | Automatic (8) → upon request with destroy option (0) |
| 5 | Non-Circumvention | 0-9 | Broad no-contact (9) → no clause (0) |
| 6 | Term/Duration | 0-9 | No term/perpetual (9) → 1-2 years (0) |
| 7 | Effective Date | 0-8 | Blank (8) → properly defined (0) |
| 8 | Legal Compliance Exceptions | 0-8 | No court order carve-out (8) → full exception with notice (0) |
| 9 | Remedies Balance | 0-9 | Highly punitive (9) → balanced injunctive relief (0) |

### 9 Circumstantial Categories (binary score-or-zero, minimal edits)

| # | Category | Score | Trigger |
|---|----------|:-----:|---------|
| C1 | Electronic Signatures | 4 | Facsimile only, no electronic |
| C2 | Reasonable Fees | 4 | Attorney's fees without "reasonable" |
| C3 | Narrow Indemnification | 5 | Covers "any disclosure" not limited to breach |
| C4 | No Obligation to Proceed | 5 | Implies obligation to transact |
| C5 | Personal Financial Disclosure | 5 | Requires personal financial statements |
| C6 | Signature Page Notation | 3 | Signature block without notation |
| C7 | Commercial Reasonableness | 4 | "Take all steps" / absolute obligations |
| C8 | Defined Term Consistency | 3 | Mixed capitalization of defined terms |
| C9 | Business Purpose Expansion | 4 | Narrow purpose without "purchasing" |

## Output Documents (per NDA)

| # | File | Description |
|---|------|-------------|
| 1 | `_Original.docx` | Unmodified input copy |
| 2 | `_Smart_Attorney_Analysis.md` | Scores, quoted language, reasoning |
| 3 | `_Redacted_Redlined.docx` | PII removed, track changes visible |
| 4 | `_Redacted_Clean.docx` | PII removed, track changes accepted |
| 5 | `_Reconstructed_Redlined.docx` | PII restored, track changes visible |
| 6 | `_Reconstructed_Clean.docx` | PII restored, track changes accepted |
| 7 | `_Mapping.json` | PII hex mapping for audit |
| 8 | `_call1_raw.txt` | Raw AI Call 1 response |
| 9 | `_call2_raw.txt` | Raw AI Call 2 response |

## File Structure

```
/home/cliff/redact/redline_project/
├── code/
│   ├── smart_attorney_system_backup.py    # Main system (current production)
│   ├── batch_run.py                       # Batch processor (reads TestInput/)
│   ├── smart_attorney_system_v2_production.py  # Original 16-pattern system (archived)
│   └── [50+ archived development files]
├── components/
│   ├── prompt_call1_analysis.md           # Call 1 prompt: scoring & analysis
│   ├── prompt_call2_changes.md            # Call 2 prompt: change generation
│   ├── smart_attorney_prompt.md           # Original single-call prompt (archived)
│   └── [other archived prompts]
├── testExamples/                          # Original test NDAs (PDF + DOCX)
├── testExamples_with_pii/                 # Test NDAs with inserted PII
├── libreTest/                             # LibreOffice test outputs
└── PROJECT_README.md                      # This file
```

## Running the System

### Batch Processing (Recommended)
```bash
# Place DOCX files in TestInput folder
cd /home/cliff/redact/redline_project/code
python3 batch_run.py
# Output goes to: /home/cliff/redact/OneDrive_1_3-23-2026/TestOutput/
# Processed files move to: /home/cliff/redact/OneDrive_1_3-23-2026/Completed/
```

### Single File
```bash
cd /home/cliff/redact/redline_project/code
python3 smart_attorney_system_backup.py /path/to/nda.docx
```

### Directories
- **TestInput:** `/home/cliff/redact/OneDrive_1_3-23-2026/TestInput/`
- **TestOutput:** `/home/cliff/redact/OneDrive_1_3-23-2026/TestOutput/`
- **Completed:** `/home/cliff/redact/OneDrive_1_3-23-2026/Completed/`

## Dependencies

- Python 3.12+
- OpenAI API (gpt-4o) — key in `/home/cliff/redact/openai_api_key.txt`
- LibreOffice (headless mode) + UNO Python bindings
- python-docx (`pip install python-docx`)
- Whitelist: `/home/cliff/redact/redaction_whitelist.txt` (~16,000 terms)

## Test Results (March 25, 2026)

### 25-NDA Batch Run
- **23/25 processed successfully** (1 was .doc format, 1 was adequate — no changes needed)
- **19/23 had 100% pattern apply rate**
- Scores ranged from 7 (well-drafted) to 68 (needs heavy work)
- Average processing time: ~30-45 seconds per NDA

### Attorney Comparison (Sample 4 + Sample 2)
Compared AI output against actual attorney redlines:
- **Carve-outs:** 9/10 match
- **Representatives expansion:** 9/10 match
- **Term limits:** 9/10 match
- **Injunctive relief:** 10/10 match
- **Reasonable fees:** Post-processing catches it deterministically
- **Legal compliance exceptions:** AI adds on 8/10 (attorney adds on 3/10 — we're more aggressive)

### Key Gaps vs Attorney
- Effective Date fails on documents with tab characters in blank date fields
- Attorney makes surgical party-renaming changes (e.g., "Client" → "Potential Buyer") that our system doesn't do
- Attorney narrows scope to specific transaction; our system adds protections but doesn't scope-narrow
- "Accept changes" in LibreOffice fails silently (clean versions may still show track changes)

## Evolution History

### Original System (v2_production) — 16 Patterns
- Single AI call with 16 hardcoded pattern triggers
- Model: gpt-4o-mini
- No scoring, no thresholds — applied everything it found
- Missing: non-circumvention, indemnification, obligation to proceed, personal financial, remedies balance

### Current System (backup) — 2-Call Scoring
- 2-call system: Score → Threshold → Changes
- Model: gpt-4o
- Python threshold enforcement (deterministic, not AI-dependent)
- 9 core + 9 circumstantial categories
- Post-processing rules (reasonable fees)
- 4 output documents with PII redaction/reconstruction
- Formatting-preserving PII redaction

### Rules Added During Development
From original → current, these rules were added:
- Category 8: Legal Compliance Exceptions (core)
- Category 9: Remedies Balance (core, absorbed old C8 Injunctive Relief)
- C7: Commercial Reasonableness
- C8: Defined Term Consistency
- C9: Business Purpose Expansion
- C3: Narrow Indemnification
- C4: No Obligation to Proceed
- C5: Personal Financial Disclosure

### Key Architecture Decisions
1. **Python threshold enforcement** — AI was inconsistently applying its own threshold rules. Moving threshold logic to Python between Call 1 and Call 2 made it deterministic.
2. **Core vs Circumstantial edit style** — Core categories get full sentence replacement. Circumstantial categories get minimal surgical edits (fewest words possible).
3. **Post-processing rules** — Deterministic text replacements (like "reasonable" before "attorney's fees") that don't depend on AI scoring.
4. **Zone.Identifier filtering** — Windows metadata files filtered from batch processing.

## Known Issues

1. **Effective Date tab matching** — Documents with tab characters in blank date fields fail text matching. LibreOffice regex whitespace fallback doesn't fully resolve this.
2. **Accept changes error** — `document.getRedlines()` accept method fails silently. Clean versions may retain track changes markup.
3. **PDF support** — PDF→DOCX conversion via LibreOffice puts text in drawing frames. Need `pdf2docx` library for proper paragraph-based conversion.
4. **PII false positives** — "Circumvent Agreement" detected as PERSON. PERSON regex (`[A-Z][a-z]+ [A-Z][a-z]+`) matches any two capitalized words.
5. **PII false negatives** — 3-word names (e.g., "Marcus Realty Associates") not caught by 2-word PERSON regex. Need COMPANY suffix list expansion (add "Associates", "Group", "Partners", etc.).

## Next Steps

1. **PDF support** — Add `pdf2docx` for proper PDF→DOCX conversion
2. **PII detection improvements** — Expand COMPANY suffixes, reduce PERSON false positives
3. **Accept changes fix** — Investigate LibreOffice redlines API for proper change acceptance
4. **Attorney feedback integration** — Process attorney review of 25-NDA batch output
5. **Scope narrowing** — Add rule for narrowing broad NDA scope to specific transaction
6. **Party renaming** — Add rule for clarifying party roles (e.g., "Client" → "Potential Buyer")
