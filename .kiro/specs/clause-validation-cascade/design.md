# Technical Design: Clause Validation Cascade Engine

## Overview

The Clause Validation Cascade Engine replaces the current AI-generates-legal-text architecture with a system where AI only evaluates documents and references approved clauses, while deterministic Python code handles all replacement text through a four-tier validation cascade. Every replacement is verified as originating from attorney-approved clause text in the SQL Server database. The system integrates with the existing FastAPI web application, PII redaction pipeline, and front-end approval workflow.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────────┐ │
│  │ Upload & │───▶│  Redaction   │───▶│    Evaluation Module      │ │
│  │ Extract  │    │  System      │    │    (GPT-4o — eval only)   │ │
│  └──────────┘    └──────────────┘    └─────────────┬─────────────┘ │
│                                                     │               │
│                                                     ▼               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Rules Engine                                │  │
│  │  (deterministic patterns — runs first, bypasses cascade)      │  │
│  └──────────────────────────────────┬───────────────────────────┘  │
│                                      │                              │
│                                      ▼                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Cascade Engine                               │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────┐  ┌───────────┐  │  │
│  │  │ Tier 1  │─▶│ Tier 2  │─▶│   Tier 3    │─▶│  Tier 4   │  │  │
│  │  │ Exact   │  │ Fuzzy   │  │ Full Clause │  │  Human    │  │  │
│  │  │ Match   │  │ Match   │  │ Replacement │  │  Review   │  │  │
│  │  └─────────┘  └─────────┘  └─────────────┘  └───────────┘  │  │
│  └──────────────────────────────────┬───────────────────────────┘  │
│                                      │                              │
│                                      ▼                              │
│  ┌──────────────┐    ┌──────────────────────┐    ┌─────────────┐  │
│  │  Provenance  │───▶│   Change Presenter   │───▶│  Document   │  │
│  │  Verifier    │    │   (user approval)    │    │  Processor  │  │
│  └──────────────┘    └──────────────────────┘    └─────────────┘  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐              ┌────────────────────────────┐    │
│  │  SQL Server    │              │  SQLite Fallback           │    │
│  │  (SeedJuraTech)│              │  (provisions.db)           │    │
│  └────────────────┘              └────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

**Processing Pipeline Sequence:**

1. User uploads document + selects form_type
2. Extract text from file (.docx/.pdf/.txt/.mhtml)
3. Apply PII redaction (hex mapping) → redacted_text + mapping
4. Fetch clauses from DB by form_type
5. Run Rules Engine on redacted_text → rules_changes[]
6. Send redacted_text + clause list to AI Evaluation Module
7. AI returns findings[] (clause_id, document_section, issue, suggested_portion)
8. Validate AI response (boundary enforcement)
9. For each valid finding: fetch clause → run Cascade (Tiers 1→2→3→4) → verify provenance
10. Combine rules_changes + cascade_changes, deduplicate
11. Extract 150-word context for each change
12. Present to user (awaiting_selection)
13. User accepts/rejects individual changes
14. Apply accepted changes to original DOCX, restore PII
15. Generate redlined + clean outputs, write audit log

## Components and Interfaces

### Evaluation Module (`evaluation_module.py`)

Constrains AI to evaluation-only output. Sends clauses by ID, receives references back.

```python
class EvaluationModule:
    def __init__(self, openai_client, model: str = "gpt-4o"):
        self.client = openai_client
        self.model = model

    def evaluate(self, redacted_text: str, clauses: list[ClauseRecord], form_type: str) -> list[AIFinding]:
        """Send document + clause list to AI, get back findings with clause references only."""

    def validate_response(self, findings: list[AIFinding], document_text: str, clauses: list[ClauseRecord]) -> list[AIFinding]:
        """Reject findings where document_section isn't in document or suggested_portion isn't in clause."""
```

**AI Response Schema (what the AI returns):**
```json
{
  "findings": [
    {
      "id": 1,
      "clause_id": 47,
      "document_section": "exact verbatim quote from document 30-150 chars",
      "issue": "what is missing or deficient",
      "suggested_portion": "verbatim quote from the clause text that addresses the gap",
      "priority": "high|medium|low"
    }
  ]
}
```

**Boundary enforcement:** After receiving AI response, code validates that `document_section` exists verbatim in input text and `suggested_portion` exists verbatim in the referenced clause. Violations are rejected and logged.

---

### Clause Repository (`clause_repository.py`)

Unified interface to clause database with automatic failover.

```python
class ClauseRepository:
    def __init__(self, sql_config: dict, sqlite_path: str): ...
    def get_clauses_by_form_type(self, form_type: str) -> list[ClauseRecord]: ...
    def get_clause_by_id(self, clause_id: int, form_type: str) -> Optional[ClauseRecord]: ...
    def get_clause_text(self, clause: ClauseRecord) -> str: ...
```

**ClauseRecord:**
```python
@dataclass
class ClauseRecord:
    id: int
    form_type: str
    category_id: int
    prov_desc: str
    html_data_text: str
    clean_text: str        # Computed: HTML stripped, entities decoded, whitespace normalized
    risk_level: str
```

