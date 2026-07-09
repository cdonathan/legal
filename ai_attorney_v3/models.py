"""
Data models for the Clause Validation Cascade Engine.
All dataclasses used across modules are defined here.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClauseRecord:
    """A single attorney-approved clause from the database."""
    id: int                    # Database primary key or positional index
    form_type: str             # NDA, PSA, LEASE, etc.
    category_id: int           # Category grouping
    prov_desc: str             # Human-readable description
    html_data_text: str        # Raw HTML content from DB
    clean_text: str = ""       # Computed: stripped, normalized text
    risk_level: str = ""       # Risk classification


@dataclass
class AIFinding:
    """A single deficiency identified by the Evaluation Module."""
    id: int                    # Sequential ID within response
    clause_id: int             # References position in clause list (1-based)
    document_section: str      # Verbatim quote from document (30-150 chars)
    issue: str                 # Description of what's missing/deficient
    suggested_portion: str     # Verbatim quote from clause text
    priority: str              # "high" | "medium" | "low"


@dataclass
class ContextWindow:
    """150-word context surrounding a change location."""
    before_text: str           # 150 words before the match
    match_text: str            # The matched/changed text itself
    after_text: str            # 150 words after the match
    before_start: int          # Char offset where before_text starts in document
    after_end: int             # Char offset where after_text ends in document


@dataclass
class AuditEntry:
    """A single entry in the cascade audit trail."""
    timestamp: str
    tier: str                  # "tier1_exact" | "tier2_fuzzy" | "tier3_full" | "tier4_human"
    input_text: str            # What was being matched
    result: str                # "pass" | "fail"
    reason: str                # Why it passed or failed
    score: Optional[float] = None  # Similarity score if applicable


@dataclass
class CascadeResult:
    """Result of running the four-tier cascade for a single finding."""
    replacement_text: Optional[str]       # The verified replacement (None for manual)
    confidence: str                       # "exact" | "fuzzy" | "full_clause" | "manual"
    clause_id: int                        # Source clause reference
    char_offset: Optional[int] = None     # Position within clause text
    similarity_score: Optional[float] = None
    requires_human: bool = False
    full_clause_text: Optional[str] = None    # Full clause for manual review display
    ai_issue: Optional[str] = None            # AI's issue description for manual items
    ai_document_section: Optional[str] = None # AI's quoted doc section for manual items
    audit_trail: list = field(default_factory=list)  # List of AuditEntry


@dataclass
class VerificationResult:
    """Result of provenance verification."""
    verified: bool
    method: str                # "exact" | "fuzzy" | "full_clause" | "human_review" | "provenance_failed"
    clause_id: Optional[int] = None
    char_offset: Optional[int] = None
    char_length: Optional[int] = None


@dataclass
class ProposedChange:
    """A complete proposed change ready for user presentation."""
    id: int
    type: str                              # "replace" | "insert"
    find: str                              # Text to find in document (old text)
    replace: str                           # Replacement text (from clause or rules)
    before_context: str                    # 150 words before
    after_context: str                     # 150 words after
    confidence: str                        # "exact" | "fuzzy" | "full_clause" | "manual"
    source: str                            # "rules_engine" | "cascade_engine"
    clause_id: Optional[int] = None        # Reference to Clause_Database
    clause_desc: Optional[str] = None      # Human-readable clause name
    reasoning: str = ""                    # Why this change is needed
    priority: str = "medium"               # "high" | "medium" | "low"
    document_position: int = 0             # Char offset in document for preview sync
    similarity_score: Optional[float] = None  # For fuzzy matches
    full_clause_text: Optional[str] = None    # Full clause for manual review items


@dataclass
class TextLocation:
    """A located text span within a document."""
    start: int                 # Char offset start
    end: int                   # Char offset end
    confidence: float          # Match confidence (0.0-1.0)
    method: str                # "exact" | "normalized" | "fuzzy"
