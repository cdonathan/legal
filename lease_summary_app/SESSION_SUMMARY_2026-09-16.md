# Lease Summary App — Session Summary (Sept 16-17, 2026)

Work done this session on the multi-file lease summary pipeline, focused on
fixing date-attribution bugs found in a real-world test run (ALDO/Coastland
Center folder — 11 documents: original lease + 7 amendments + change
request + omnibus agreement + termination notice), and adding a
human-in-the-loop verification step for hand-written/uncertain text.

Committed as `b8d5444` on branch `lease-summary-multi-file`, pushed to
`origin/lease-summary-multi-file`.

## 1. Document classification fixes

**Bug:** `classify_document()` checked the generic `"LEASE AGREEMENT"` text
signal before more specific signals (OMNIBUS, TERMINATION, etc.). Documents
like an Omnibus Agreement routinely reference "the Lease" in their own
recitals, which tripped the generic check and caused them to be
misclassified as `doc_type: "lease"` — competing with the real lease
document and letting the Omnibus's own date silently overwrite the real
lease's date during merge.

**Fix:** reordered the checks in `multi_file.py`'s `classify_document()` so
specific types are checked first; the generic lease signal is now the last
resort.

## 2. AI-based document ordering

**Bug:** determining which document is the original lease and which
amendment is "latest" relied on regex-matching ordinal words in filenames
("First", "Seventh", etc.). This breaks down for two reasons:
- Every amendment's own recital paragraph restates the *entire* prior
  amendment history ("...as amended by a First Amendment... a Second
  Amendment..."), so a naive ordinal search over document *text* picks up
  "First Amendment" even when reading the Seventh Amendment.
- Filename conventions vary a lot between landlords/law firms (e.g.
  "Extension and Fourth Amendment" vs. "Amendment No. 4" vs. date-only
  filenames).

**Fix:** added `classify_documents_with_ai()` in `engine.py` — a small,
cheap AI call that reads just the filenames (+ a short header excerpt) and
reasons about chronological ordering the way a person would. Falls back to
the old filename-heuristic if the AI call fails for any reason. Correctly
identified, for the ALDO folder, that the Termination Notice (not the
Seventh Amendment) was the actual "latest" lease-related event.

## 3. Date-field attribution bugs (the core problem this session)

Several related bugs, all with the same underlying pattern: fields that
describe a **fixed historical fact tied to one specific document** were
being treated as ordinary "latest-wins" merge fields, so a later document
mentioning the same date/fact (even correctly) could silently override the
correct attribution.

- **`Date_Lease` recital leak:** amendments' recital paragraphs restating
  the lease's history ("Under the lease dated July 30, 2007...") were
  sometimes extracted as if they were the CURRENT document's own
  `Date_Lease`. Fixed by rewriting the field's AI-facing description to
  explicitly exclude the recital paragraph, and treating `Date_Lease` as
  belonging ONLY to the document classified as `doc_type == "lease"`
  (`LEASE_ORIGIN_ONLY_FIELDS` in `multi_file.py`).
- **New field `Amendment_Effective_Date`:** amendments have their OWN
  effective/signing date (e.g. "THIS SEVENTH AMENDMENT... is made and dated
  November 22, 2019") which is a completely different fact from the
  original lease's date. Added as its own tracked field so it's never
  confused with `Date_Lease` or pulled from the recital paragraph.
- **`Date_Commencment` amendment override:** an amendment restating the
  original commencement date (e.g. in a term-extension clause) was
  overriding the lease's own attribution for that field, even when the
  value was identical — mislabeling the source. Fixed by adding
  `Date_Commencment` to `LEASE_ORIGIN_ONLY_FIELDS` too — it's now pinned to
  the lease document exclusively, same as `Date_Lease`.
- **Normalized-date badge disagreeing with the displayed value:**
  `merge_normalized_dates()` did its own INDEPENDENT latest-wins scan over
  every document's raw normalized dates, which could name a different
  "winning" document than `merge_fields()` had already chosen for that
  field's displayed text. Fixed by making `merge_normalized_dates()` derive
  each field's date badge from the SAME winning document that
  `merge_fields()` selected (passed in as `merged_fields`), so the badge can
  never disagree with the value shown next to it. Also handles
  human-verification corrections (which append `" (human-verified)"` to
  `current_source`) by using the corrected value directly.
- **`execution_date` derivation for sorting/history:** amendments now use
  their own `Amendment_Effective_Date` (falling back to `Date_Lease`/
  `Date_Commencment` only if that's empty) to determine sort order and
  history attribution, instead of the original lease's date fields.

## 4. Handwritten-date detection and OCR

**Bug:** the existing `_fix_handwritten_dates()` (in `lease_summary_tool.py`)
only caught garbled OCR tokens in the pattern `"<garbage> day of <Month>"`.
Two real-world cases slipped through:
- A different template phrasing: `"is ___, 20__"` / `"...is made and dated
  ___, 20__ (the "Effective Date")"`.
- A TRUE BLANK GAP — some PDFs have literally zero characters where a
  hand-written date should be (not even garbled OCR noise), which no
  garbled-token pattern could ever match.

**Fix:** extended the detection regex to catch both the blank-fill template
phrasing (including a fully empty blank) and anchored a second pattern on
the reliable `(the "Effective Date")`-style label that follows these dates
in practice, catching cases the day/comma/year pattern missed.

Also added a **targeted re-OCR cross-check**: when a page's extracted text
is flagged as containing a suspect hand-written date, `ingest_document()`
now re-renders just that page at 400 DPI and runs a fresh Tesseract pass,
appending the result as a labeled cross-reference block in the document
text. This is often far more legible than whatever OCR/text layer the PDF
shipped with. The AI prompt (`engine.py`) was updated to prioritize this
cross-check and any cross-document restatement of the same date over
guessing, and to explicitly return `"NEEDS VERIFICATION"` rather than
fabricate a plausible-looking date when it truly can't resolve one.

## 5. Human verification UI (new feature)

Per explicit request: when AI or code recognizes hand-written text, the
user should see the source image, the AI's derived reading, a checkbox to
confirm it, and a text box to correct it if wrong — as a step between
analysis and report generation.

**Backend (`app.py`, `lease_summary_tool.py`):**
- `find_snippet_screenshot(file_path, snippet)` — locates a text snippet in
  a PDF and returns a cropped PNG of the surrounding page region. Rejects
  degenerate search candidates (e.g. a bare comma left over after stripping
  `[handwritten...]` markers) and candidates that match implausibly many
  locations on one page, to avoid cropping around an unrelated match.
- `_detect_handwriting_touched_fields()` — flags a field if ITS OWN
  extracted span overlaps (within a few characters) a `[handwritten...]`
  marker in the source text — whether the AI resolved it confidently or
  not. Deliberately narrow-windowed so nearby-but-unrelated fields (e.g.
  "corporation" printed a few words before a hand-filled date blank) aren't
  swept in.
- `_build_verification_items()` — builds the per-field review payload:
  label, AI's value, whether the AI was confident, a plain-language
  instruction sentence, and a screenshot URL. Uses the ALREADY-COMPUTED
  source position (from `verify_and_expand()`) to build the screenshot
  search anchor from the literal document text, rather than the AI's value
  (which can be slightly paraphrased even when told not to be, breaking
  exact-text search).
- Pipeline pause/resume: the background job thread blocks on a
  `threading.Event` once flagged fields are found, sets
  `job_meta["status"] = "needs_verification"`, and resumes when
  `POST /api/verify/{job_id}` is called (or a 1-hour timeout elapses).
  Two checkpoints exist per pipeline (single-file and multi-file): one
  right after the main extraction/verify pass, and a second after the
  targeted retry pass (since `ai_retry_fields()` reads raw text directly
  and has no handwriting-resolution guidance of its own).
- New endpoints: `POST /api/verify/{job_id}` (submit corrections, resumes
  the paused thread), `GET /api/verify-screenshot/{job_id}/{field_name}`
  (serves the cropped PNG).
- `AgreementType.get_display_labels()` — builds a short human-readable
  label per field name from the UI `sections` config, for display on the
  verification card (previously the long AI-prompt field description was
  shown by mistake).

**Frontend (`static/index.html`):**
- New "Please Verify Hand-Written Text" step between processing and
  preview. Each flagged field shows: an instruction sentence (what to look
  for, in which document, what format to type), the cropped screenshot, the
  AI's reading with a confirm checkbox (checked by default) when confident,
  or a required text box with no checkbox when the AI outright failed, and
  a "leave blank to keep flagged" note.
- Poll loop (`pollJobStatus`) branches on `status === 'needs_verification'`
  to show the review form instead of the progress spinner; submitting or
  skipping resumes polling.
- Poll loop also now tolerates a few consecutive failed polls before
  giving up (see race-condition fix below), instead of failing the whole
  job on one bad read.

## 6. Reference Provisions formatting bug

**Bug:** every bare-fact field (address lines, city, zip, email, attn name)
was individually tagged with its section/document reference in the
Interpretation column, so a 5-line tenant address rendered as 5 disconnected
fragments each suffixed `(REFERENCE PROVISIONS)` — noisy and hard to read
as an address block.

**Fix:** `format_field_interpretation()` / `format_interpretation()` /
`build_field_variants()` now accept a `suppress_section` flag; fields in the
agreement type's `short_fields` set (already used elsewhere for
verification purposes) skip the section tag entirely.

## 7. meta.json race condition

**Bug:** `_save_meta()` wrote `job_dir/meta.json` with a plain
`open(path, "w")` + `json.dump()`, which truncates the file before writing.
Since the background pipeline thread saves meta dozens of times per job
while the frontend polls `/api/status/{job_id}` every ~1.5s on a separate
thread, there was a real window where a poll could read a
truncated/empty file and fail with "Lost track of this job."

**Fix:** `_save_meta()` now writes to a temp file and atomically renames it
into place (`os.replace`), so a concurrent read always sees either the old
or the fully-written new content, never a partial write. `_load_meta()`
also now tolerates a decode failure by returning `None` instead of raising.

## Known limitations / follow-ups not yet done

- The human-verification pause state lives only in server memory
  (`threading.Event` in a module-level dict) — restarting the server kills
  any in-progress paused job, even though its `meta.json` still shows
  `needs_verification`. Not persisted/resumable across restarts.
- The verification pause only checks the CURRENT/merged value per field,
  not every historical value across every document. If an older amendment's
  date is garbled but a later document's value "wins" the merge, the older
  garbled value sits unflagged in that field's Raw history.
- Re-OCR of severely degraded handwriting is not perfectly reliable (e.g.
  one case OCR'd "November 22, 2019" as "Novela 22, 2024" — the AI
  correctly refused to guess and flagged it for human review instead, which
  is the intended fallback behavior, but OCR accuracy on bad handwriting
  remains inherently limited).
- Output filename mangling: `Path(folder_path).name` on a Windows-style
  path processed on Linux doesn't split on backslashes the way it would on
  Windows, producing malformed filenames like
  `C:\OneDrive_1_8-24-2026\ALDO_multi_data.json`. Flagged but not fixed
  this session (deprioritized in favor of content-correctness fixes).
- Two other cataloged-but-unaddressed issues from the original quality
  review: a hallucinated section label ("LATEST AMENDMENT" isn't a real
  section heading), and an unconfirmed row/section label mismatch (row
  tagged "First Amendment" but section text says "THIRD AMENDMENT OF
  LEASE").
