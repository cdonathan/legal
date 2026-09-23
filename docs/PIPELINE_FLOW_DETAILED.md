# Summary Tool & Redline Tool — Detailed Pipeline Trace

This document traces both standalone tools' current implementations exactly as built, step by
step, distinguishing **[LOCAL CODE]** (deterministic, no AI) from **[AI CALL]** (OpenAI API
invocation). It is based on direct reading of:

- Summary tool: `delivery/seedjura_psa_standalone_20260922_104755.zip` (`app.py`, `engine.py`,
  `lease_summary_tool.py`, `field_variants.py`, `multi_file.py`, `agreement_types/`, `xml_export.py`,
  `redactor.py`)
- Redline tool: `delivery/ai_attorney_v4.zip` → `ai_attorney_v3/` (`app.py`, `evaluation_module.py`,
  `provenance_verifier.py`, `cascade_engine.py`, `rules_engine.py`, `redaction.py`,
  `clause_repository.py`, `document_processor.py`, `text_utils.py`, `context_extractor.py`)

Purpose: give a precise, file/function-level record of what is deterministic code and what is an
AI call, so the AWS re-architecture preserves the existing trust boundaries (what the AI is
allowed to decide vs. what code always verifies) rather than accidentally weakening them.

---

## Legend

- **[LOCAL CODE]** — deterministic: regex, string/fuzzy matching, file I/O, DB lookup, python-docx/
  LibreOffice manipulation. No model call, fully reproducible, cheap.
- **[AI CALL]** — an OpenAI API call. Numbered per tool's own "Call N" convention where one exists.
- File:function references point to the file inside each tool's standalone package root
  (`seedjura_psa_standalone_.../` for summary, `ai_attorney_v3/` for redline).

---

# PART 1 — SUMMARY TOOL

Package: `seedjura_psa_standalone_20260922_104755/`
Entry point: `app.py` (FastAPI), core logic in `engine.py` + `lease_summary_tool.py` (legacy
primitives reused by the newer generic engine) + `multi_file.py` (multi-document merge) +
`field_variants.py` (output shaping) + `agreement_types/` (per-document-type plugin config).

Two pipelines exist side by side: **single-file** and **multi-file/merge** (lease + amendments).
Both run in a background `threading.Thread` per job; the HTTP request returns a `job_id`
immediately, and the frontend polls `GET /api/status/{job_id}` against a `meta.json` file written
to `WORK_DIR/{job_id}/meta.json` (atomic write via temp-file + `os.replace`, so a poller never
reads a half-written file).

## 1.0 Entry points [LOCAL CODE]

- `POST /api/upload` (`app.py:upload_agreement`) — single file. Validates extension
  (`.pdf/.docx/.doc/.txt`), generates `job_id = uuid4()[:8]`, saves the upload to
  `WORK_DIR/{job_id}/{filename}`, writes initial `meta.json` (`status: "processing"`), spawns
  `_run_single_file_pipeline` in a daemon thread, returns `{job_id, status}` immediately.
- `POST /api/upload-folder` (`app.py:upload_folder`) — multi-file. Takes a folder path (Windows or
  WSL, converted via `_win_to_wsl`), calls `multi_file.scan_folder()` to enumerate documents,
  spawns `_run_multi_file_pipeline`.

## 1.1 Pipeline A — Single File (`app.py:_run_single_file_pipeline`)

### Phase 1 — Ingest [LOCAL CODE]
`lease_summary_tool.ingest_document()`. Dispatches by extension:
- **PDF** (`_extract_pdf`): opens with PyMuPDF (`pymupdf`). Detects encrypted PDFs
  (`doc.needs_pass`) and raises `DocumentIngestError(kind="encrypted")` if an empty-password
  attempt fails. Extracts `page.get_text()` per page. Runs `_fix_handwritten_dates()` — a regex
  table correcting common OCR misreads (e.g. "Bias"→"1st", "Znd"→"2nd") — and detects
  `[handwritten...]` markers; pages containing them are queued for a **targeted re-OCR**
  (`_ocr_single_page`, pytesseract at higher DPI), and the result is appended as a
  `[RE-OCR CROSS-CHECK ...]` block, never replacing the original extracted text. If the whole
  document's text is thin (<200 chars total or <50 chars/page average), falls back to full-document
  OCR (`_ocr_pdf`), used only if it yields more text than direct extraction.
- **DOCX** (`_extract_docx`): python-docx, reads paragraphs + tables.
- **DOC**: unsupported, raises `DocumentIngestError(kind="unsupported")`.
- **TXT/MD**: plain read.
- Errors (empty file, <20 chars extracted, corrupt PDF) raise `DocumentIngestError`, mapped to a
  structured log code (`app_logging.INGEST_KIND_TO_CODE`), job marked `status="error"`.
- **Out:** `raw_text` (str).

### Type & sub-type resolution [LOCAL CODE]
- `agreement_types.detect_agreement_type()` — if `agreement_type == "auto"`, scores each
  registered `AgreementType` (lease, PSA) by counting filename/header keyword hits from that
  type's `doc_type_signals` config (filename hit = +10, header hit = +5, checked against the first
  3000 chars). Highest score wins; falls back to `"lease"` if nothing matches.
- `AgreementType.detect_sub_type()` — checks `sub_types` config (e.g. lease's `"amendment"`,
  `"addendum"`; PSA's `"amendment"`, `"termination"`) against filename substrings and header text.
- Both are pure keyword/config lookups defined per agreement type in
  `agreement_types/{type}/config.json` — no AI involved in classification.

### Phase 2 — PII scan [LOCAL CODE]
`lease_summary_tool.redact_and_capture_pii()`. **Important:** this does *not* redact the text sent
to the AI. It runs `ContractRedactor`'s regex patterns (SSN, EIN, account/routing numbers, credit
cards, email, phone, title+name, address, dollar amounts, dates — `redactor.py`) over `raw_text`
solely to build a `pii_findings` list (type/value/position) for **display purposes** — a
`pii_summary` count shown in the UI/job meta. The code's own comment states the reasoning
explicitly: "We do NOT redact for the AI analysis — we need the full text." So
`text_for_ai == raw_text`, unmodified, is what actually goes to OpenAI. `redactor.py`'s full
pattern+whitelist redaction path exists but is only used by its own standalone CLI tool against
`.mhtml` files — it is not wired into this FastAPI app's pipeline.
- **Out:** `(text_for_ai, pii_findings)` where `text_for_ai` is unredacted raw text.