---

### Cascade Engine (`cascade_engine.py`)

Four-tier resolution with audit trail at each step.

```python
class CascadeEngine:
    def __init__(self, clause_repo: ClauseRepository): ...

    def resolve(self, finding: AIFinding, clause: ClauseRecord, document_text: str) -> CascadeResult:
        """Run tiers 1→2→3→4 sequentially until one succeeds."""

    def _tier1_exact(self, suggested: str, clause_text: str) -> Optional[CascadeResult]:
        """Verbatim substring check after whitespace normalization."""

    def _tier2_fuzzy(self, suggested: str, clause_text: str, threshold: float = 0.90) -> Optional[CascadeResult]:
        """Sliding window with difflib.SequenceMatcher. Best match ≥90% wins."""

    def _tier3_full_clause(self, finding: AIFinding, clause: ClauseRecord, document_text: str) -> Optional[CascadeResult]:
        """Use full clause text; locate deficient section at ≥85% confidence."""

    def _tier4_human_review(self, finding: AIFinding, clause: ClauseRecord) -> CascadeResult:
        """Flag for manual review. Always succeeds."""
```

**Tier 2 Algorithm (Fuzzy Match):**
- Uses `difflib.SequenceMatcher` (standard library, phrase-level similarity)
- Sliding window sized at ±20% of suggested text length
- Performance optimization: two-pass for clauses > 500 chars (coarse scan at step=10, fine-grained in candidate regions)
- Selects highest-scoring match above 90% threshold

---

### Rules Engine (`rules_engine.py`)

Deterministic patterns that bypass AI entirely.

```python
class RulesEngine:
    RULES: list[Rule]  # Loaded from code + optionally from DB

    def apply(self, document_text: str) -> list[ProposedChange]:
        """Apply all regex rules, return changes with 150-word context."""
```

Minimum rule set: "attorney's fees" → "reasonable attorney's fees", "best efforts" → "commercially reasonable efforts", "take all steps" → "take commercially reasonable steps".

---

### Provenance Verifier (`provenance_verifier.py`)

Final gate before presenting to user.

```python
class ProvenanceVerifier:
    def verify(self, change: ProposedChange, clause: ClauseRecord) -> VerificationResult:
        """Confirm replacement_text is verbatim substring of clause.clean_text."""

    def generate_report(self, changes: list[ProposedChange]) -> dict:
        """Provenance report for entire document."""
```

If verification fails, item escalates to Tier 4 (human review).

---

### Context Extractor (`context_extractor.py`)

```python
def extract_context(document_text: str, match_start: int, match_end: int, word_count: int = 150) -> ContextWindow:
    """
    150 words before + matched text + 150 words after.
    Snaps to word boundaries. Returns ContextWindow dataclass.
    """
```

---

### Document Processor (`document_processor.py`)

Handles file I/O, DOCX modification, and output generation.

```python
class DocumentProcessor:
    def extract_text(self, file_path: str) -> str: ...
    def apply_changes(self, docx_path: str, changes: list[ProposedChange], output_path: str, redline: bool = False): ...
    def create_pdf(self, docx_path: str, pdf_path: str): ...
```

Output formats: redlined DOCX (strikethrough red + underline green), clean DOCX (changes applied), PDF via LibreOffice.

---

### Audit Logger (`audit_logger.py`)

```python
class AuditLogger:
    def log_tier_attempt(self, finding_id: int, tier: str, input_data: str, result: str, reason: str): ...
    def log_resolution(self, finding_id: int, replacement: str, clause_id: int, confidence: str, accepted: bool): ...
    def log_ai_response(self, raw_response: str): ...
    def save(self, job_id: str, output_dir: str): ...
```

Produces JSON audit file per document with timestamps, all decisions, and AI response.

---

### Front-End (`static/index.html`)

Split-panel single-page application:
- Left panel: change suggestion cards (grouped by confidence level, checkboxes)
- Right panel: full document preview with highlighted change locations
- Navigation sync: click card → scroll preview; click highlight → scroll cards
- Color coding: green (exact), yellow (fuzzy), orange (full_clause), red (manual)

## Data Models

```python
@dataclass
class ProposedChange:
    id: int
    type: str                      # "replace" | "insert"
    find: str                      # Text to find in document
    replace: str                   # Replacement text (from clause)
    before_context: str            # 150 words before
    after_context: str             # 150 words after
    confidence: str                # "exact" | "fuzzy" | "full_clause" | "manual"
    source: str                    # "rules_engine" | "cascade_engine"
    clause_id: Optional[int]
    clause_desc: Optional[str]
    reasoning: str
    priority: str                  # "high" | "medium" | "low"
    document_position: int         # Char offset for preview sync
    similarity_score: Optional[float]

@dataclass
class CascadeResult:
    replacement_text: Optional[str]
    confidence: str
    clause_id: int
    char_offset: Optional[int]
    similarity_score: Optional[float]
    requires_human: bool = False
    full_clause_text: Optional[str] = None
    ai_issue: Optional[str] = None
    ai_document_section: Optional[str] = None
    audit_trail: list = field(default_factory=list)

@dataclass
class AIFinding:
    id: int
    clause_id: int
    document_section: str
    issue: str
    suggested_portion: str
    priority: str

@dataclass
class AuditEntry:
    timestamp: str
    tier: str
    input_text: str
    result: str
    reason: str
    score: Optional[float]
```

