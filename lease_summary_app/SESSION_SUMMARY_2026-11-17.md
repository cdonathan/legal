# Lease Summary App — Session Summary (Nov 17-18, 2026)

Work done this session: a real-world accuracy test of the multi-file lease
pipeline against an attorney-reviewed deal, and five rounds of bug fixes
driven directly by comparing our output to that attorney's final, approved
lease summary (the "gold standard").

Committed as `50408cb`, `ab42d30`, `c5f49b4`, `ae07028`, `d365dd6` on branch
`lease-summary-multi-file`, pushed to `origin/lease-summary-multi-file`.

## Test setup

**Documents** (Avenue Recovery Center / Norfolk, VA — 5 files):
`Fully Executed Norfolk Avenues Lease.pdf`, `Norfolk - Amendment 1 to
Lease.pdf`, `Norfolk.Entity Guaranty.pdf`, `Norfolk.Individual Guaranty.pdf`,
`Commencement Date Notice.pdf`.

**Gold standard:** an attorney-reviewed, final-approved lease summary for
this exact deal (`Geneve_SeedJura_template.txt` / `Geneve_Avenue_Recovery
.docx`, provided by the user). A second, *earlier draft* critique document
for the same deal also existed and gave different answers for a couple of
OPEX fields — that earlier draft was superseded by the attorney's own final
version and should **not** be treated as authoritative if it resurfaces.

**Method:** ran the actual `/api/upload-folder` pipeline end-to-end
(including the human-verification step) on real documents, downloaded the
generated `.docx`, and diffed every field against the gold standard's
value *and* section citation — not just "did a value appear."

## 1. Date-field template mapping (pre-existing, fixed first)

**Bug:** in `SeedJura_Lease_Summary_FORM.docx`, row 10 (Commencement Date)
was bound to the `Date_Lease` placeholder, row 11 (Effective Date) to
`Amendment_Effective_Date`, and row 12 (Termination Date) to
`Date_Termination` — none of which matched the row labels.

**Fix:** rebound to `Date_Commencment` (row 10), `Date_Lease` (row 11), and
`Date_Expiration` (row 12). Verified against the gold standard
(05/01/2024 / 02/12/2024 / 04/30/2039).

## 2. Truncation limit and output token budget

**Bug:** document text was truncated at 80,000 characters before being sent
to the AI (`engine.py`, `lease_summary_tool.py`). For this lease (~189,000
chars), that cut off the document ~56% through, silently losing the
Assignment, Estoppel, SNDA, Signage, and Purchase-Option sections — the AI
never saw that text at all. `max_tokens` was also capped at 16,000, just
under GPT-4o's real 16,384-token ceiling, which clipped some larger
responses once the truncation fix let more content through.

**Fix:** raised truncation to 500,000 chars and `max_tokens` to 16,384 in
both `engine.py` and `lease_summary_tool.py`. Also added multi-occurrence
anchor-phrase disambiguation (`_find_all_ai_anchor_positions()`) — a short
anchor phrase can match a document's Table of Contents heading as well as
the real clause, and the code was blindly taking whichever occurrence came
first.

## 3. Document misclassification (the root cause of this session's work)

**Bug:** `classify_document()` in `multi_file.py` looks for the literal
phrase `"LEASE AGREEMENT"` to identify the origin lease document. This
lease's own preamble says "This Lease ... is dated ..." — it never uses
that literal phrase — so it fell through to `doc_type: "other"` and got a
restricted, low-field-count secondary extraction pass instead of full
origin-document treatment. Meanwhile the short "Commencement Date Notice"
document's third-party citation ("...Lease Agreement (the "Lease") dated
February 12, 2024...") *did* contain the phrase, so **it** won the origin
`"lease"` slot instead — displacing the real lease.

**Consequence:** every Section C field that should have come from the real
lease (Tenant Insurance, OPEX, Utilities, Landlord/Tenant Repair
Obligations, Assignment, Sublease, Holdover, Estoppel, SNDA, Signage) came
back `None`, because the document that actually contains that language was
never given the full extraction pass.

**Fix** (`multi_file.py`):
- Added a self-referential-preamble signal (regex for `"THIS LEASE ... IS
  DATED"`) so a lease is recognized by its own opening declaration, not
  just the literal "LEASE AGREEMENT" phrase.
- Added a dedicated `"commencement_notice"` doc_type for Commencement Date
  Notice/Confirmation documents, so they stop impersonating the origin
  lease.