> **This is the key difference from the redline tool** (see Part 2) — the summary tool's current
> implementation sends full, un-redacted contract text to OpenAI. Any AWS re-architecture that
> wants to preserve "AWS never sees raw PII" needs to either (a) actually redact before the AI call
> here (a real behavior change, since the AI currently reads names/dollar figures/addresses
> directly to extract them), or (b) accept that the summary tool's AI call legitimately needs
> unredacted text because it's extracting exactly those fields, and scope the "no PII leaves the
> building" guarantee to apply only to the redline tool's evaluation step. This needs an explicit
> decision — see the note at the end of this document.

### Phase 3 — Call 1: Raw extraction [AI CALL — Call 1]
`engine.analyze_with_ai()`. Builds a prompt (`build_extraction_prompt()`) listing every field from
`agreement.fields` (name → AI-facing description), the sub-type's `ai_instruction`, the agreement's
`extraction_rules`, and a **"HANDWRITTEN DATE HANDLING"** block: the model is instructed to resolve
`[handwritten: X]` / `[handwritten-year: X]` markers using the `[RE-OCR CROSS-CHECK]` block first,
then context, and if still unresolvable to emit the literal string **`"NEEDS VERIFICATION"`**
rather than guess — this exact marker string is what the entire human-verification-pause mechanism
keys on downstream. Response format per field: `{text, section, anchor (first ~8 words of the
source sentence), date (date fields only, mm/dd/yyyy)}`.
- Call: `_call_openai_with_retry` — model `gpt-4o` (`lease_summary_tool.AI_MODEL`),
  `temperature=0.1`, `max_tokens=16000`, `response_format=json_object`, 3 retries w/ exponential
  backoff, failures classified into `auth`/`quota`/`timeout`/`transient` (`AIServiceError`).
  JSON parsed with a regex-based recovery pass (`_attempt_json_recovery`) if malformed.
- **Out:** `(field_data, anchors, dates, sections)`.
- User-supplied `preparer`/`purpose`, and the current-date `summary_date` field, are then force-set
  **in code**, not by the AI.

### Phase 3B — Source verification [LOCAL CODE]
`engine.verify_and_expand()` — the core deterministic verification engine, per field:
1. Date fields (`Date_*`, `Amendment_Effective_Date`) search only the first 10,000 chars of source
   (dates always sit on opening pages — restricting the window avoids matching an unrelated date
   later in the document).
2. "None."-like values: tries a keyword-anchor fallback search (`field_anchors.json` regex
   patterns) before accepting an empty value.
3. **Short fields** (names, addresses, dollar figures — `agreement.short_fields`): accepted as-is,
   position located via `_locate_in_source()`.
4. **AI anchor-phrase verification**: if the AI supplied an `anchor` phrase, every occurrence of
   that phrase in the source is found (handles duplicates — e.g. table of contents vs. actual
   clause), the sentence around each occurrence is extracted, and validated against
   `field_anchors[field_name]` regex patterns. First occurrence that validates wins. If none
   validate, the field is queued for retry rather than silently keeping a possibly-wrong match.
5. **Exact match** (whitespace/case-normalized substring).
6. **Fuzzy match** (`thefuzz`) — locates the best-scoring window, expands to sentence boundaries,
   flags for retry if score <0.5.
7. Final fallback: keyword-anchor search again, else counted as `not_found` and the raw AI value is
   kept as-is (unverified).
- **Out:** `(verified_data, report, flagged_fields, positions)`. `positions[field] = (start, end)`
  — character offsets into the **original** `raw_text` — feeds every downstream snippet/screenshot
  step. `report` tallies exact/expanded/anchor_verified/short_field/not_found/none_value counts.

### Phase 3B2 — First human-verification pause [LOCAL CODE — blocking pause/resume]
`app.py:_detect_handwriting_touched_fields()` flags a field if either (a) its value still literally
contains `"[handwritten"` or `"needs verification"` (case-insensitive substring check —
`field_variants.needs_verification()`), or (b) its verified source position overlaps a
`[handwritten...]` marker found anywhere in the raw text — this catches confident-looking AI
guesses whose *source* was itself marked handwritten, not just outright AI failures.

If any fields are touched:
- `_build_verification_items()` builds one review item per field: slices the literal document
  substring at that field's `positions` span (not the AI's possibly-paraphrased value) as the
  search target, calls `lease_summary_tool.find_snippet_screenshot()` (PyMuPDF `page.search_for()`
  at 250 DPI) to crop and save a PNG of the source region, and writes a UI-facing instruction
  string.
- `job_meta["status"] = "needs_verification"`, `verification_items` populated, saved to `meta.json`.
- `_wait_for_corrections()` **blocks the background thread** on a `threading.Event` (keyed by
  `job_id`) for up to 1 hour. `POST /api/verify/{job_id}` (`submit_verification`) writes corrections
  into `meta["_pending_corrections"]` and signals the event; the waiting thread reads the dict back
  out, applies non-empty corrections into `field_data`, sets status back to `"processing"`, and
  continues.
- **This is exactly the "resume-in-place" pattern flagged earlier as not scaling well** — a real
  thread is held open, potentially for up to an hour, per document needing review. See the
  recommendation in this session's earlier discussion (verification as an independent job/API call
  rather than a blocking pause) for how this should change in the AWS version.

### Phase 3C — Call 2: Interpretation [AI CALL — Call 2]
`engine.interpret_fields()` / `_interpret_batch()`. Runs only on fields **not** still flagged
`needs_verification`. Uses small ±500-char snippets around each field's verified position
(`build_snippets()`) rather than the whole document. Batches of 30 fields, up to 4 concurrent
via `ThreadPoolExecutor`. Prompt asks for a precise plain-language reading per
`agreement.interpretation_rules` (e.g. lettered breakdowns for multi-part clauses, literal `"None"`
for empty fields). Has a timeout circuit-breaker: aborts if ≥half the batches time out, rather than
exhausting retries on every batch individually.
- **Out:** `{field_name: interpretation_string}`.

### Phase 3D — Completeness check [LOCAL CODE, no AI]
`engine.check_completeness()` — pure structural check: which expected fields are still
"None"-like (`missing_expected`), which have no interpretation, which look "suspect" (a date/amount
field whose interpretation has no digits at all — sanity heuristic). `needs_retry` = missing
fields ∪ fields flagged during verification.

### Phase 3D (retry) — [AI CALL — retry of Call 1]
`engine.ai_retry_fields()`, triggered only if `needs_retry` is non-empty. Targeted prompt over just
the missing/flagged fields plus per-field `retry_hints`, re-reads the full raw source text,
instructs the model to tolerate OCR typos and return `"Not found."` rather than fabricate.
Recovered values are **re-verified in code** — must appear as a substring in source or pass a fuzzy
check — before being accepted; this is a code-side guard against hallucination on the retry path.
Recovered fields get a fresh (smaller) interpretation call.

