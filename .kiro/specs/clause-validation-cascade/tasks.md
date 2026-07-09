# Implementation Plan: Clause Validation Cascade Engine

## Overview

This plan implements the Clause Validation Cascade Engine as a new `ai_attorney_v3/` project. Tasks are ordered by dependency — foundational modules first (models, utilities, data access), then core logic (cascade, rules, evaluation), then integration (pipeline, API, UI), and finally testing.

## Tasks

- [x] 1. Create project scaffolding: `ai_attorney_v3/` directory structure, `config.py` with env vars (DB_SERVER, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, OPENAI_API_KEY), `requirements.txt` with pinned deps (fastapi, uvicorn, python-multipart, python-docx, openai, pymssql, pdfplumber), `models.py` with all dataclasses (ClauseRecord, AIFinding, CascadeResult, ProposedChange, ContextWindow, AuditEntry, VerificationResult), launcher scripts (start.bat, start.sh), and copy redaction_whitelist.txt + blacklists/ + provisions.db from existing standalone app. **Requirements: 10**
- [x] 2. Create `text_utils.py` with normalize_whitespace(), clean_clause_html() (strip HTML tags, decode entities, replace template placeholders with ___, normalize whitespace), locate_text_in_document() (multi-strategy: exact → normalized → fuzzy at threshold), and find_original_span() (map normalized positions back to original char positions). Create `context_extractor.py` with extract_context(document_text, match_start, match_end, word_count=150) that returns 150 words before + match + 150 words after with word-boundary snapping. **Requirements: 8, 5**
- [x] 3. Create `clause_repository.py` with ClauseRepository class: get_clauses_by_form_type(form_type) queries SQL Server first then falls back to SQLite on failure, get_clause_by_id(clause_id, form_type) retrieves single clause by position index, get_clause_text(clause) calls clean_clause_html to produce clean_text. Handle case-insensitive form_type and column name variations (PROV_DESC vs prov_desc vs proV_DESC). Add connection health check with automatic failover logging. **Requirements: 2, 11**
- [x] 4. Create `rules_engine.py` with RulesEngine class: minimum rules "attorney's fees" → "reasonable attorney's fees", "best efforts" → "commercially reasonable efforts", "take all steps" → "take commercially reasonable steps". apply(document_text) runs all regex patterns, returns ProposedChange list with source="rules_engine", 150-word context via extract_context(), and document_position char offset. **Requirements: 7**
- [x] 5. Create `evaluation_module.py` with EvaluationModule class: build_evaluation_prompt() constructs prompt sending clause IDs + text, instructing AI to return only references (clause_id, document_section, issue, suggested_portion) — never legal language. Batch clauses in groups of 25 per API call. evaluate() calls GPT-4o at temperature=0.0, parses JSON into AIFinding list. validate_response() rejects findings where document_section not in document or suggested_portion not in referenced clause. Log boundary violations. **Requirements: 1, 11**
- [x] 6. Create `cascade_engine.py` with CascadeEngine class and implement _tier1_exact(suggested, clause_text): normalize whitespace on both, check if suggested is substring of clause_text, map back to original clause positions for actual substring, return CascadeResult with confidence="exact" and char_offset. Log pass/fail in audit trail. **Requirements: 3**
- [x] 7. Implement _tier2_fuzzy(suggested, clause_text, threshold=0.90) in cascade_engine.py: sliding window using difflib.SequenceMatcher with window sizes 80%-120% of suggested length, two-pass optimization for clauses > 500 chars (coarse step=10, fine ±50 chars), select highest match ≥90%, return actual clause substring at matched position with confidence="fuzzy" and similarity_score. Log best score. **Requirements: 4**
- [x] 8. Implement _tier3_full_clause(finding, clause, document_text) in cascade_engine.py: use locate_text_in_document to find deficient section at ≥85% confidence, set replacement_text to full clause.clean_text, return CascadeResult with confidence="full_clause". Return None if location confidence < 85% to cascade to Tier 4. Log confidence score. **Requirements: 5**
- [x] 9. Implement _tier4_human_review(finding, clause) in cascade_engine.py: always succeeds, returns CascadeResult with confidence="manual", requires_human=True, replacement_text=None, includes full_clause_text + ai_issue + ai_document_section. Implement resolve() orchestrator running tiers 1→2→3→4 sequentially. Record all prior tier failures in audit_trail. **Requirements: 6**
- [x] 10. Create `provenance_verifier.py` with ProvenanceVerifier class: verify(change, clause) confirms change.replace is verbatim substring of clause.clean_text, records clause_id + char_offset + char_length. For "manual" confidence returns verified=True with method="human_review". For failed verification returns verified=False (caller escalates to Tier 4). generate_report(changes) produces provenance report dict for entire document. **Requirements: 9**
- [x] 11. Create `audit_logger.py` with AuditLogger class: log_tier_attempt(), log_resolution(), log_ai_response(), and save(job_id, output_dir) that writes JSON audit file with all entries, timestamps, document ID, form_type, total findings, and cascade tier distribution stats. **Requirements: 12**
- [x] 12. Create `redaction.py` — port apply_hex_redaction, _load_whitelist, _load_blacklist_patterns, fix_ligatures from existing app.py. Maintain 3-pass structure (blacklist → structural → non-whitelist). Return (redacted_text, mapping). Implement reconstruct_pii(text, mapping) for output documents. Ensure python-docx run-level compatibility. **Requirements: 10**
- [x] 13. Create `document_processor.py` with DocumentProcessor class: extract_text(file_path) supporting .docx/.pdf/.txt/.mhtml, apply_changes(docx_path, changes, output_path, redline) with exact find-and-replace + redline formatting (strikethrough red old, underline green new) or clean formatting, create_pdf() via LibreOffice headless, overlap detection (higher-confidence change wins on same span). **Requirements: 10**
- [x] 14. Create `app.py` with FastAPI routes: POST /api/upload (file + form_type + user_id, creates job, starts thread), GET /api/job/{job_id} (status + proposed_changes with context/confidence), POST /api/job/{job_id}/apply (selected IDs, generate outputs), GET /api/job/{job_id}/download/{file_type}, POST /api/job/{job_id}/rerun (max 3 passes), GET /api/job/{job_id}/document (full text with position markers). **Requirements: 8, 10, 13**
- [x] 15. Implement process_job(job_id) orchestrator: extract text → redact PII → fetch clauses by form_type → run rules engine → call evaluation module → validate AI response → run cascade per finding → verify provenance → extract context → deduplicate (rules wins over cascade for same region) → sort by position → set status awaiting_selection → save audit log. Handle form_type override if confidence < 70%. **Requirements: 1, 2, 7, 10, 11, 12**
- [x] 16. Create `static/index.html` split-panel UI: upload form with type dropdown, left panel with change cards (checkbox, confidence badge color-coded green/yellow/orange/red, find/replace text, reasoning, clause ref, 150-word collapsible context), right panel document preview with highlighted change locations, navigation sync (click card ↔ scroll preview), active section tracking, action bar (Apply Selected, Download Redline, Download Clean, Rerun). Manual items show full clause in expandable section. **Requirements: 8, 13**
- [x] 17. Create test suite: tests/test_cascade.py (all four tiers with known clause text), tests/test_provenance.py (pass/fail/offset), tests/test_rules_engine.py (patterns, no false positives), tests/test_evaluation.py (mock AI, boundary rejection), tests/test_integration.py (end-to-end: upload NDA → verify all replacement text traces to provisions.db). Validate against existing test NDAs from redline_project/testExamples/. **Requirements: 1, 3, 4, 5, 6, 7, 9, 12**

