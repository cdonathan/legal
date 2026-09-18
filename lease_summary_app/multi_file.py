"""
Multi-File Summary Engine
===========================
Processes all documents in a tenant folder, extracts fields from each,
determines chronological order, and merges into a single summary with
historical change tracking.

Flow:
  1. Scan folder for all PDF/DOCX files
  2. Ingest each document and extract execution date + document type
  3. Sort documents by execution date (oldest → newest)
  4. Extract fields from each document via AI
  5. Merge fields: latest value wins, earlier values become history
  6. Output: merged summary with change history
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


# Fields a standalone GUARANTY document can plausibly address. Used to scope
# down the batch extraction call (Call 2 of the multi-file pipeline) for
# guaranty docs to just these - guaranty agreements are a separate document
# from the lease itself and only ever speak to who's guaranteeing what.
GUARANTY_FIELDS = {
    "Guarantor_Name", "Guarantor_StReg", "Guarantor_Type", "Guaranty_Term",
}


# Every date format the AI's "date" field or a source document might
# plausibly produce. Tried in order; the first one that parses cleanly wins.
# parse_strict_date() extracts an embedded date substring rather than
# requiring the ENTIRE input string to be just a date. Extracted field
# values routinely carry surrounding context (e.g. Amendment_Effective_Date
# often comes back as 'June 1, 2020 (the "Agreement Effective Date")' or
# 'effective February 1, 2019 (the "Effective Date")') - if the whole
# string had to match a strptime format exactly, these perfectly good dates
# would be rejected as unparseable just because of trailing text, while a
# document whose date happened to come back as a bare "November 9, 2016"
# with no surrounding text would incorrectly look MORE valid and win a
# latest-date comparison it shouldn't win. Month names are matched against
# an explicit lookup table (not "any word followed by digits"), so OCR
# garbage like "Novela 22, 2024" still correctly fails to parse.
_MONTH_LOOKUP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# "<Month> <day>[st/nd/rd/th], <year>" - comma optional, ordinal suffix
# optional (e.g. "June 1, 2020", "June 1st 2020").
_MONTH_DATE_RE = re.compile(
    r'\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b'
)

# Numeric date patterns, tried in order most-specific-first so a 4-digit
# year never gets misread as part of a 2-digit-year pattern. Each maps a
# regex match to (year, month, day).
_NUMERIC_DATE_PATTERNS = (
    (re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b'),
     lambda m: (int(m.group(3)), int(m.group(1)), int(m.group(2)))),   # m/d/YYYY
    (re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b'),
     lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3)))),   # YYYY-mm-dd (ISO)
    (re.compile(r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b'),
     lambda m: (int(m.group(3)), int(m.group(1)), int(m.group(2)))),   # m-d-YYYY
    (re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{2})\b'),
     lambda m: (2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))),  # m/d/yy
)


def parse_strict_date(value: Optional[str]) -> Optional[datetime]:
    """
    Find and parse a real calendar date embedded anywhere in `value`, or
    return None if no valid date can be found.

    This is the single source of truth for "is this date confident enough
    to trust automatically, or does a human need to look at it" - it's
    intentionally strict about WHAT counts as a date (a string like
    "Novela 22, 2024" - an OCR misreading of handwriting - or "50, 20J_" -
    a raw unresolved template blank - must NOT silently pass through just
    because it contains some digits) while being lenient about surrounding
    text (a value like 'June 1, 2020 (the "Agreement Effective Date")' must
    still be recognized as June 1, 2020). Every one of the fragile bugs
    found in this pipeline traces back to some form of loose date handling
    - this function exists so there is exactly ONE place that decides
    "yes, this is a real date."
    """
    if not value:
        return None
    v = value.strip()
    if not v or v.upper() in ("TBD", "NONE", "NONE.", "NEEDS VERIFICATION", "UNKNOWN"):
        return None
    if "[handwritten" in v.lower():
        return None

    m = _MONTH_DATE_RE.search(v)
    if m:
        month = _MONTH_LOOKUP.get(m.group(1).lower())
        if month:
            try:
                return datetime(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass  # e.g. "February 30" - not a real date, fall through

    for regex, extractor in _NUMERIC_DATE_PATTERNS:
        match = regex.search(v)
        if match:
            try:
                year, month, day = extractor(match)
                return datetime(year, month, day)
            except ValueError:
                continue

    return None


def is_confident_date(value: Optional[str]) -> bool:
    """True if `value` parses as a real calendar date via parse_strict_date."""
    return parse_strict_date(value) is not None


# A document's execution date is always stated on its opening page(s),
# never buried deep in the body - and its signature block, if any, is
# always on the last page (or second-to-last, if the last page is blank).
# Restricting keyword/fallback searches to these windows instead of the
# full document text keeps regex work bounded and matches how these
# documents are actually written.
DATE_SEARCH_WINDOW_CHARS = 10_000
SIGNATURE_SEARCH_WINDOW_CHARS = 10_000

# Keyword indicators that a document's signature block is present, checked
# only within the last SIGNATURE_SEARCH_WINDOW_CHARS characters (see
# has_signature()). A document with none of these near its end has no
# signature page in its extracted text and is treated as unsigned/
# unfinalized - excluded from the pipeline entirely rather than
# contributing unreliable field data from an unexecuted draft.
_SIGNATURE_KEYWORDS = (
    "in witness whereof",
    "signature",
    "signed",
    "authorized signatory",
    "duly authorized",
    "print name",
    "docusign",
    "/s/",
    # Letter-style documents (e.g. a termination notice sent as a short
    # business letter) don't use formal "IN WITNESS WHEREOF" contract
    # language - they close with an ordinary letter sign-off followed by a
    # name/title block instead (e.g. "Yours very truly, / Aldo US Inc. /
    # Per: / Stephanie Hart / Vice President Real Estate").
    "truly",       # covers "yours truly" / "yours very truly"
    "sincerely",
    "per:",
    "authorized representative",
    "on behalf of",
)


def has_signature(text: str) -> bool:
    """
    True if the last SIGNATURE_SEARCH_WINDOW_CHARS characters of `text`
    contain a recognizable signature-block indicator. This is the gate for
    "is this document an executed/finalized version we can rely on" - a
    document with no signature block near its end is excluded from the
    pipeline entirely (see the ingest phase in _run_multi_file_pipeline()).
    """
    if not text:
        return False
    window = text[-SIGNATURE_SEARCH_WINDOW_CHARS:].lower()
    return any(kw in window for kw in _SIGNATURE_KEYWORDS)


@dataclass
class DocumentInfo:
    """Represents a single document in a multi-file set."""
    filepath: str
    filename: str
    doc_type: str = ""  # lease, amendment, agreement, notice, etc.
    execution_date: Optional[str] = None  # mm/dd/yyyy
    execution_date_raw: str = ""  # Original text
    amendment_number: Optional[int] = None  # 1, 2, 3... if applicable
    field_data: Dict[str, str] = field(default_factory=dict)
    normalized_dates: Dict[str, str] = field(default_factory=dict)
    interpretations: Dict[str, str] = field(default_factory=dict)  # field -> plain-language reading
    sections: Dict[str, str] = field(default_factory=dict)  # field -> bare section ref (e.g. "Section 3.8")
    text: str = ""
    char_count: int = 0


@dataclass
class FieldHistory:
    """Tracks the history of a single field across documents."""
    current_value: str = ""
    current_interpretation: str = ""
    current_section: str = ""  # bare section ref, e.g. "Section 3.8"
    current_date: str = ""  # mm/dd/yyyy
    current_source: str = ""  # filename
    current_doc_type: str = ""
    current_amendment_number: Optional[int] = None
    history: List[dict] = field(default_factory=list)
    # Each history entry: {"value", "interpretation", "section", "date",
    #                      "source", "doc_type", "amendment_number"}


def scan_folder(folder_path: str) -> List[str]:
    """Find all processable files in a folder."""
    supported_ext = {".pdf", ".docx", ".doc", ".txt"}
    files = []
    for entry in os.scandir(folder_path):
        if entry.is_file() and Path(entry.name).suffix.lower() in supported_ext:
            files.append(entry.path)
    return sorted(files)


def classify_document(filename: str, text_header: str = "") -> Tuple[str, Optional[int]]:
    """
    Classify a document by type and extract amendment number if applicable.
    Returns (doc_type, amendment_number).
    """
    fname = filename.upper()
    header = text_header[:2000].upper() if text_header else ""

    # Amendment number extraction.
    #
    # IMPORTANT: check the FILENAME for an ordinal before ever looking at the
    # document's header/body text. Amendment documents routinely recite the
    # lease's full amendment history in their opening recital (e.g. "...as
    # amended by a First Amendment of Lease dated October 5, 2011, a Second
    # Amendment of Lease dated..., a Third Amendment..."). If we searched
    # header text first, the SEVENTH Amendment's own header would still
    # contain the phrase "First Amendment" (from that recital) and match
    # ordinal 1 before ever reaching "SEVENTH" - collapsing every amendment
    # in a folder to amend_num=1. The filename (e.g. "EXTENSION AND SEVENTH
    # AMENDMENT OF LEASE") is a far more reliable signal for which amendment
    # THIS document actually is, so it's checked first and, if found, used
    # exclusively - header text is only consulted as a fallback when the
    # filename itself doesn't carry an ordinal.
    amendment_num = None
    ordinal_map = {
        "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5,
        "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10,
        "ELEVENTH": 11, "TWELFTH": 12,
    }

    for ordinal, num in ordinal_map.items():
        if ordinal + " AMENDMENT" in fname:
            amendment_num = num
            break

    if amendment_num is None:
        match = re.search(r'AMENDMENT\s*(?:NO\.?|#)\s*(\d+)', fname)
        if match:
            amendment_num = int(match.group(1))

    # Filename had no ordinal at all - fall back to header/body text (e.g. a
    # generically-named file whose title page states "THIRD AMENDMENT").
    # This is inherently less reliable for documents whose header also
    # recites earlier amendments, but it's better than nothing when the
    # filename gives no signal at all.
    if amendment_num is None:
        for ordinal, num in ordinal_map.items():
            if ordinal + " AMENDMENT" in header:
                amendment_num = num
                break
        if amendment_num is None:
            match = re.search(r'AMENDMENT\s*(?:NO\.?|#)\s*(\d+)', header)
            if match:
                amendment_num = int(match.group(1))

    # Document type classification.
    #
    # IMPORTANT: More specific/rarer document types are checked BEFORE the
    # generic "LEASE AGREEMENT" signal. Documents like Omnibus Agreements,
    # Termination Notices, Estoppels, etc. routinely reference "the Lease"
    # or contain "LEASE AGREEMENT" boilerplate in their recitals (e.g. "...
    # TENANT AND LANDLORDS ARE PARTIES TO CERTAIN LEASE AGREEMENTS...") even
    # though they are NOT the original lease document. Checking those
    # stronger signals first prevents them from being misclassified as
    # doc_type "lease", which would otherwise let their dates/facts silently
    # override the real lease's fields during merge.
    if "AMENDMENT" in fname or "AMENDMENT" in header:
        doc_type = "amendment"
    elif "COVID" in fname or "COVID" in header:
        doc_type = "covid_amendment"
    elif "OMNIBUS" in fname or "OMNIBUS" in header:
        doc_type = "omnibus_agreement"
    elif "TERMINATION" in fname or "TERMINATION" in header:
        doc_type = "termination"
    elif "ESTOPPEL" in fname or "ESTOPPEL" in header:
        doc_type = "estoppel"
    elif "GUARANTY" in fname or "GUARANTEE" in fname or "GUARANTY" in header or "GUARANTEE" in header:
        doc_type = "guaranty"
    elif "SETTLEMENT" in fname or "SETTLEMENT" in header:
        doc_type = "settlement"
    elif "CHANGE REQUEST" in fname or "JDE" in fname:
        doc_type = "change_request"
    elif "RESOLUTION" in fname or "RESOLUTION" in header:
        doc_type = "resolution"
    elif "EXTENSION" in fname or "EXTENSION" in header:
        doc_type = "amendment"  # Extensions are amendments
    elif "LEASE AGREEMENT" in fname or "LEASE AGREEMENT" in header:
        doc_type = "amendment" if amendment_num else "lease"
    else:
        doc_type = "other"

    return doc_type, amendment_num


def sort_documents(docs: List[DocumentInfo]) -> List[DocumentInfo]:
    """
    Sort documents chronologically (oldest first) for HISTORY-DISPLAY
    purposes only (Raw Data column ordering, "documents" list in job_meta).
    Uses execution_date if available, falls back to amendment number,
    then document type (lease before amendments).

    NOTE: this sort no longer decides which document "wins" for the three
    priority date facts (Date_Lease/Date_Termination/Amendment_Effective_Date)
    - those are pinned by document identity in merge_fields() based on
    validated dates determined in app.py's Phase 3C, not by this sort order.
    execution_date is always assigned via parse_strict_date(...).strftime
    ("%m/%d/%Y") before this runs, so the single %m/%d/%Y format below is
    safe - it's no longer receiving a mix of formats (e.g. an AI-normalized
    ISO "2007-07-30" string) the way it used to.
    """
    def sort_key(doc: DocumentInfo):
        # Primary: execution date
        date_val = None
        if doc.execution_date:
            try:
                date_val = datetime.strptime(doc.execution_date, "%m/%d/%Y")
            except ValueError:
                pass

        # Secondary: amendment number (lease=0, amendments=1-N)
        amend_num = doc.amendment_number or 0
        if doc.doc_type == "lease":
            amend_num = 0

        # Tertiary: type priority
        type_priority = {
            "lease": 0,
            "guaranty": 0,
            "amendment": 1,
            "covid_amendment": 2,
            "omnibus_agreement": 2,
            "change_request": 3,
            "resolution": 3,
            "settlement": 4,
            "termination": 5,
            "estoppel": 6,
            "other": 7,
        }
        type_val = type_priority.get(doc.doc_type, 7)

        # Sort: date first (None last), then amendment number, then type
        if date_val:
            return (0, date_val, amend_num, type_val)
        else:
            return (1, datetime.min, amend_num, type_val)

    return sorted(docs, key=sort_key)


# Fields that describe a fixed, immutable fact about the ORIGINAL lease
# (the day it was signed, its title) rather than something that can
# legitimately change over the life of the tenancy. These must never be
# overridden by amendments, termination notices, omnibus agreements, etc. -
# only the document actually classified as the original "lease" may supply
# them. This is deliberately a short list: fields like Owner_Name CAN
# legitimately change later (assignment) and should keep normal latest-wins
# merge behavior.
#
# Date_Commencment is included here too: the Commencement Date is a fixed
# historical fact set once by the original lease (when the tenancy actually
# began), not something amendments redefine. Amendments frequently restate
# or reference "July 30, 2007"/the original commencement date in their own
# recitals or term-extension clauses (e.g. "the Term...shall begin on the
# Commencement Date") - without this pin, whichever amendment sorts last
# would silently override the lease's own Commencement Date attribution,
# even when the value happens to be identical, mislabeling its source.
LEASE_ORIGIN_ONLY_FIELDS = {"Date_Lease", "LeaseAgr_Name", "Date_Commencment"}

# Similar pin, but for facts that only make sense on a Termination Notice.
TERMINATION_ONLY_FIELDS = {"Date_Termination"}


def merge_fields(
    sorted_docs: List[DocumentInfo],
    skip_empty: bool = True,
    effective_date_source: Optional["DocumentInfo"] = None,
) -> Dict[str, FieldHistory]:
    """
    Merge fields across documents in chronological order.
    Later documents override earlier ones ("latest governs"). Changes are
    tracked as history, each version tagged with its source document,
    section reference, and interpretation.

    Exceptions (pinned fields - never "latest wins" across arbitrary
    documents):
    - LEASE_ORIGIN_ONLY_FIELDS (e.g. Date_Lease, Date_Commencment) describe
      a fixed historical fact about the original lease and are only ever
      populated from the document classified as doc_type == "lease".
    - TERMINATION_ONLY_FIELDS (Date_Termination) are only ever populated
      from a document classified as doc_type == "termination".
    - Amendment_Effective_Date is pinned to ONE specific document: whichever
      document the caller identified as "the latest" (passed in as
      effective_date_source - see _run_multi_file_pipeline's classify step).
      This is the user's Priority #1 fact ("the effective date... once
      found in the latest document, nothing overrides it") - it must not
      be treated as an ordinary latest-wins field across every amendment,
      or whichever document merely SORTS last (by a possibly-wrong parsed
      date) would silently win instead of the document actually identified
      as latest. If effective_date_source is None, falls back to ordinary
      latest-wins behavior across amendment-like documents.

    Args:
        sorted_docs: Documents sorted oldest → newest
        skip_empty: Don't count "None." / empty / "See Original Lease." as values
        effective_date_source: the DocumentInfo identified as "the latest"
          document (excluding a Termination Notice, if any) - see
          Date_Termination handling in _run_multi_file_pipeline. Only this
          document's Amendment_Effective_Date value is used.

    Returns:
        Dict mapping field_name → FieldHistory with current value and history
    """
    merged: Dict[str, FieldHistory] = {}

    skip_values = {'', 'none', 'none.', 'n/a', 'not applicable',
                   'see original lease', 'see original lease.', 'not found.'}

    for doc in sorted_docs:
        for field_name, value in doc.field_data.items():
            # Skip empty/null values
            if skip_empty and (not value or value.strip().lower() in skip_values):
                continue

            # Lease-origin facts can only come from the actual lease document.
            if field_name in LEASE_ORIGIN_ONLY_FIELDS and doc.doc_type != "lease":
                continue

            # Termination-only facts can only come from a termination notice.
            if field_name in TERMINATION_ONLY_FIELDS and doc.doc_type != "termination":
                continue

            # The "latest document's effective date" is pinned to exactly
            # one document, identified by the caller - not by sort order.
            if field_name == "Amendment_Effective_Date" and effective_date_source is not None:
                if doc is not effective_date_source:
                    continue

            value = value.strip()
            doc_date = doc.execution_date or "Unknown"
            doc_source = doc.filename
            doc_interp = doc.interpretations.get(field_name, "") or value
            doc_section = doc.sections.get(field_name, "")

            if field_name not in merged:
                # First time seeing this field
                merged[field_name] = FieldHistory(
                    current_value=value,
                    current_interpretation=doc_interp,
                    current_section=doc_section,
                    current_date=doc_date,
                    current_source=doc_source,
                    current_doc_type=doc.doc_type,
                    current_amendment_number=doc.amendment_number,
                )
            else:
                existing = merged[field_name]
                # Check if value actually changed
                if _values_differ(existing.current_value, value):
                    # Push current to history
                    existing.history.append({
                        "value": existing.current_value,
                        "interpretation": existing.current_interpretation,
                        "section": existing.current_section,
                        "date": existing.current_date,
                        "source": existing.current_source,
                        "doc_type": existing.current_doc_type,
                        "amendment_number": existing.current_amendment_number,
                    })
                    # Update current — latest document governs
                    existing.current_value = value
                    existing.current_interpretation = doc_interp
                    existing.current_section = doc_section
                    existing.current_date = doc_date
                    existing.current_source = doc_source
                    existing.current_doc_type = doc.doc_type
                    existing.current_amendment_number = doc.amendment_number
                else:
                    # Same value, just update the date/source/section attribution
                    existing.current_date = doc_date
                    existing.current_source = doc_source
                    existing.current_doc_type = doc.doc_type
                    existing.current_amendment_number = doc.amendment_number
                    if doc_section:
                        existing.current_section = doc_section
                    if doc_interp:
                        existing.current_interpretation = doc_interp

    return merged


def _values_differ(val1: str, val2: str) -> bool:
    """
    Check if two field values are meaningfully different.
    Normalizes whitespace and ignores minor formatting differences.
    """
    def normalize(v):
        v = re.sub(r'\s+', ' ', v).strip().lower()
        # Remove trailing periods for comparison
        v = v.rstrip('.')
        return v

    return normalize(val1) != normalize(val2)


def format_field_with_history(field_history: FieldHistory) -> str:
    """
    Format a field value with its history for display in the summary.
    Returns formatted text suitable for the DOCX/preview.

    Kept for backward compatibility (used as the base FieldName value).
    For the split Interpretation/Raw columns, see
    ``format_field_interpretation`` and ``format_field_raw``.
    """
    if not field_history.history:
        # No changes — just return current value
        return field_history.current_value

    # Has history — format with annotations
    lines = []
    # Current value (most recent)
    source_label = _short_source(field_history.current_source)
    lines.append(f"[Current - {source_label} ({field_history.current_date})]:")
    lines.append(field_history.current_value)

    # Historical values (most recent first)
    for entry in reversed(field_history.history):
        source_label = _short_source(entry["source"])
        lines.append(f"")
        lines.append(f"[Prior - {source_label} ({entry['date']})]:")
        lines.append(entry["value"])

    return "\n".join(lines)


def format_field_interpretation(field_history: FieldHistory, suppress_section: bool = False) -> str:
    """
    Build the Interpretation column value for a merged field: the latest
    (current/superseding) value only, in precise/plain-language form,
    tagged with its section reference — qualified with the document label
    (e.g. "Amendment: Section 1") when it did not come from the original
    lease.

    suppress_section: when True, the "(Section X)" tag is omitted entirely.
    Use this for trivial bare-fact fields (address lines, city, zip, phone,
    email, attn name, etc. - typically an agreement type's `short_fields`
    set) where a section/document reference adds noise rather than useful
    verification context - e.g. a multi-line tenant address reads far more
    clearly as a clean address block than as 5 separate lines each individually
    suffixed with "(REFERENCE PROVISIONS)".
    """
    from field_variants import format_interpretation, qualify_section, is_none_value, needs_verification

    if needs_verification(field_history.current_value):
        return "NEEDS VERIFICATION"
    if is_none_value(field_history.current_value):
        return "None"

    if suppress_section:
        return field_history.current_interpretation or field_history.current_value

    qualified_section = qualify_section(
        field_history.current_section,
        field_history.current_doc_type,
        field_history.current_amendment_number,
    )
    return format_interpretation(field_history.current_interpretation, qualified_section)


def format_field_raw(field_history: FieldHistory) -> str:
    """
    Build the Raw Data column value for a merged field: the verbatim
    copy/paste from EVERY document that stated this field (current +
    all historical versions), each tagged with its source document and
    section reference, most recent first.
    """
    from field_variants import is_none_value, doc_type_label, needs_verification

    if is_none_value(field_history.current_value) and not field_history.history:
        return "None"

    lines = []

    def _tag(doc_type, amendment_number, source, section, date):
        label = doc_type_label(doc_type, amendment_number, fallback=Path(source).stem if source else "")
        bits = [label]
        if section:
            bits.append(section)
        if date and date != "Unknown":
            bits.append(date)
        return ", ".join(bits)

    def _display_value(value):
        if needs_verification(value):
            return f"NEEDS VERIFICATION (source text: {value.strip()})"
        return value

    # Current (latest / superseding) version first
    tag = _tag(
        field_history.current_doc_type, field_history.current_amendment_number,
        field_history.current_source, field_history.current_section, field_history.current_date,
    )
    lines.append(f"[{tag}]: {_display_value(field_history.current_value)}")

    # Historical versions, most recent first
    for entry in reversed(field_history.history):
        tag = _tag(
            entry.get("doc_type", ""), entry.get("amendment_number"),
            entry.get("source", ""), entry.get("section", ""), entry.get("date", ""),
        )
        lines.append(f"[{tag}]: {_display_value(entry['value'])}")

    return "\n\n".join(lines)


def _short_source(filename: str) -> str:
    """Shorten a filename for display (e.g., extract amendment label)."""
    name = Path(filename).stem

    # Try to extract the key part (e.g., "FIRST AMENDMENT OF LEASE")
    # Pattern: TENANT - Location - Code - DOCUMENT TYPE - Number
    parts = name.split(" - ")
    if len(parts) >= 4:
        return parts[3].strip()  # Document type part

    # Fallback: just use first 40 chars
    if len(name) > 40:
        return name[:40] + "..."
    return name


def build_multi_file_prompt_prefix(doc_info: DocumentInfo) -> str:
    """
    Build a prefix instruction for AI extraction that's specific to
    the document type in a multi-file context.
    """
    if doc_info.doc_type == "lease":
        return "This is the ORIGINAL LEASE AGREEMENT. Extract ALL fields completely."

    elif doc_info.doc_type == "guaranty":
        return (
            "This is a GUARANTY AGREEMENT (a separate document from the lease itself). "
            "Extract ONLY guarantor-related fields from it: Guarantor_Name, Guarantor_StReg, "
            "Guarantor_Type, and Guaranty_Term (the term/duration of the guarantor's obligation, "
            "e.g. 'for the entire lease term and all Tenant's obligations'). "
            "For all other fields not addressed by a guaranty agreement, return empty string \"\"."
        )

    elif doc_info.doc_type == "amendment":
        num_str = ""
        if doc_info.amendment_number:
            ordinals = {1: "First", 2: "Second", 3: "Third", 4: "Fourth",
                        5: "Fifth", 6: "Sixth", 7: "Seventh", 8: "Eighth",
                        9: "Ninth", 10: "Tenth"}
            num_str = ordinals.get(doc_info.amendment_number,
                                   f"#{doc_info.amendment_number}")
            num_str = f" ({num_str})"
        return (
            f"This is a LEASE AMENDMENT{num_str}. "
            "Only extract fields that are EXPLICITLY modified or stated in this amendment. "
            "For fields NOT addressed in this amendment, return empty string \"\". "
            "Do NOT guess values from the original lease — only extract what this document changes."
        )

    elif doc_info.doc_type == "covid_amendment":
        return (
            "This is a COVID-19 AGREEMENT TO AMEND. "
            "Extract only the specific terms modified (typically rent relief, "
            "deferral, term changes). For unmodified fields, return empty string \"\"."
        )

    elif doc_info.doc_type == "omnibus_agreement":
        return (
            "This is an OMNIBUS AGREEMENT. "
            "Extract any lease terms it modifies. For unmodified fields, return empty string \"\"."
        )

    elif doc_info.doc_type in ("termination", "settlement", "resolution"):
        return (
            f"This is a {doc_info.doc_type.upper().replace('_', ' ')}. "
            "Extract key dates, terms, and any modifications to the lease. "
            "For fields not applicable, return empty string \"\"."
        )

    elif doc_info.doc_type in ("change_request", "estoppel"):
        return (
            f"This is a {doc_info.doc_type.upper().replace('_', ' ')}. "
            "Extract any factual data it provides (names, addresses, dates, amounts). "
            "For fields not mentioned, return empty string \"\"."
        )

    else:
        return (
            "Extract any lease-relevant information from this document. "
            "For fields not addressed, return empty string \"\"."
        )


def _is_none_like_date(value: str, skip_values: set) -> bool:
    """True if a value is empty/None-like and shouldn't be shown as a date badge."""
    return not value or value.strip().lower() in skip_values


def merge_normalized_dates(
    sorted_docs: List[DocumentInfo],
    merged_fields: Optional[Dict[str, "FieldHistory"]] = None,
) -> Dict[str, str]:
    """
    Build the normalized (mm/dd/yyyy-ish) date shown for each date field.

    IMPORTANT: this must agree with merge_fields()'s notion of which
    document "won" each field - it is NOT an independent latest-wins scan
    over every document's normalized_dates. An independent scan can (and
    did) disagree with merge_fields(): e.g. a document sorted after the one
    that actually supplied a field's current text value might still have
    its OWN normalized date for that same field key sitting in
    doc.normalized_dates (a leftover from its own extraction/retry pass),
    silently overriding the correct value with an unrelated document's
    date, or - for LEASE_ORIGIN_ONLY_FIELDS like Date_Lease/
    Date_Commencment - leaking a non-lease document's date onto a
    lease-only field.

    If `merged_fields` (merge_fields()'s output) is provided, each field's
    normalized date is taken ONLY from whichever document
    merged_fields[field].current_source identifies as the winner - the same
    document whose text became the field's displayed value. Falls back to
    the old independent-scan behavior only if merged_fields isn't supplied
    (kept for backward compatibility with any other caller).
    """
    skip_values = {'', 'tbd', 'none', 'unknown', 'needs verification'}

    if merged_fields is not None:
        docs_by_filename = {d.filename: d for d in sorted_docs}
        merged_dates = {}
        for field_name, hist in merged_fields.items():
            source = hist.current_source or ""
            # A human-verification correction appends " (human-verified)" to
            # current_source (see app.py's correction-application code) -
            # strip that suffix to look up the underlying document. The
            # CORRECTED VALUE ITSELF is the best "normalized date" in that
            # case anyway (a human typed it in directly), so prefer it.
            if source.endswith(" (human-verified)"):
                if not _is_none_like_date(hist.current_value, skip_values):
                    merged_dates[field_name] = hist.current_value
                continue
            winning_doc = docs_by_filename.get(source)
            if not winning_doc:
                continue
            date_val = winning_doc.normalized_dates.get(field_name, "")
            if date_val and date_val.strip().lower() not in skip_values:
                merged_dates[field_name] = date_val
        return merged_dates

    # Fallback: independent latest-wins scan (legacy behavior).
    merged_dates = {}
    for doc in sorted_docs:
        for field_name, date_val in doc.normalized_dates.items():
            if field_name in LEASE_ORIGIN_ONLY_FIELDS and doc.doc_type != "lease":
                continue
            if date_val and date_val.strip().lower() not in skip_values:
                merged_dates[field_name] = date_val

    return merged_dates
