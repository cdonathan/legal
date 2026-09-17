"""
Field Variant Builder
=======================
Every extracted field now produces THREE output variables:

  FieldName        -- base value (kept for backward compatibility; usually
                       mirrors the Raw value)
  FieldName_Int     -- Interpretation: the precise, latest/superseding value
                       (or a plain-language reading of a clause), always
                       carrying a section reference when one is known.
  FieldName_Raw     -- Raw Data: the verbatim copy/paste from the source
                       document(s). For multi-document (lease + amendments)
                       summaries this includes EVERY historical version,
                       each tagged with its source document and section.

This module holds the shared formatting rules so that both the single-file
pipeline (engine.py) and the multi-file merge pipeline (multi_file.py) build
these three variants the same way.
"""

from typing import Dict, Iterable, Optional, Tuple

# Values the AI (or a human) uses to mean "nothing here" — all of these
# collapse to the literal string "None" in every output (DOCX/XML/JSON).
# This directly satisfies the rule: never show the raw variable name or a
# raw "None." with a stray period, always show exactly "None".
_NONE_MARKERS = {
    "", "none", "none.", "n/a", "na", "not applicable", "not applicable.",
    "not found", "not found.", "see original lease", "see original lease.",
    "see original agreement", "see original agreement.", "tbd",
}


def is_none_value(value: Optional[str]) -> bool:
    """True if a value should be treated as empty/not-applicable."""
    if value is None:
        return True
    v = value.strip().lower()
    if not v:
        return True
    return v in _NONE_MARKERS


# Markers that indicate a value could not be reliably resolved - typically a
# hand-written date/number the AI was told to flag rather than guess (see
# lease_summary_tool._fix_handwritten_dates and the HANDWRITTEN DATE HANDLING
# prompt rules in engine.py). If any of these markers are still present in a
# value by the time it reaches display, the extraction/AI resolution steps
# failed to resolve it - it must never be shown as a bare, seemingly-valid
# value (e.g. a wrong date presented with total confidence).
_NEEDS_VERIFICATION_MARKERS = ("[handwritten", "needs verification")


def needs_verification(value: Optional[str]) -> bool:
    """True if a value still carries an unresolved-handwriting/uncertainty marker."""
    if not value:
        return False
    v = value.lower()
    return any(marker in v for marker in _NEEDS_VERIFICATION_MARKERS)


def clean_value(value: Optional[str]) -> str:
    """Normalize a raw value: 'None'-like inputs become the literal 'None'.
    Values that still carry an unresolved handwriting/uncertainty marker
    become the literal 'NEEDS VERIFICATION' rather than leaking raw
    bracket-syntax or a low-confidence guess into the output."""
    if needs_verification(value):
        return "NEEDS VERIFICATION"
    if is_none_value(value):
        return "None"
    return value.strip()


def format_interpretation(value: Optional[str], section: Optional[str] = "", suppress_section: bool = False) -> str:
    """
    Build the Interpretation column text.
    Rule: if there IS data, include the section reference (e.g. "Section
    3.8" or "Amendment: Section 1") UNLESS suppress_section is True. If
    there is no data, just "None" (no section reference needed).

    suppress_section: pass True for trivial bare-fact fields (address
    lines, city, zip, phone, email, attn name - typically an agreement
    type's `short_fields`) where a section tag adds noise rather than
    useful verification context, e.g. a multi-line address reads far more
    clearly without every line individually suffixed "(REFERENCE PROVISIONS)".
    """
    if needs_verification(value):
        return "NEEDS VERIFICATION"
    if is_none_value(value):
        return "None"
    v = value.strip()
    if suppress_section:
        return v
    sec = (section or "").strip()
    if sec:
        return f"{v} ({sec})"
    return v


