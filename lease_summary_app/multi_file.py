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
    text: str = ""
    char_count: int = 0


@dataclass
class FieldHistory:
    """Tracks the history of a single field across documents."""
    current_value: str = ""
    current_date: str = ""  # mm/dd/yyyy
    current_source: str = ""  # filename
    history: List[dict] = field(default_factory=list)
    # Each history entry: {"value": str, "date": str, "source": str}


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

    # Amendment number extraction
    amendment_num = None
    ordinal_map = {
        "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5,
        "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10,
        "ELEVENTH": 11, "TWELFTH": 12,
    }

    for ordinal, num in ordinal_map.items():
        if ordinal + " AMENDMENT" in fname or ordinal + " AMENDMENT" in header:
            amendment_num = num
            break

    # Also check for "AMENDMENT NO. X" or "AMENDMENT #X"
    if amendment_num is None:
        match = re.search(r'AMENDMENT\s*(?:NO\.?|#)\s*(\d+)', fname)
        if not match:
            match = re.search(r'AMENDMENT\s*(?:NO\.?|#)\s*(\d+)', header)
        if match:
            amendment_num = int(match.group(1))

    # Document type classification
    if "LEASE AGREEMENT" in fname or "LEASE AGREEMENT" in header:
        if amendment_num:
            doc_type = "amendment"
        else:
            doc_type = "lease"
    elif "AMENDMENT" in fname or "AMENDMENT" in header:
        doc_type = "amendment"
    elif "COVID" in fname or "COVID" in header:
        doc_type = "covid_amendment"
    elif "OMNIBUS" in fname or "OMNIBUS" in header:
        doc_type = "omnibus_agreement"
    elif "TERMINATION" in fname or "TERMINATION" in header:
        doc_type = "termination"
    elif "ESTOPPEL" in fname or "ESTOPPEL" in header:
        doc_type = "estoppel"
    elif "SETTLEMENT" in fname or "SETTLEMENT" in header:
        doc_type = "settlement"
    elif "CHANGE REQUEST" in fname or "JDE" in fname:
        doc_type = "change_request"
    elif "RESOLUTION" in fname or "RESOLUTION" in header:
        doc_type = "resolution"
    elif "EXTENSION" in fname or "EXTENSION" in header:
        doc_type = "amendment"  # Extensions are amendments
    else:
        doc_type = "other"

    return doc_type, amendment_num


def sort_documents(docs: List[DocumentInfo]) -> List[DocumentInfo]:
    """
    Sort documents chronologically (oldest first).
    Uses execution_date if available, falls back to amendment number,
    then document type (lease before amendments).
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


def merge_fields(
    sorted_docs: List[DocumentInfo],
    skip_empty: bool = True,
) -> Dict[str, FieldHistory]:
    """
    Merge fields across documents in chronological order.
    Later documents override earlier ones. Changes are tracked as history.

    Args:
        sorted_docs: Documents sorted oldest → newest
        skip_empty: Don't count "None." / empty / "See Original Lease." as values

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

            value = value.strip()
            doc_date = doc.execution_date or "Unknown"
            doc_source = doc.filename

            if field_name not in merged:
                # First time seeing this field
                merged[field_name] = FieldHistory(
                    current_value=value,
                    current_date=doc_date,
                    current_source=doc_source,
                )
            else:
                existing = merged[field_name]
                # Check if value actually changed
                if _values_differ(existing.current_value, value):
                    # Push current to history
                    existing.history.append({
                        "value": existing.current_value,
                        "date": existing.current_date,
                        "source": existing.current_source,
                    })
                    # Update current
                    existing.current_value = value
                    existing.current_date = doc_date
                    existing.current_source = doc_source
                else:
                    # Same value, just update the date/source
                    existing.current_date = doc_date
                    existing.current_source = doc_source

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


def merge_normalized_dates(
    sorted_docs: List[DocumentInfo],
) -> Dict[str, str]:
    """
    Merge normalized dates across documents — latest wins.
    """
    merged_dates = {}
    skip_values = {'', 'tbd', 'none', 'unknown'}

    for doc in sorted_docs:
        for field_name, date_val in doc.normalized_dates.items():
            if date_val and date_val.strip().lower() not in skip_values:
                merged_dates[field_name] = date_val

    return merged_dates