### Phase 3D2 — Second human-verification pause [LOCAL CODE]
Identical mechanism to 3B2, re-run because the retry step has no handwriting-resolution guidance of
its own and could reintroduce a garbled value that slipped past the first pause.

### Phase 3E — Call 4: QA/feedback pass [AI CALL — Call 4]
`engine.suggest_improvements()`. Non-fatal, advisory only. Sends the full source document (up to
100,000 chars) plus a compact extraction-result table and asks the model to flag inconsistencies,
missed fields, or ambiguous field descriptions. **No corrected values are requested or applied** —
output is saved to `qa_feedback.json` as a standalone artifact for later prompt/config improvement,
never merged into `field_data`. Failures here are caught and logged non-fatally; the job continues
regardless.

### Field-variant construction [LOCAL CODE]
`field_variants.build_field_variants()` — expands each flat field into 3 output variables:
- `FieldName` — base value (`clean_value()`: "None"-like → literal `"None"`; unresolved →
  literal `"NEEDS VERIFICATION"`).
- `FieldName_Int` — interpretation + optional `"(Section X)"` tag (suppressed for `short_fields`).
- `FieldName_Raw` — verbatim text tagged `"[DocLabel, Section X]: ..."`.

### Phase 4 — Output generation [LOCAL CODE]
- **DOCX**: `lease_summary_tool.populate_template()` — python-docx, literal string substitution of
  `[!@FieldName]` / `[*FieldName]` placeholder tokens (handles a placeholder spanning multiple
  DOCX `<w:r>` runs by concatenating run text, substituting, then collapsing into the first run).
  Pure templating, no rich formatting logic.
- **XML**: `xml_export.field_data_to_xml_pretty()` — builds a `<GlobalFormVars>` document. For
  `"lease"`, uses a fixed ~115-element `XML_FIELDS` schema with a rename map and a keyword-based
  split of `Early_Termination_Description` into landlord/tenant variants. For any other type (e.g.
  PSA), emits the agreement's own real field names directly, unmapped. Each field gets 3 XML
  elements (base/_Int/_Raw); base carries a `normalized_date` attribute when applicable.
- **JSON sidecar**: written directly in `app.py` — source file, timestamp, agreement type, PII
  count, fields extracted/total, full 3-variant field data, section references.
- **Auto-save**: all three files copied into the user's configured output folder (default
  `C:\seedJura\Summary_Output`, persisted in `user_settings.json`), with locked-file retry logic
  (`_safe_copy` appends a timestamp suffix if the destination is open elsewhere, e.g. in Word).
- `job_meta["status"] = "complete"`.

## 1.2 Pipeline B — Multi-File / Merge (`app.py:_run_multi_file_pipeline`)

Used for a lease + its amendment history. Differs from the single-file path as follows:

1. **Ingest all files [LOCAL CODE]** — per-file failures are logged and skipped, not fatal to the
   whole batch. Type auto-detection runs once, against the first successfully-ingested document.
2. **Signature gate [LOCAL CODE]** `multi_file.has_signature()` — any document whose last 10,000
   chars contain none of a fixed signature-keyword list (`"in witness whereof"`, `"/s/"`,
   `"docusign"`, `"per:"`, etc.) is **excluded entirely** as an unsigned/draft document, not merely
   flagged.
3. **Classification [LOCAL CODE]** `multi_file.classify_document()` — lease type uses a hardcoded
   keyword ladder, filename checked before header text (deliberate — amendment headers often recite
   the full prior amendment history, which would otherwise misassign the ordinal number). Any
   non-lease type uses only that type's `config.json` `sub_types[*].filename_signals` /
   `header_signals` — no lease-specific keywords are hardcoded for other types.
4. **Per-document extraction [AI CALL — Call 1 per document, batched]**
   `engine.analyze_documents_parallel()` — the origin document (full lease/PSA) requests every
   field (`require_all=True`); every other document type (amendment, guaranty, etc.) requests only
   a scoped field subset with `require_all=False`. Up to 4 documents processed concurrently.
5. **Per-document verification [LOCAL CODE]** — `verify_and_expand()` run independently per
   document; `flagged_fields` accumulate into a combined list.
6. **Date-role resolution [LOCAL CODE]** — driven by each agreement type's `date_roles` config
   (which field names represent origin/termination/effective dates — these differ between lease and
   PSA). Each candidate date is validated with `multi_file.parse_strict_date()` (rejects OCR garbage,
   accepts embedded dates like `'June 1, 2020 (the "Effective Date")'`). The single "effective
   date" fact is resolved by picking, among all qualifying documents, whichever has the **latest
   validly-parsed date** — never by file sort order or AI-guessed chronology.
7. **Merge [LOCAL CODE]** `multi_file.merge_fields()` — iterates documents oldest→newest; for each
   field, "latest document wins, earlier value pushed to history" — **except** three pinned
   categories that bypass sort order: origin-only fields, termination-only fields, and the single
   effective-date field (pinned to the specific document identified in step 6, not whichever
   document merely sorts last).