## Task Dependency Graph

```json
{
  "waves": [
    [1],
    [2, 3, 11, 12],
    [4, 5, 6, 10, 13],
    [7],
    [8],
    [9],
    [14, 15],
    [16],
    [17]
  ]
}
```

- **Wave 1:** Project scaffolding (no dependencies)
- **Wave 2:** Foundation modules — text utils, clause repo, audit logger, redaction (depend on scaffolding)
- **Wave 3:** Core logic — rules engine, evaluation module, tier 1, provenance verifier, document processor (depend on wave 2)
- **Wave 4:** Tier 2 fuzzy match (depends on tier 1)
- **Wave 5:** Tier 3 full clause (depends on tier 2)
- **Wave 6:** Tier 4 human review + resolve orchestrator (depends on tier 3)
- **Wave 7:** FastAPI routes + job orchestrator (depend on all modules)
- **Wave 8:** Front-end UI (depends on API)
- **Wave 9:** Test suite (depends on everything)

## Notes

- The project lives in a new `ai_attorney_v3/` directory alongside the existing `ai_attorney_standalone/` for parallel testing during development.
- The local SQLite `provisions.db` should be synced from production SQL Server before development begins.
- The existing front-end in `ai_attorney_standalone/static/index.html` can be used as a starting reference for the split-panel redesign.
- Testing against the 25 attorney-redlined NDAs from `redline_project/testExamples/` provides ground truth for accuracy validation.