def format_raw_single(value: Optional[str], section: Optional[str] = "", doc_label: str = "") -> str:
    """
    Build the Raw Data column text for a SINGLE document (no amendment
    history yet). Tags the value with the document/section it came from
    when known, e.g. "[Lease, Section 3.8]: <verbatim text>".
    """
    if needs_verification(value):
        return f"NEEDS VERIFICATION (source text: {value.strip()})"
    if is_none_value(value):
        return "None"
    v = value.strip()
    tag_bits = [b for b in [doc_label.strip() if doc_label else "", (section or "").strip()] if b]
    if tag_bits:
        return f"[{', '.join(tag_bits)}]: {v}"
    return v


def build_field_variants(
    field_names: Iterable[str],
    field_data: Dict[str, str],
    interpretations: Optional[Dict[str, str]] = None,
    sections: Optional[Dict[str, str]] = None,
    doc_label: str = "",
    short_fields: Optional[Iterable[str]] = None,
) -> Dict[str, str]:
    """
    Expand a flat {field: raw_value} dict (plus parallel interpretation/section
    dicts) into the full 3-variable-per-field dict:
        {field: base, field_Int: interpretation, field_Raw: raw}
    used for the SINGLE-FILE pipeline (one document, no amendment history).

    short_fields: field names (typically agreement_type.short_fields) whose
    Interpretation column should omit the "(Section X)" tag - these are
    trivial bare facts (address lines, city, zip, email, etc.) where a
    section reference is noise, not useful verification context.
    """
    interpretations = interpretations or {}
    sections = sections or {}
    short_fields = set(short_fields) if short_fields else set()
    out: Dict[str, str] = {}

    for f in field_names:
        raw_val = field_data.get(f, "")
        section_val = sections.get(f, "")
        interp_val = interpretations.get(f, "") or raw_val

        base_clean = clean_value(raw_val)
        out[f] = base_clean
        out[f"{f}_Int"] = format_interpretation(interp_val, section_val, suppress_section=f in short_fields)
        out[f"{f}_Raw"] = format_raw_single(raw_val, section_val, doc_label)

    return out


# Ordinal labels reused across the multi-file merge for amendment naming.
ORDINALS = {
    1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth",
    6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth", 10: "Tenth",
    11: "Eleventh", 12: "Twelfth",
}


def doc_type_label(doc_type: str, amendment_number: Optional[int] = None, fallback: str = "") -> str:
    """Human-readable label for a document, used for Raw tags and qualified
    section references (e.g. 'First Amendment')."""
    if doc_type == "lease":
        return "Lease"
    if doc_type == "guaranty":
        return "Guaranty Agreement"
    if doc_type == "amendment":
        if amendment_number:
            ordinal = ORDINALS.get(amendment_number, f"#{amendment_number}")
            return f"{ordinal} Amendment"
        return "Amendment"
    if doc_type == "covid_amendment":
        return "COVID-19 Amendment"
    if doc_type == "omnibus_agreement":
        return "Omnibus Agreement"
    if doc_type == "termination":
        return "Termination Notice"
    if doc_type == "estoppel":
        return "Estoppel Certificate"
    if doc_type == "settlement":
        return "Settlement Agreement"
    if doc_type == "change_request":
        return "Change Request"
    if doc_type == "resolution":
        return "Resolution"
    return fallback or (doc_type.replace("_", " ").title() if doc_type else "Document")


def qualify_section(section: Optional[str], doc_type: str, amendment_number: Optional[int] = None,
                     fallback_label: str = "") -> str:
    """
    Combine a bare section reference (e.g. 'Section 3.8') with its document
    context. For the original lease, the section is used as-is. For any
    other document (amendment, addendum, etc.) it's prefixed with the
    document label, e.g. 'Amendment: Section 1' or 'First Amendment: Section 1'.
    """
    sec = (section or "").strip()
    if doc_type == "lease":
        return sec
    label = doc_type_label(doc_type, amendment_number, fallback_label)
    if not sec:
        return label
    return f"{label}: {sec}"