8. **Combined human-verification pause [LOCAL CODE]** — one combined pass (rather than the single
   file pipeline's two separate pauses) covering both unresolved priority dates and any merged field
   whose winning document's source touched a handwriting marker.
9. **Call 3 — interpretation [AI CALL]** — one call over the merged current values (not once per
   document), using snippets built from whichever document each field actually came from.
10. **Completeness/retry** — same mechanism as single-file, retried against the origin document's
    text.
11. **QA pass [AI CALL — Call 4]** — run once over all documents concatenated with a
    `"=== DOCUMENT BREAK ==="` separator.
12. **Output** — `_Raw` variant includes every historical version tagged with its source document +
    section (most recent first); `_Int` shows only the current/superseding value. Filenames use the
    folder name.

## 1.3 Plugin system (`agreement_types/`)

`discover_types()` scans each subdirectory for `config.json` at startup and builds an
`AgreementType` instance per type (currently `lease`, `psa`). Each type supplies: field list +
AI-facing descriptions, section groupings for UI/display, `short_fields`/`none_fields`/
`expected_fields` sets, `doc_type_signals` (auto-detection keywords), `sub_types` (amendment/
termination detection + skip-field rules + AI instructions), `date_roles` (drives the multi-file
date-pinning logic generically, not hardcoded per type), template path, and all AI prompt text
(extraction rules, interpretation rules, retry hints) — plus a separate `field_anchors.json`
per type used by the anchor-verification/fallback-search logic in `verify_and_expand()`. Lease and
PSA share the exact same code path through `engine.py`/`multi_file.py`; everything that differs
between document types is config, not code — meaning a third type (e.g. NDA-adjacent or a new
agreement class) can be added without touching the pipeline logic itself.

## 1.4 Job state machine

`processing` → (`needs_verification` ⇄ `processing`, zero or more times) → `complete` | `error`.
`job_meta["phases"]` is a live per-phase string map (`ingest`, `pii`, `ai`, `verify`, `verify_human`,
`interpret`, `retry`, `qa`, `generate`) updated at every step boundary — this is what the polling
UI renders as progress.

## 1.5 External dependencies / secrets

- **OpenAI**: `gpt-4o`, key read from `openai_api_key.txt` (several fixed search paths, including
  `C:\seedJura\openai_api_key.txt`) or `OPENAI_API_KEY` env var.
- **PyMuPDF**: PDF text extraction, encrypted-PDF detection, screenshot cropping for the
  verification UI.
- **pytesseract + Tesseract**: OCR fallback for scanned PDFs and targeted re-OCR of suspected
  handwritten regions.
- **python-docx**: DOCX ingestion and template population.
- **thefuzz**: fuzzy matching in `verify_and_expand`, degrades gracefully if not installed.
- Filesystem: `WORK_DIR=/tmp/lease_summary_jobs` (scratch), configurable output folder (default
  `C:\seedJura\Summary_Output`), logs to `C:\seedJura\logs\seedjura.log`.

---

# PART 2 — REDLINE TOOL

Package: `ai_attorney_v3/` (from `ai_attorney_v4.zip`)
Entry point: `app.py` (FastAPI), a global **in-memory** `jobs: dict` (not persisted — restarting
the process loses all job state; this is a key difference from the summary tool's disk-backed
`meta.json` and matters for how this must change on AWS). No authentication on any endpoint; CORS
is wide open (`allow_origins=["*"]`) — flagged explicitly as a gap to close before this is exposed
beyond localhost.

## 2.0 Job creation — `POST /api/upload` [LOCAL CODE]
`app.py:upload_file`. Validates extension (`.docx/.pdf/.txt/.mhtml/.mht`), generates
`job_id = uuid4()`, saves the upload under `JOBS_DIR/{job_id}/`, inserts a job dict into the
in-memory store (`status="queued", step=0, pass_number=1`), spawns a daemon thread running
`process_job(job_id)`, returns `{job_id, status}` immediately.

## 2.1 Step 1 — Text extraction [LOCAL CODE]
`document_processor.py:DocumentProcessor.extract_text`. Dispatches on extension: `.txt` raw read;
`.mhtml/.mht` HTML-tag-stripped; `.pdf` via `pdfplumber` page-by-page; `.docx` via python-docx
(`doc.paragraphs` only — **tables and headers/footers are not extracted**, which is intentional
given the AI prompt later explicitly tells the model to avoid quoting TOC/headers). All paths run
`fix_ligatures()` (PDF ligature-artifact string substitution). **Out:** `job["original_text"]`,
`job["word_count"]`.

## 2.2 Step 2 — PII "hex redaction" [LOCAL CODE — regex/set lookups, no AI]
`redaction.py:apply_hex_redaction`. Three deterministic passes run **before the AI ever sees the
text**:
1. **Blacklist companies**: loads ~617 known company names from 5 `.txt` files (`blacklists/` —
   broker, real-estate, title, law-firm, insurance companies), builds case-insensitive whole-word
   regexes (longest-first, greedy), replaces matches with `[REDACTED]`, tagged `"COMPANY"`.
2. **Structural regex patterns**: email, phone, dollar amounts, SSN, EIN, company-suffix (LLC/Inc/
   Corp), address, ZIP, two date formats.
3. **Person-name catch-all**: `Capitalized Capitalized` pattern (with optional middle initial or
   suffix), checked against a 16,278-line whitelist (`redaction_whitelist.txt` — common
   English/legal words) so defined terms and boilerplate capitalized phrases aren't falsely flagged;
   if all words in a match are whitelisted, it's skipped, otherwise tagged `"PERSON"`.
- **Out:** `redacted_text` (this is what's actually sent to OpenAI and matched against clauses for
  the rest of the pipeline) + `pii_mapping` (`{original_string: LABEL}`, kept only in job memory,
  never sent to OpenAI).
- **This is the behavior the summary tool's PII step does not currently replicate** — see the note
  in Part 1 and the cross-tool note at the end of this document.
- **Reconstruction**: `reconstruct_pii` / `reconstruct_pii_in_docx` replace `[REDACTED]` tokens back
  with original values, longest-value-first, strictly by first-remaining-occurrence order (every
  PII item is replaced by the identical literal token, not a numbered/hashed placeholder despite the
  module's "hex" naming — reconstruction relies on token order being preserved downstream; there is
  no positional/ID-based safety net).

## 2.3 Step 3 — Fetch clauses from provisions DB [LOCAL CODE — DB lookup, no AI]
`clause_repository.py:ClauseRepository.get_clauses_by_form_type`. Tries SQL Server (`pymssql`)
first; on failure, permanently flips to a SQLite fallback (`provisions.db`) for the life of the
repository instance. Clauses get **positional 1-based IDs** (index within this job's result set,
not the DB primary key) — this is the ID the AI is told to reference. HTML clause text is stripped/
normalized (`text_utils.clean_clause_html`) into `clause.clean_text`. Zero clauses returned → job
aborts with `status="error"`.

## 2.4 Step 4 — Deterministic Rules Engine [LOCAL CODE — no AI]
`rules_engine.py:RulesEngine.apply`. 6 hardcoded regex→fixed-replacement rules (e.g. `attorney's
fees` → `reasonable attorney's fees`; `in perpetuity` → a fixed 2-year term clause), with lookback
guards against double-fixing already-corrected text. Produces `ProposedChange`s with
`confidence="exact"`, `source="rules_engine"`, IDs starting at 1000 (to avoid collision with
cascade-engine IDs assigned later). **These bypass the cascade engine and AI entirely.**

## 2.5 Step 5 — AI Evaluation [AI CALL]
`evaluation_module.py:EvaluationModule.evaluate` → `_evaluate_batch` → `_build_prompt`. Clauses
batched (25 per batch). Prompt explicitly instructs the model:
- It is an **evaluator only** — must not write replacement legal language.
- `document_section` must be an exact 30-150 char verbatim quote from the document body (explicitly
  told to avoid TOC/headers/footers/signature blocks).
- `suggested_portion` must be an exact verbatim quote **from the clause text**, minimal portion
  only.
- Be aggressive — flag any clause where the document's language is weaker/vaguer.
- Evaluate every clause in the batch; return `priority: "low"` rather than skip irrelevant ones.
- Return strictly a JSON array.
- Call: `gpt-4o`, `max_tokens=16000`, `temperature=0.0`. Malformed/truncated JSON is salvaged via a
  manual brace-depth scan (`_recover_truncated`) that extracts whatever complete objects it can.
- **Out:** `findings: list[AIFinding]` (id, clause_id, document_section, issue, suggested_portion,
  priority). The AI never outputs replacement text that gets used directly — `suggested_portion` is
  a claimed verbatim quote, verified in the next two steps, not trusted blindly.

## 2.6 Step 6 — Boundary validation [LOCAL CODE — pure string checks, not AI]
`evaluation_module.py:EvaluationModule.validate_response`. For each finding, two checks against
whitespace-normalized text:
1. `document_section` must actually appear in the document text — fails → rejected, dropped
   silently (the AI hallucinated a quote that isn't in the document).
2. `clause_id` must be in range, and `suggested_portion` must actually appear in that clause's text
   — fails → rejected (bad reference, or the AI paraphrased instead of quoting).

This is the first line of defense against AI hallucination — pure substring checks, zero AI
involvement, and it runs on every finding before anything reaches the cascade engine.

## 2.7 Step 7 — Cascade Engine resolution [LOCAL CODE — string-similarity algorithms, no AI]
`cascade_engine.py:CascadeEngine.resolve`, run once per valid finding. Four tiers, stopping at the
first success:
- **Tier 1 — exact**: is `suggested_portion` a literal substring of the clause text (raw, then
  whitespace-normalized)? → `confidence="exact"`.
- **Tier 2 — fuzzy**: sliding-window `difflib.SequenceMatcher` scoring (coarse pass then fine pass
  for long clauses, an O(n²) optimization), threshold 0.90 → `confidence="fuzzy"`.
- **Tier 3 — full clause**: only attempted for short clauses (≤200 chars) where the clause isn't
  disproportionately longer than the target text (explicit anti-hallucination-scale guard) — if the
  document section can be located with sufficient confidence, substitutes the entire clause text →
  `confidence="full_clause"`.
- **Tier 4 — human review**: always succeeds as the terminal tier. No replacement text —
  `confidence="manual"`, carries the full clause text and the AI's stated issue for attorney
  judgment. **Manual-tier items are never auto-applied, regardless of what the user selects later.**

Every tier attempt (pass or fail, with score/reason) is written to an audit trail
(`audit_logger.py`).

## 2.8 Step 8 — Provenance Verification [LOCAL CODE — second, independent substring re-check]
`provenance_verifier.py:ProvenanceVerifier.verify_all` / `.verify`. A defense-in-depth gate distinct
from the cascade tiers themselves:
- Rules-engine changes auto-verify (hardcoded text).
- Manual-tier changes auto-verify as `"human_review"` (nothing to check — no auto-apply text
  exists).
- Everything else: re-checks `change.replace` is actually a substring of its source clause. **On
  failure, the change is forcibly demoted** — `confidence` overwritten to `"manual"`, `replace`
  cleared to `""` — i.e. any change that somehow slipped through the cascade with unverifiable
  replacement text is knocked down to a manual-review item rather than being applied. Nothing is
  silently dropped at this stage; everything either stays verified or becomes a manual item.

## 2.9 Step 9 — Context extraction & positioning [LOCAL CODE]
`text_utils.py:locate_text_in_document` + `context_extractor.py:extract_context`. Re-locates each
change's anchor text in the document (exact → normalized → fuzzy sliding-window, in that order),
sets `document_position`, and extracts 150 words of context before/after (word-boundary-snapped) for
the review UI.

## 2.10 Step 10 — Merge, dedupe, finalize [LOCAL CODE]
Combines `rules_changes` + cascade-verified changes (cascade changes that duplicate a rules-engine
match by text are dropped — rules engine wins), sorts by document position, reassigns sequential
IDs. Saves a full audit log (`{job_id}_audit.json`) covering AI responses, every tier attempt, every
resolution, every provenance check. `job["status"] = "awaiting_selection"`.

## 2.11 Client interaction — `GET /api/job/{id}`, `GET /api/job/{id}/document` [LOCAL CODE]
Status polling returns `proposed_changes` once `awaiting_selection`. `.../document` converts the
original DOCX to structured HTML for an editable browser preview (`docx_to_html.py`) — inspects raw
run XML directly for bold/italic/underline/strikethrough rather than relying on style inheritance,
and tags each paragraph with an index for diff-mapping.

## 2.12 Step 12 — Apply selected changes — `POST /api/job/{id}/apply` [LOCAL CODE]
`app.py:apply_selected`. Filters to `applicable` = non-manual changes with actual replacement text
(manual items are **never** auto-applied, even if their ID is passed as "accepted"). Two paths:

**2.12a — LibreOffice UNO path (real track changes)** `_apply_with_libreoffice_uno`: if the `uno`
Python bindings are available, launches headless LibreOffice over a socket bridge, opens the
working document, sets `RecordChanges=True` (the actual Word-compatible track-changes flag,
equivalent to enabling Track Changes in the Writer/Word UI), uses LibreOffice's native
`findFirst()`/`setString()` to apply each change — because `RecordChanges` is on, each edit is
recorded as a real tracked insertion/deletion inside the document's native revision model. Saves the
tracked version, then accepts all changes and saves a clean version. This is the correct/preferred
path but depends on the UNO bridge being installed and configured, which is often not the case in a
plain Python environment — if `import uno` fails, this returns `False` immediately.

**2.12b — python-docx fallback (visual only, NOT real track changes)**
`document_processor.py:DocumentProcessor.apply_changes`: applies changes highest-confidence-first,
removing overlaps; redlined output splits each paragraph into before/strikethrough-red-old-text/
underline-green-new-text/after runs — **this is purely visual formatting**, not Word's native
`w:ins`/`w:del` revision XML. Word will display the colored/struck text but "Accept All Changes"
won't do anything with it, and it won't appear in the Reviewing pane as a trackable revision. Clean
output does an in-place text replace that collapses run-level formatting from the middle of the
sentence into whatever formatting the paragraph's first run had.

Then: **PII reconstruction** (`reconstruct_pii_in_docx`) restores real PII into both output DOCX
files — this happens only on the final applied documents; everything upstream (AI prompts, audit
logs) only ever saw redacted text. **PDF generation** shells out to
`libreoffice --headless --convert-to pdf` for both clean and redline versions (staggered by 1s sleep
to avoid two concurrent headless instances colliding).

## 2.13 Step 13 — Download — `GET /api/job/{id}/download/{type}` [LOCAL CODE]
Streams the requested output file (`redline_docx|clean_docx|redline_pdf|clean_pdf`).

## 2.14 Step 14 — Multi-pass rerun — `POST /api/job/{id}/rerun` [LOCAL CODE orchestration, triggers a fresh AI pass]
Takes the previous pass's **clean docx output** (already has PII reconstructed, accepted changes
baked in), sets it as the new input, and re-runs the entire pipeline from Step 1 — meaning a fresh
extraction, a **fresh PII redaction** (new `pii_mapping`, overwriting the old one), fresh clause
fetch, fresh rules pass, and a fresh OpenAI evaluation call against the now-improved document,
looking for any remaining or newly-visible deficiencies. Capped at 3 total passes.

## 2.15 Job status state machine (exact values)
`queued` → `extracting_text` → `redacting_pii` → `fetching_clauses` → `applying_rules` →
`evaluating` → `validating` → `resolving_changes` → `verifying_provenance` →
`preparing_presentation` → `awaiting_selection` → (user calls `/apply`) → `complete` →
(optional `/rerun`, up to pass 3) → `queued` again. Any exception at any point → `error`.

## 2.16 Confidence/tier taxonomy
`"exact"` (rules engine, or cascade tier 1) → `"fuzzy"` (cascade tier 2, ≥0.90 similarity) →
`"full_clause"` (cascade tier 3, whole clause substituted, clauses ≤200 chars only) → `"manual"`
(cascade tier 4, or anything that failed provenance re-verification) — manual items always require
attorney judgment and are never auto-applied.

## 2.17 External dependencies / secrets
- **OpenAI**: `gpt-4o`, `temperature=0.0`, `max_tokens=16000`. Key from `openai_api_key.txt`
  (plaintext file next to `app.py`) or `OPENAI_API_KEY` env var.
- **SQL Server** via `pymssql` (env vars `DB_SERVER/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`; default
  password is blank — a real deployment must set this) with automatic, permanent-for-the-session
  fallback to **SQLite** (`provisions.db`) if the SQL Server connection fails at all.
- **LibreOffice/soffice**: invoked twice — plain subprocess for PDF conversion, UNO socket bridge
  for real track changes. Both assume `libreoffice` is on `PATH`.
- Filesystem: `JOBS_DIR` (all job artifacts — upload, working copies, outputs, audit log),
  `STATIC_DIR` (frontend), `BLACKLIST_DIR`, `WHITELIST_PATH`.
- **No auth, CORS wide open** — must be closed before any AWS exposure beyond a private VPC.

---

# CROSS-TOOL NOTES FOR THE AWS RE-ARCHITECTURE

1. **PII redaction is NOT symmetric between the two tools today.** The redline tool redacts PII
   before the AI call (`redacted_text` is what OpenAI sees) and only reconstructs it locally into
   the final output document. The summary tool's PII scan is display-only — it deliberately sends
   full unredacted text to OpenAI because it needs to extract exactly those fields (names, dollar
   figures, addresses ARE the data being extracted). This is a real, not cosmetic, difference and
   needs an explicit decision before AWS: either (a) the summary tool's AI call is not something
   that can move to a shared "AWS never sees raw PII" boundary without a real redesign (e.g.
   redact-then-extract-placeholder-then-reconstruct, similar to the redline tool's pattern, which is
   a bigger lift since fields like "Tenant Name" are structurally PII), or (b) the summary tool's
   AWS boundary is scoped differently from the redline tool's, and that's stated explicitly in
   whatever data-handling documentation goes to large enterprise customers' security teams.

2. **Verification/validation in both tools is deterministic code, not a second AI call.** Provenance
   verification (redline) and source-position verification (summary) are both pure string/regex/
   fuzzy-matching checks. This is a real strength — carry it forward unchanged. The AI is never
   trusted to self-certify; code always re-checks the AI's claims against ground truth (clause DB
   for redline, source document text for summary) before anything reaches a human or a final
   document.