- Added one narrow, named exception to the existing date-field merge pin:
  `Date_Commencment` is normally locked to the origin lease document only
  (`LEASE_ORIGIN_ONLY_FIELDS`), but a `commencement_notice` document is
  also allowed to supply it — the lease's own Commencement Date clause is
  often purely conditional ("the date Landlord delivers possession"),
  while the confirmation document states the actual resolved calendar
  date. See `COMMENCEMENT_DATE_CONFIRMATION_TYPES`.
- `field_variants.py`: added a "Commencement Date Confirmation" display
  label for the new doc_type.

## 4. Retry pass clobbering correctly-merged values

**Bug (found immediately after fixing #3):** once the real lease was
correctly classified, `Date_Commencment` started showing the lease's own
conditional definition again instead of the confirmed date — a regression
introduced by the fix above. Root cause: the multi-file completeness retry
pass (`app.py`) re-reads *only* the origin lease document's text for any
field flagged by per-document verification, and unconditionally overwrites
whatever the merge step had already resolved, even when that resolved
value correctly came from a **different** document. The same bug also hit
`Guaranty_Term` (clobbered with unrelated lease text instead of the
Guaranty Agreement's own language) once it got flagged in a later run.

**Fix** (`app.py`): before running the retry call, excluded any field
whose current merged value's source document isn't the one about to be
re-queried. Being flagged by `verify_and_expand()` (which runs per-document,
*before* the merge) doesn't mean the final merged value is wrong.

## 5. Field-level extraction accuracy (net lease, TI concession, guarantor)

Five more field-level issues found by continuing the gold-standard
diff, all fixed via `agreement_types/lease/config.json` (field
descriptions / `retry_hints` / `expected_fields` / the amendment sub-type's
own AI instructions) and `field_anchors.json` (both the per-type copy and
the legacy top-level copy):

- **OPEX_Inclusion** — was matching an unrelated Right-of-First-Offer
  clause. A net ("NNN") lease usually states OPEX inclusion as an
  "Additional Rent" provision right after Base Rent, not an itemized list.
  Taught the prompt to look for and prefer that clause.
- **Tenant_Share_Percentage / Tenant_Share_Amount** — returned `None` on a
  net lease with no stated percentage; now inferred as `"100% (Net
  Lease)"` from the lease's own "Net Lease" provision.
- **Tenant_Allowance_Additional ("Additional TI Funds")** — the field
  description only described a per-square-foot allowance, so a one-time
  landlord concession tied to an amendment ("in consideration for the
  deletion of Section X, Landlord shall pay Tenant $___") wasn't
  recognized — and was easy for the AI to overlook among ~90 other fields
  in one batched amendment extraction call even after the description was
  broadened. Also had to add it explicitly to the amendment sub-type's own
  "fields commonly IN an amendment" instruction before it was reliably
  picked up.
- **Rent_BaseRent_Monthly** — returned `None` whenever a lease states only
  an annual figure (e.g. in a Schedule) paid in 12 equal monthly
  installments, because the system's strict "verbatim text only"
  extraction rule blocked any arithmetic. Added a narrow, explicit
  exception letting this one field compute Annual ÷ installment count,
  clearly labeled as a calculation.
- **Guarantor_StReg / Guarantor_Type ("guarantor conflation")** — when a
  lease has both an Entity and an Individual Guaranty and the Entity
  Guaranty is later terminated, `Guarantor_Name` correctly updates to the
  surviving individual via latest-wins merge, but `StReg`/`Type` kept
  showing the terminated entity's state/type. Cause: the individual
  guaranty's own extraction correctly left those fields blank (a person
  has no state of registration), and in this merge system an empty value
  means "defer to whatever the previous document said," not "clear it" —
  so the stale entity data was never actually overridden. Fixed by having
  an individual guarantor's extraction return the literal, non-skippable
  string `"N/A (Individual)"` instead of blank, so it actually replaces
  the stale value during merge.

## Current state

All of the above is verified against the attorney's gold standard in the
actual generated `.docx`, not just the API response — including a full
re-run of the pipeline after each fix to make sure no earlier fix
regressed. No open, confirmed bugs remain from this test case. Two
cosmetic (non-factual) differences from the gold standard remain by
design choice, not bug:
- `OPEX_Exclusion` quotes the raw carve-out clause verbatim; the gold
  standard summarizes the same clause as `"None"` (no real exclusions).
- `Guaranty_Term` quotes the full verbatim guaranty clause; the gold
  standard shortens it to `"Entire Term"`. Same underlying fact.

If a future conversation hits an extraction gap on a **new** lease/folder:
start by comparing the generated `.docx` against whatever reference
document the user provides, field-by-field with section citations — not
just presence/absence of a value — the same way this session worked. Most
of the bugs above were invisible until compared against a real attorney
answer; the API returning *something* for a field doesn't mean it's right.