## Correctness Properties

### Property 1: No AI-Generated Text in Output
Every `replace` field in a ProposedChange is either (a) from the Rules Engine (hardcoded), (b) a verified substring of an Approved_Clause, or (c) flagged for human review with no auto-apply. The Provenance Verifier confirms this before any change reaches the user.

**Validates: Requirements 1, 9**

### Property 2: Provenance Chain Integrity
Every applied change has a traceable path: AI finding → clause_id → cascade tier → provenance verification → user approval. The audit log records each step with timestamps.

**Validates: Requirements 9, 12**

### Property 3: Strict Cascade Ordering
Tiers execute 1→2→3→4 sequentially. A higher tier only runs if all lower tiers fail. No tier is skipped. This ensures the most precise match is always preferred.

**Validates: Requirements 3, 4, 5, 6**

### Property 4: No Overlapping Changes
Document position tracking ensures two changes cannot affect the same text span. If overlap is detected, the higher-confidence change wins and the lower-confidence one is dropped.

**Validates: Requirements 10**

### Property 5: PII Isolation
PII redaction happens before evaluation (AI never sees real names/addresses). PII reconstruction happens after all changes are applied to the output document.

**Validates: Requirements 10**

## Error Handling

| Error Condition | Handling |
|----------------|----------|
| SQL Server connection failure | Fall back to local SQLite provisions.db. Log warning. |
| AI returns invalid JSON | Retry once. If still invalid, fail job with parse_error status. |
| AI returns clause_id not in DB | Reject that finding. Log violation. Continue with others. |
| AI's document_section not found in text | Reject that finding. Log boundary violation. |
| AI's suggested_portion not found in clause | Reject. Still attempt Tiers 2-4 using full clause text. |
| Provenance verification fails | Escalate to Tier 4 (human review). Never silently apply. |
| Document text extraction fails | Fail job with extraction_error status. |
| LibreOffice PDF generation fails | Return DOCX outputs only. Log warning. |
| No clauses found for form_type | Fail job with no_clauses_error. Prompt user to verify form_type. |

## Testing Strategy

| Layer | Test Type | Coverage |
|-------|-----------|----------|
| Cascade Tier 1 | Unit test | Exact match, whitespace normalization, edge cases (empty string, full clause = suggested) |
| Cascade Tier 2 | Unit test | Fuzzy match above/below threshold, window sizing, performance with long clauses |
| Cascade Tier 3 | Unit test | Document location at various confidence levels, normalized matching |
| Cascade Tier 4 | Unit test | Always succeeds, correct data in result |
| Provenance Verifier | Unit test | Verify pass/fail, offset calculation, report generation |
| Rules Engine | Unit test | All patterns match correctly, context extraction, no false positives |
| AI Boundary | Integration test | Mock AI responses with valid/invalid data, rejection logic |
| End-to-end | Integration test | Upload NDA → get proposed changes → verify all replacement text traces to clause DB |
| Front-end | Manual test | Split-panel sync, checkbox behavior, download links |

## File Structure

```
ai_attorney_v3/
├── app.py                      # FastAPI entry point, routes
├── config.py                   # Environment config, DB settings
├── models.py                   # Data classes
├── evaluation_module.py        # AI prompt + response parsing
├── cascade_engine.py           # Four-tier cascade
├── provenance_verifier.py      # Final verification gate
├── rules_engine.py             # Deterministic patterns
├── clause_repository.py        # DB access (SQL Server + SQLite)
├── document_processor.py       # File I/O, DOCX modification, output
├── redaction.py                # PII hex-mapping (from existing)
├── context_extractor.py        # 150-word context windows
├── audit_logger.py             # Structured audit trail
├── text_utils.py               # Normalize, clean, locate text
├── static/
│   └── index.html              # Split-panel UI
├── provisions.db               # SQLite fallback
├── redaction_whitelist.txt     # PII whitelist
├── blacklists/                 # Known company names
├── requirements.txt            # Python dependencies
├── start.bat / start.sh        # Launchers
└── tests/
    ├── test_cascade.py
    ├── test_provenance.py
    ├── test_rules_engine.py
    └── test_evaluation.py
```

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fuzzy matching | `difflib.SequenceMatcher` | Standard library, phrase-level similarity, ratio() maps to 90% threshold |
| Database access | pymssql + sqlite3 | Matches existing stack, no new deps |
| DOCX manipulation | python-docx | Already in use, run-level formatting |
| PDF generation | LibreOffice headless | Already deployed |
| AI model | GPT-4o, temperature=0.0 | Best legal analysis accuracy, deterministic |
| Front-end | Single static HTML + vanilla JS | No build step, matches deployment model |
| Audit format | JSON per document | Portable, queryable, human-readable |
| New project folder | `ai_attorney_v3/` | Clean separation from v2, allows parallel testing |