3. **The summary tool's human-verification pause currently blocks a live thread for up to an hour.**
   This is the resume-in-place pattern discussed earlier as not viable at scale (thread/connection
   exhaustion, no resilience to restarts, poor UX for batch processing). The redline tool has no
   equivalent pause — its human review step (accepting/editing proposed changes) happens through
   normal request/response after the job is already `awaiting_selection`, which is a better-shaped
   pattern and validates the "Option C now, Option B later" recommendation discussed earlier for
   summary verification.

4. **Job state persistence differs today**: summary tool persists to `meta.json` on disk (survives
   a process restart in principle, though not multi-instance-safe as written); redline tool is
   pure in-memory (`jobs: dict`, lost entirely on restart). Both need to move to DynamoDB (or
   equivalent) for the AWS version regardless — this doc is recording the current state, not
   proposing to keep either as-is.

5. **Neither tool has authentication on its API today.** Both assume a trusted localhost/single-user
   context. This is fine for the standalone desktop tools but must be addressed (API keys, mTLS, or
   signed requests between SeedJura's server and AWS) before any AWS deployment.

6. **LibreOffice is a hard dependency for both tools' document-output steps** (redline's real
   track-changes and PDF generation; summary likely needs it too for any PDF export, though the
   traced summary pipeline above only emits DOCX/XML/JSON directly). This confirms the earlier
   recommendation that LibreOffice-dependent steps run in a container (Fargate), not Lambda.

7. **Both tools already produce structured audit trails** (redline's `{job_id}_audit.json`; summary's
   `qa_feedback.json` + verification `report` dict) — these map cleanly onto the "hand a large
   enterprise customer's security/compliance team a clean execution history" requirement discussed
   earlier for Step Functions.


---

# PART 3 — PARTY IDENTITY PROTECTION & DOCUMENT-SET DESIGN (AWS RE-ARCHITECTURE)

This section captures decisions made after the pipeline trace above, addressing the privilege
concern that unredacted party-identifying information must never reach AWS/AI for either tool. It
supersedes the "Cross-Tool Notes" Option 1/2/3 framing in favor of a concrete design: **tokenize
before any AI call, resolve identity with code first, and escalate to a human only when code
genuinely cannot resolve it.**

## 3.1 Why Option 3 ("transient data, documented exception") was rejected

Sending unredacted contract text to a third-party AI processor (even framed as "transient" on our
side) creates real attorney-client privilege and confidentiality exposure — this is a live legal
concern, not a hypothetical one, and retention policy on the AI provider's side is a separate,
uncontrolled variable regardless of how "transient" our own handling is. Decision: **no
identifying information may leave SeedJura's server in any form, for either tool, full stop.** No
exception, no reliance on a third party's data retention terms.

## 3.2 Scope: what gets tokenized

**Must be tokenized before any AWS/AI call reaches it:**
- The two legal parties' identity — names and addresses (e.g. Landlord/Tenant for leases,
  Buyer/Seller for PSAs, or the equivalent two-sided relationship per agreement type)
- SSNs, EINs, phone numbers, emails, account numbers — **these identify a specific person/entity
  even without a role label attached**, so they are in scope regardless of which party they belong
  to. (Earlier framing that these "don't reveal who the tenant is, so they're safe" was wrong — the
  bar is "does this identify a specific person or entity at all," not "does this specifically
  reveal a role.")

**Does NOT need tokenizing — flows to AWS/AI as-is:**
- Dollar amounts, dates, and all substantive clause/contract language — needed for interpretation,
  does not identify anyone.
- Minor/non-party roles (notaries, witnesses, brokers mentioned in passing) — deliberately out of
  v1 scope. Rationale: these individuals are not bound by the agreement's obligations, so they are
  not "affected by the document" in the same sense the two legal parties are. **This is an accepted
  scope boundary, not an oversight** — see 3.6 for real-world counterexamples (guarantors, lenders,
  notice recipients) that push against this boundary and are deferred, not solved, for v1.

## 3.3 Resolution mechanism (local, code-first)

1. **Search the full text of the origin document (see 3.4 for which document that is), not a
   length-limited window.** Real lease recitals can appear 1500-2000+ characters in, after a table
   of contents — confirmed against an actual lease document (see 3.7). A fixed "first 3000-5000
   chars" window is not reliable.
2. **Primary pattern: defined-term parenthetical.** Search for the recital construction
   `<Entity Name> ... ("Landlord"/"Lessor")` and `<Entity Name> ... ("Tenant"/"Lessee")` (or the
   equivalent pair for other agreement types), walking backward from the parenthetical to capture
   the preceding capitalized entity name, handling `LLC/Inc/Corp/L.P./Trust` suffixes and filler
   text ("a Delaware corporation," "whose address is:"). Confirmed reliable against every real
   Lease Agreement, Amendment, Resolution Agreement, and Settlement Agreement examined (see 3.7).
3. **Address correlation**: once a name is resolved, its address is usually adjacent in the same
   recital or in a structured "Notices" clause. Confirmed present in the Resolution Agreement
   example (full address given for both parties in the recital itself).
4. **Signature-block cross-check**: an independent second read of the same fact, used as a
   corroboration/confidence gate, not a first-choice source.
5. **Confidence gate — bias conservative.** Silent auto-accept requires the recital match AND
   signature-block corroboration to agree. Recital-only (no corroboration found) is treated as a
   request-verification case, not an accept case — a wrong silent acceptance here is worse than an
   extra human confirmation, because this is specifically the fact the whole design exists to
   protect.

## 3.4 Which document is authoritative for identity — the origin-lease-first model

**Confirmed by direct inspection of a real 50+ file shopping-center lease portfolio (see 3.7) that
not every document type in a real document set contains a recoverable party name:**

- **Amendments, Resolution Agreements, Settlement Agreements**: contain the recital pattern
  directly and reliably.
- **Omnibus Agreements**: may reference Landlord only as "the landlord entities listed on
  Exhibit G" — the actual name is not in the extracted text at all, by document design.
- **Tenant's Estoppel Certificates**: refer back to "the Landlord named therein [the original
  Lease]" without restating the name — structurally about a third party (a lender), not about
  restating the two original parties.
- **Internal system exports (JDE Change Request) and structured notice forms (Tenant Change
  Notice)**: contain the tenant's name as a bare field value with no "Tenant"/role language to
  anchor on, and may contain unrelated real names (an internal employee who submitted the form).
- **Some documents have no extractable text at all** (e.g. a flat scan with no OCR layer) and need
  the existing OCR fallback; if OCR still yields nothing, the document is included in the set with
  content unprocessed (see 3.6, gap 3).

**Design consequence:** party identity must be resolved **once**, from the document most likely to
state it cleanly — the origin Lease/Agreement (oldest by execution date, or by document-type
signal if dates are unavailable) — and then propagated to every other document in the set by
**searching for the already-known name/address**, not by independently re-deriving identity from
each document's own structure. Searching for a known string is a strictly easier and safer problem
than extracting an unknown one, and it correctly handles the Omnibus/Estoppel case (no match found
is expected and not an error — see 3.6 gap 1) rather than forcing a brittle universal extraction
pattern to work against document types it fundamentally cannot resolve.

**Newest-document check**: after resolving identity from the origin document, run the same
search/resolution against the newest document in the set to catch assignment/successor changes
(a lease's Tenant can legitimately change via assignment over its lifetime — confirmed in the real
portfolio: Aeropostale's "FIRST AMENDMENT OF LEASE" explicitly documents an assignment to
"Aero OpCo LLC" following a bankruptcy sale). If the newest document names a different party in the
same role with a clear assignment/successor clause, that becomes the current authoritative
identity; the original is retained locally as superseded (useful data, never sent to AWS). If the
newest document disagrees without a clear explanation, escalate per 3.6 gap 2.

## 3.5 Document ordering — how "oldest"/"newest" is determined

Confirmed already implemented and reused as-is: `multi_file.py:sort_documents()` orders documents
by (1) execution date extracted from each document's own text and validated by
`parse_strict_date()` (rejects OCR garbage), (2) amendment ordinal number if stated
("First Amendment," "Second Amendment"), (3) document-type priority as a last-resort tiebreaker.
**This is independent of upload order or file timestamps** — a batch uploaded all at once, or in
any order, resolves to the same chronological sequence, because the signal is read from document
content, not the upload transaction.

## 3.6 Gap handling (v1 scope)

**v1 scoping decision:** a single uploaded folder is assumed to be one document set (one matter/
one lease's history). General-purpose grouping of unrelated documents dropped together in bulk
(e.g. hundreds of unrelated leases in one batch) is explicitly deferred — early users are expected
to be attorneys curating a folder per matter, not portfolio-scale bulk uploads. This assumption
needs revisiting if/when non-attorney, high-volume portfolio users (e.g. property management
companies processing many unrelated tenancies at once) become a real usage pattern.

Within that single-folder-as-one-set assumption, three gap types were identified against the real
portfolio data and need distinct handling — these are not edge cases to defer, they are expected,
regular occurrences within a normal matter folder:

1. **Document has no recoverable party name (Omnibus Agreement, Estoppel Certificate pattern).**
   Expected, not an error. Handling: inherit identity from the folder's resolved origin-document
   identity; do not escalate to human review; log as "inherited, not independently verified" in
   the audit trail so this is visible on review, not silently indistinguishable from a document
   that was actually checked.

2. **Document's extracted party name conflicts with the resolved identity, with no assignment/
   successor clause explaining the difference.** Real gap, not expected. Handling: escalate to the
   existing human-verification-pause mechanism (same async pattern as the handwriting-verification
   pause already built for the summary tool), triggered once per folder for this condition, not
   per document. Given attorneys are the primary early user, surface this as a substantive flag
   ("this document names a different party than the rest of this folder") rather than suppressing
   it — it may indicate a genuine legal fact (an unrecognized assignment) or a filing error (wrong
   document in the folder), either of which the user should see, not have silently resolved for
   them.

3. **Document has no extractable text at all** (e.g. a flat scan with no OCR text layer — confirmed
   present in the real portfolio: a "Change of Address" notice yielded zero extracted text).
   Handling: run the existing OCR fallback first. If still empty, include the document in the set
   (inherit folder identity per gap 1's handling) but flag it distinctly as
   "no text extracted — content not processed" in the job output, rather than letting it silently
   disappear from the set with no record it was ever there.

**Duplicate/version detection (a gap inside the single-folder case, not deferrable):** confirmed
present in the real portfolio — multiple near-identical "LEASE AGREEMENT" files for the same tenant/
suite differing only by a document-management-system version-hash suffix in the filename (e.g.
`... - 18204.pdf` vs `... - 18204 v1 4874-8133-4204.pdf`). Left unhandled, these produce multiple
"documents" with identical (or no) execution dates and no way for `sort_documents()` to distinguish
them, corrupting the ordering the whole identity-resolution design depends on. v1 handling: if two
documents in the same folder share the same document-type classification and the same (or absent)
execution date, treat them as duplicates of one underlying document — keep one (prefer the filename
without a version-hash suffix, as that is typically the final/canonical copy) and flag the rest as
skipped-duplicates in the job output rather than silently processing all copies as distinct
amendments.

## 3.7 Worked example — real shopping-center lease portfolio

The design above was validated against a real ~50-file portfolio (`C:\OneDrive_1_8-24-2026`) — one
shopping center ("Coastland Center") with 6 tenants, each with their own subfolder containing a
full document history: original lease, multiple numbered amendments, extension agreements,
COVID-19 amendments, omnibus agreements, termination notices, resolution/settlement agreements,
estoppel certificates, and internal system exports (JDE change requests, tenant change notices).

Findings from direct text extraction (PyMuPDF) against this set:
- Filenames in this portfolio follow a disciplined convention
  (`{TENANT} - {PROPERTY} - {SUITE} - {DOC TYPE} - {ID}[version hash]`) — this is a **best case**,
  not a baseline to design around; messier/inconsistent naming (or no naming convention at all)
  must still work, since filename convention is a landlord-specific filing habit, not a guarantee.
- The recital-based party-name pattern (`<Name> ... ("Landlord")` / `("Tenant")`) was confirmed
  present and extractable in: the original Lease Agreement (though positioned well past a short
  window — after a full table of contents), every numbered Amendment, the Resolution Agreement,
  and the Settlement Agreement.
- The pattern was confirmed **absent** (by document design, not extraction failure) in: the Omnibus
  Agreement (Landlord named only via an exhibit reference) and the Tenant's Estoppel Certificate
  (refers back to the original Lease rather than restating the name).
- Individual (non-corporate) real names were confirmed present in document types beyond the two
  core parties: guarantors named and sued individually in the Settlement Agreement recital, a
  lender's general counsel named in the Estoppel Certificate, individual notice recipients named in
  the Termination Notice, and an internal employee's name in the Tenant Change Notice. **These are
  out of v1 scope per the "two legal parties only" decision (3.2) but are a real, confirmed
  exposure the design deliberately defers, not one that doesn't exist** — worth revisiting once
  usage moves beyond the initial attorney-curated-single-matter use case.
- One document (a "Change of Address" notice) yielded no extractable text at all, confirming the
  OCR-fallback dependency (gap 3 in 3.6) is a real, not hypothetical, requirement.
- Duplicate version-hash files were confirmed present for one tenant (four near-identical
  "LEASE AGREEMENT" files differing only by a trailing document-management-system hash),
  confirming the duplicate-detection requirement (3.6) is real, not hypothetical.

## 3.8 Resulting per-tool workflow (summary)

**Summary tool:**
1. Local: ingest folder (assumed one document set), OCR fallback as needed.
2. Local: `sort_documents()` to find oldest (origin) and newest (current) documents.
3. Local: resolve party identity from the origin document (recital + signature-block
   cross-check, full-document search, conservative confidence gate); check the newest document for
   assignment/successor changes. Escalate to human-verification-pause only if resolution is
   ambiguous, missing on the origin document itself, or conflicting without explanation — once per
   folder, not per document.
4. Local: propagate resolved identity across the rest of the set by searching each document's full
   text for the already-known name/address strings (per 3.4) — not by re-deriving identity per
   document. Apply gap handling (3.6) for documents where no match is found, where a conflicting
   name is found, or where no text is extractable. Apply duplicate detection before/alongside
   ordering.
5. Local: tokenize all occurrences of both parties' names, addresses, and identifying data (SSN/
   EIN/phone/email/account numbers, per 3.2) across every document in the set. Build a
   document-set-scoped mapping table, held locally only.
6. AWS: Call 1 (extraction), Call 2 (interpretation), Call 4 (QA) all run against fully tokenized
   text — safe to run at AWS now that identifying information never reaches this hop.
7. Local: existing completeness check and handwriting-verification pause (a separate, unrelated
   concern from party identity) run against the returned field data.
8. Local: user reviews the output (confidence-flagged inline, per the earlier Option C decision —
   not a mandatory gate).
9. Local: reconstruct real party names/addresses/identifiers from the mapping table; generate
   DOCX/XML/JSON output.

**Redline tool:** unchanged in shape from the existing pipeline (already redacts before any AI
call) — open item: whether `redaction.py`'s current generic `"PERSON"`/`[REDACTED]` tagging should
be upgraded to the same role-aware, origin-document-resolved tokenization described above, since
the same privilege concern applies equally to a redlined contract revealing who is negotiating with
whom. Not yet decided — carried forward as an open item alongside the two other open items already
tracked (document-set grouping beyond the v1 single-folder assumption; signatory/individual-name
scope beyond the two core legal parties).
