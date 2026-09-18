"""
SeedJura Agreement Analysis Engine
====================================
Generic pipeline for processing any agreement type.
Agreement-specific knowledge comes from AgreementType configs.

This module provides the same pipeline as lease_summary_tool.py but
driven by pluggable agreement type configurations rather than hardcoded
lease fields.

Pipeline:
  1. Ingest document (PDF/DOCX/TXT)
  2. PII scan
  3. AI field extraction (using agreement type's fields + prompts)
  4. Source verification (using agreement type's anchors + field sets)
  5. AI retry for flagged fields
  6. Template population
"""

import os
import sys
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, List, Optional

# Ensure parent dir is on path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lease_summary_tool import (
    ingest_document,
    redact_and_capture_pii,
    get_openai_client,
    _normalize_text,
    _find_best_match,
    _map_normalized_pos_to_original,
    _find_sentence_start,
    _find_sentence_end,
    _verify_ai_anchor,
    populate_template as _populate_template_raw,
    AI_MODEL,
)

from agreement_types import get_type, detect_agreement_type, list_types
from agreement_types.base import AgreementType
from multi_file import DATE_SEARCH_WINDOW_CHARS

try:
    from errors import ProcessingError
except ImportError:
    class ProcessingError(Exception):
        """Fallback if errors.py isn't importable in this context."""
        kind = ""


# =============================================================================
# AI EXTRACTION - AGREEMENT-TYPE DRIVEN
# =============================================================================

def build_extraction_prompt(
    agreement: AgreementType,
    text: str,
    sub_type: str = "",
    only_fields: Optional[Dict[str, str]] = None,
    require_all: bool = True,
) -> str:
    """
    Build AI extraction prompt from agreement type config.

    only_fields: if given, restricts the fields the prompt asks for to this
    subset (e.g. excluding lease-only fields like insurance/OPEX/SNDA for an
    amendment, or restricting to just the guaranty fields for a guaranty doc).
    Defaults to agreement.fields (every field) when not given.

    require_all: if False, the model is told to OMIT fields it doesn't find
    addressed in this document entirely, rather than writing "None."/"See
    Original Lease." placeholders for every unaddressed field. This is for
    amendments/addenda/guaranty docs where most fields legitimately don't
    apply - it keeps the response (and generation time) small. The calling
    code is responsible for filling in defaults for any field the model
    omits.
    """
    fields = only_fields if only_fields is not None else agreement.fields
    fields_list = "\n".join(
        f'  "{k}": "{v}"' for k, v in fields.items()
    )

    # Sub-type instruction (e.g., amendment-specific rules)
    sub_type_instruction = ""
    if sub_type and sub_type != agreement.type_id:
        sub_type_instruction = agreement.get_sub_type_instruction(sub_type)
        if sub_type_instruction:
            sub_type_instruction = f"\n{sub_type_instruction}\n"

    # Use agreement-specific extraction rules, or fall back to generic
    extraction_rules = agreement.extraction_rules or _DEFAULT_EXTRACTION_RULES

    omission_instruction = ""
    if not require_all:
        omission_instruction = """
IMPORTANT - OMIT UNADDRESSED FIELDS:
This document only addresses SOME of the fields below. For any field this
document does NOT mention or modify, OMIT that field's key from your JSON
response entirely - do NOT write "None.", "See Original Lease.", or any
other placeholder for it. Only include keys for fields this document
actually addresses. This keeps your response focused and fast.
"""

    prompt = f"""You are a legal document analyst. Analyze the following document and extract the requested information into a JSON object.
{sub_type_instruction}{omission_instruction}
{extraction_rules}

HANDWRITTEN DATE HANDLING:
- This document may contain OCR artifacts from handwritten dates on fill-in-the-blank templates.
- If you see "[handwritten: X]" or "[handwritten-year: X]" markers, the original handwritten text was garbled by OCR. Use context clues to resolve it, in this priority order:
  1. A "[RE-OCR CROSS-CHECK ...]" block elsewhere in the document text - this is a fresh, higher-resolution re-scan of the SAME page and is usually far more legible than the original garbled text.
  2. Other places in this document (or other documents, if provided) that restate the same date in clean text, e.g. an amendment's recital saying "Under the lease dated July 30, 2007".
  3. Nearby context clues (execution dates, commencement dates, surrounding text).
- Common OCR misreads: "Bias" = "1st", "Znd" = "2nd", garbled text before "day of <Month>" = a handwritten day number.
- CRITICAL: Only resolve a garbled date if you can genuinely read it with confidence from the clues above. Do NOT invent or guess a plausible-looking date. If a date field remains genuinely illegible/ambiguous after checking all the clues above, set "text" to "NEEDS VERIFICATION" and "date" to "NEEDS VERIFICATION" rather than fabricating a value - a human will need to check the original document.

RESPONSE FORMAT - EVERY FIELD RETURNS UP TO FOUR KEYS:
Return a JSON object where EVERY field maps to an object with these keys:
- "text": The RAW, verbatim copy/paste of the exact language from the document. Never summarize this. This is the "Raw Data". This is the ONLY key that requires careful verbatim copying - do not spend effort rephrasing or interpreting it.
- "section": The section/article number this value comes from, exactly as labeled in the document (e.g. "Section 3.8", "Article 7", "Sec. 12(b)"). Empty string "" if genuinely not identifiable. Do not restate the document name here (e.g. do not write "Lease, Section 3.8" - just "Section 3.8"); the calling code adds document context separately.
- "anchor": The first 8 words of the source sentence where "text" was found (used to verify location). Empty string "" is fine for short values (names, amounts, Yes/No, dates).
- "date": ONLY for date fields (Date_Lease, Date_Commencment, Date_Expiration, Date_EarlyAccess, Rent_Abatement_Commencement, Rent_Abatement_Expiration, Date_Opening, or any other date-related field): your best-guess normalized date in mm/dd/yyyy format, or "TBD" if it truly cannot be determined. Omit this key entirely for non-date fields.

Do NOT include an "interpretation" key - a separate pass handles that. Focus entirely on fast, accurate verbatim extraction.

Example - simple fact field:
  "Amt_Security_Deposit": {{"text": "Thirteen Thousand Eight Hundred Twenty-Five and 00/100 Dollars ($13,825.00)", "section": "Section 4", "anchor": ""}}

Example - date field:
  "Date_Lease": {{"text": "1st day of March, 2021", "section": "", "date": "03/01/2021", "anchor": ""}}

Example - clause:
  "Tenant_Insurance": {{"text": "...(a) Bodily injury...One Million Dollars...(b) Insurance covering all of Tenant's furniture...(c) In addition to naming Landlord's lender...", "section": "Section 15", "anchor": "At all times during the Term Tenant"}}

Example - nothing found:
  "Base_Year": {{"text": "None.", "section": "", "anchor": ""}}

FIELDS TO EXTRACT (field_name: description):
{fields_list}

DOCUMENT TEXT:
{text[:80000]}

Respond with ONLY a valid JSON object. No markdown, no explanation."""

    return prompt


def _attempt_json_recovery(raw: str) -> dict:
    """
    Attempt to recover a partially broken JSON response from the AI.
    Common issues: unescaped quotes inside values, trailing commas, truncation.
    """
    import re

    # Strategy 1: Try fixing unescaped newlines and quotes inside string values
    # Replace literal newlines inside JSON string values
    fixed = raw.replace('\r\n', '\\n').replace('\r', '\\n')

    # Strategy 2: Try parsing line by line, extracting key-value pairs
    # This handles the case where one field has bad JSON but others are fine
    results = {}
    # Match pattern: "FieldName": {"text": "...", "anchor": "..."}
    # or "FieldName": "value"
    pattern = r'"([^"]+)"\s*:\s*\{["\s]*text["\s]*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*["\s]*anchor["\s]*:\s*"((?:[^"\\]|\\.)*)"\s*\}'
    matches = re.finditer(pattern, raw, re.DOTALL)
    for m in matches:
        key = m.group(1)
        text = m.group(2).replace('\\n', '\n').replace('\\"', '"')
        anchor = m.group(3).replace('\\n', '\n').replace('\\"', '"')
        results[key] = {"text": text, "anchor": anchor}

    # Also try flat format: "FieldName": "value"
    if not results:
        pattern_flat = r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"'
        matches = re.finditer(pattern_flat, raw)
        for m in matches:
            key = m.group(1)
            val = m.group(2).replace('\\n', '\n').replace('\\"', '"')
            if key not in results and key not in ("text", "anchor"):
                results[key] = val

    if results:
        print(f"  JSON recovery: extracted {len(results)} fields from malformed response")
        return results

    # Strategy 3: Try truncating at the error point and parsing what we have
    # Find the last complete field entry
    last_good = raw.rfind('"}')
    if last_good > 0:
        truncated = raw[:last_good + 2] + "}"
        try:
            parsed = json.loads(truncated)
            print(f"  JSON recovery (truncation): extracted {len(parsed)} fields")
            return parsed
        except json.JSONDecodeError:
            pass

    return {}


def _make_ai_error(message: str, detail: str = "", kind: str = ""):
    """Create an AIServiceError, importing lazily to avoid circular deps."""
    try:
        from errors import AIServiceError
        return AIServiceError(message, detail, kind=kind)
    except ImportError:
        return RuntimeError(message)


def _call_openai_with_retry(client, messages, max_tokens, max_retries=3, timeout=120):
    """
    Call the OpenAI chat API with retry logic for transient failures.
    Raises AIServiceError with a user-friendly message on permanent failure.
    The raised error's `.kind` distinguishes failure categories so callers
    can react differently (e.g. a circuit breaker on repeated timeouts):
      "timeout"  - every attempt exhausted its timeout (service is slow/hung)
      "auth"     - bad/expired API key
      "quota"    - billing/quota exhausted
      "transient" - all retries failed for some other reason (network, etc.)
    """
    import time

    last_error = None
    timeout_count = 0
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=AI_MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                timeout=timeout,
            )
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            err_type = type(e).__name__
            if "timeout" in err_type.lower() or "timeout" in err_str:
                timeout_count += 1

            # Permanent errors — don't retry
            if "authentication" in err_str or "api key" in err_str or "invalid_api_key" in err_str:
                raise _make_ai_error(
                    "OpenAI API authentication failed. Check that your API key "
                    "is valid and has not expired.", str(e), kind="auth",
                )
            if "insufficient_quota" in err_str or "quota" in err_str or "billing" in err_str:
                raise _make_ai_error(
                    "OpenAI API quota exceeded or billing issue. Check your "
                    "OpenAI account balance and usage limits.", str(e), kind="quota",
                )

            # Transient errors — retry with backoff
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"  AI call failed ({err_type}), retrying in {wait}s... "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue

    # All retries exhausted
    if timeout_count == max_retries:
        raise _make_ai_error(
            f"OpenAI request timed out on all {max_retries} attempts ({timeout}s each). "
            "The service appears to be slow or unresponsive right now.",
            str(last_error), kind="timeout",
        )
    raise _make_ai_error(
        "Could not reach the OpenAI service after several attempts. "
        "Check your internet connection and try again.",
        str(last_error), kind="transient",
    )


def classify_documents_with_ai(
    doc_types: Dict[str, str],
    doc_headers: Optional[Dict[str, str]] = None,
) -> dict:
    """
    AI-assisted document classification for a multi-file folder - reads only
    filenames (plus a short header excerpt when available) to determine
    which document is the ORIGINAL LEASE and which is the LATEST amendment/
    modification, ordering every amendment-like document chronologically.

    This exists because filename-only regex heuristics (ordinal words like
    "First"/"Seventh", "AMENDMENT NO. 4", etc.) break down in real-world
    folders: amendment documents routinely recite the lease's full
    amendment history in their own header text (e.g. an amendment's recital
    saying "...as amended by a First Amendment... a Second Amendment...")
    which can fool simple text matching, and naming conventions vary a lot
    between landlords/law firms (e.g. "Extension and Fourth Amendment" vs.
    a plain "Amendment No. 4" vs. a date-only filename). A model reading the
    filenames (and a little header context) in relation to each other can
    reason about this the way a person would, rather than relying on brittle
    keyword ordinal matching.

    Args:
        doc_types: {filename: doc_type} - the pre-computed doc_type per file
          (from classify_document's type detection, which is reliable) so
          the model only has to reason about ORDERING, not re-classify type.
        doc_headers: optional {filename: first ~500 chars of that document},
          used as tie-breaking context when filenames alone are ambiguous
          (e.g. two differently-named files that are otherwise unclear).

    Returns a dict:
        {
          "lease_filename": str or None,
          "latest_filename": str or None,
          "ordered_amendments": [filename, ...]  # oldest -> newest, amendment-like docs only
        }
    Raises AIServiceError on failure (auth/quota/timeout) - callers should
    catch this and fall back to the filename-heuristic ordering rather than
    fail the whole job over a classification-ordering call.
    """
    doc_headers = doc_headers or {}
    client = get_openai_client()

    filenames = list(doc_types.keys())
    lines = []
    for fname in filenames:
        entry = f'  "{fname}": type={doc_types[fname]}'
        header = doc_headers.get(fname, "")
        if header:
            entry += f'\n    header excerpt: "{header[:300]}"'
        lines.append(entry)
    listing = "\n".join(lines)

    prompt = f"""You are analyzing a folder of lease-related documents to determine their
chronological relationship. Each document's filename and pre-determined document
type is listed below (type was already determined by keyword matching and is
reliable - do not second-guess it). Some documents also include a short header
excerpt for context when the filename alone is ambiguous.

DOCUMENTS:
{listing}

TASK:
1. Identify which single document is the ORIGINAL LEASE (type=lease). There should be at most one.
2. Order every document whose type indicates it modifies/relates to the lease
   (amendment, covid_amendment, omnibus_agreement, change_request, resolution,
   settlement, termination, estoppel, other) chronologically from OLDEST to NEWEST,
   using ordinal words in the filename ("First", "Second", "Extension and Fourth",
   "Seventh"...), explicit numbers ("Amendment No. 4"), dates in the filename, and
   header excerpt context together - reason about what actually makes sense
   chronologically, not just string matching. Guaranty documents and documents with
   type "guaranty" should be EXCLUDED from this ordering entirely.
3. Identify which one of those ordered documents is the LATEST (most recent) -
   normally the last one in your chronological ordering, but use judgment (e.g. a
   Termination Notice or Settlement Agreement that clearly post-dates every
   amendment should be considered "latest" if it's the most recent lease-related
   event, even though it's a different document type).

Respond with ONLY a JSON object in this exact shape:
{{
  "lease_filename": "<exact filename or null>",
  "latest_filename": "<exact filename or null>",
  "ordered_amendments": ["<exact filename>", "..."]
}}

Use the EXACT filenames as given above (case-sensitive, including punctuation)."""

    response = _call_openai_with_retry(
        client,
        messages=[
            {"role": "system", "content": "You are a meticulous legal document analyst who reasons carefully about chronological ordering of lease amendments from filenames and context."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = _attempt_json_recovery(raw) or {}

    # Validate every returned filename actually exists in the input set -
    # never trust the model to invent or slightly-misspell a filename.
    valid_names = set(filenames)
    lease_filename = parsed.get("lease_filename")
    if lease_filename not in valid_names:
        lease_filename = None
    latest_filename = parsed.get("latest_filename")
    if latest_filename not in valid_names:
        latest_filename = None
    ordered_amendments = [f for f in parsed.get("ordered_amendments", []) if f in valid_names]

    return {
        "lease_filename": lease_filename,
        "latest_filename": latest_filename,
        "ordered_amendments": ordered_amendments,
    }


def analyze_with_ai(
    agreement: AgreementType,
    text: str,
    sub_type: str = "",
    only_fields: Optional[Dict[str, str]] = None,
    require_all: bool = True,
) -> Tuple[dict, dict, dict, dict]:
    """
    CALL 1 - Raw extraction only.
    Send document text to AI for VERBATIM field extraction using agreement type config.
    Interpretation is handled separately by interpret_fields() (Call 2) so this call's
    output stays small and fast to generate.

    only_fields / require_all: see build_extraction_prompt(). Use these to scope
    a call down to just the fields a document type can plausibly address (e.g.
    an amendment or a guaranty), and to let the model omit fields it doesn't
    address instead of writing a placeholder for every one of them.

    Returns (field_data, anchors, dates, sections).
    - field_data: {field_name: raw verbatim extracted_text} - only contains keys
      the model actually returned (i.e. every requested field when require_all
      is True; only the addressed subset when require_all is False).
    - anchors: {field_name: anchor_phrase}
    - dates: {field_name: "mm/dd/yyyy"} for date fields
    - sections: {field_name: section/article reference, e.g. "Section 3.8"}
    """
    print("  Sending to AI for raw extraction (Call 1)...")

    try:
        client = get_openai_client()
    except RuntimeError as e:
        # No API key
        raise _make_ai_error(
            "OpenAI API key not found. Place your key in "
            "C:\\seedJura\\openai_api_key.txt or set the OPENAI_API_KEY "
            "environment variable.",
            str(e),
        )

    prompt = build_extraction_prompt(
        agreement, text, sub_type=sub_type, only_fields=only_fields, require_all=require_all,
    )
    system_prompt = agreement.system_prompt or _DEFAULT_SYSTEM_PROMPT

    response = _call_openai_with_retry(
        client,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=16000,
    )

    raw_response = response.choices[0].message.content.strip()

    # Clean potential markdown wrapping
    if raw_response.startswith("```"):
        raw_response = re.sub(r"^```(?:json)?\s*", "", raw_response)
        raw_response = re.sub(r"\s*```$", "", raw_response)

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as e:
        print(f"  WARNING: AI response not valid JSON: {e}")
        print(f"  Raw response (first 500 chars): {raw_response[:500]}")
        # Attempt recovery: try to fix common JSON issues
        parsed = _attempt_json_recovery(raw_response)
        if not parsed:
            return {}, {}, {}, {}

    # Parse format: {"field": {"text": "...", "section": "...",
    #                           "anchor": "...", "date": "..."}} or flat
    field_data = {}
    anchors = {}
    dates = {}  # Normalized dates in mm/dd/yyyy for date fields
    sections = {}

    for key, val in parsed.items():
        if isinstance(val, dict):
            field_data[key] = val.get("text", "")
            anchors[key] = val.get("anchor", "")
            if "date" in val and val["date"]:
                dates[key] = val["date"]
            if "section" in val and val["section"]:
                sections[key] = val["section"]
        else:
            field_data[key] = val if val else ""
            anchors[key] = ""

    filled = sum(1 for v in field_data.values() if v)
    field_count = len(only_fields) if only_fields is not None else len(agreement.fields)
    print(f"  AI extracted {filled}/{field_count} fields")
    anchored = sum(1 for v in anchors.values() if v)
    print(f"  AI provided {anchored} anchor phrases")
    if dates:
        print(f"  AI normalized {len(dates)} date(s)")
    if sections:
        print(f"  AI provided {len(sections)} section reference(s)")
    return field_data, anchors, dates, sections


def _parse_extraction_json(parsed: dict) -> Tuple[dict, dict, dict, dict]:
    """Shared parsing of one document's {"field": {"text","section","anchor","date"}}
    block into the (field_data, anchors, dates, sections) 4-tuple shape used
    throughout the pipeline. Factored out of analyze_with_ai so the combined
    two-document call (analyze_combined_with_ai) can reuse it for each side."""
    field_data, anchors, dates, sections = {}, {}, {}, {}
    for key, val in (parsed or {}).items():
        if isinstance(val, dict):
            field_data[key] = val.get("text", "")
            anchors[key] = val.get("anchor", "")
            if val.get("date"):
                dates[key] = val["date"]
            if val.get("section"):
                sections[key] = val["section"]
        else:
            field_data[key] = val if val else ""
            anchors[key] = ""
    return field_data, anchors, dates, sections


def build_combined_extraction_prompt(
    agreement: AgreementType,
    lease_text: str,
    latest_text: str,
    latest_sub_type: str,
    latest_label: str,
) -> str:
    """
    Build the Call 1 prompt that reads the ORIGINAL LEASE and the LATEST
    AMENDMENT together, in one pass. Reading them together lets the model
    resolve "what is the current value of each field" correctly in context
    (e.g. an amendment saying "extend the term by 12 months" only resolves
    correctly next to the original term) - rather than reading them separately
    and reconciling values in code afterward.

    The lease side asks for a FULL extraction (every field). The latest-doc
    side asks the model to OMIT fields that amendment doesn't address - most
    amendments only touch a handful of fields.
    """
    fields_list = "\n".join(f'  "{k}": "{v}"' for k, v in agreement.fields.items())
    extraction_rules = agreement.extraction_rules or _DEFAULT_EXTRACTION_RULES

    sub_type_instruction = ""
    if latest_sub_type and latest_sub_type != agreement.type_id:
        instr = agreement.get_sub_type_instruction(latest_sub_type)
        if instr:
            sub_type_instruction = f"\n{instr}\n"

    return f"""You are a legal document analyst. You are given TWO related documents: the
ORIGINAL LEASE AGREEMENT, and the LATEST AMENDMENT to that lease (the most recent
change on file). Read them TOGETHER so you can resolve the CURRENT value of each
field correctly - the latest amendment may modify, extend, or override provisions
from the original lease.

{extraction_rules}
{sub_type_instruction}
HANDWRITTEN DATE HANDLING:
- Documents may contain OCR artifacts from handwritten dates on fill-in-the-blank templates.
- If you see "[handwritten: X]" or "[handwritten-year: X]" markers, use context clues to resolve it - check any "[RE-OCR CROSS-CHECK ...]" block (a fresh, higher-resolution re-scan of the same page) first, then other restatements of the same date in either document (e.g. an amendment's recital), then surrounding context.
- Common OCR misreads: "Bias" = "1st", "Znd" = "2nd".
- CRITICAL: Only resolve a garbled date if you can genuinely read it with confidence. Do NOT guess a plausible-looking date. If it remains illegible/ambiguous, set "text" and "date" to "NEEDS VERIFICATION" instead of fabricating a value.

RESPONSE FORMAT:
Return a JSON object with exactly two top-level keys: "lease" and "amendment".

"lease": a FULL extraction from the ORIGINAL LEASE ONLY - every field below,
even if the amendment later changes it. Map each field name to an object with
keys "text" (verbatim from the LEASE), "section", "anchor", and "date" (date
fields only). If a field is not found in the lease, "text" is "None.".

"amendment": extraction from the LATEST AMENDMENT ONLY (labeled "{latest_label}"
below) - but ONLY for fields this amendment actually addresses/modifies. OMIT
any field key this amendment does not mention - do NOT write "None." or "See
Original Lease." placeholders for fields it doesn't address. Same object shape
("text"/"section"/"anchor"/"date") for each field you do include.

Example:
{{
  "lease": {{
    "Lease_Term": {{"text": "sixty (60) months", "section": "Section 3", "anchor": ""}},
    "Base_Year": {{"text": "None.", "section": "", "anchor": ""}}
  }},
  "amendment": {{
    "Lease_Term": {{"text": "extended by twelve (12) months through January 31, 2027", "section": "Section 2", "anchor": "The Term is hereby extended"}}
  }}
}}

FIELDS TO EXTRACT (field_name: description):
{fields_list}

=== ORIGINAL LEASE AGREEMENT ===
{lease_text[:70000]}

=== LATEST AMENDMENT ({latest_label}) ===
{latest_text[:30000]}

Respond with ONLY a valid JSON object with the "lease" and "amendment" keys. No markdown, no explanation."""


def analyze_combined_with_ai(
    agreement: AgreementType,
    lease_text: str,
    latest_text: str,
    latest_sub_type: str = "",
    latest_label: str = "Latest Amendment",
) -> Tuple[Tuple[dict, dict, dict, dict], Tuple[dict, dict, dict, dict]]:
    """
    CALL 1 (multi-file) - Combined raw extraction for the lease + latest
    amendment together, in a single AI call. See build_combined_extraction_prompt
    for why these two documents are read together instead of separately.

    Returns (lease_result, amendment_result), each a (field_data, anchors,
    dates, sections) 4-tuple in the same shape analyze_with_ai returns. The
    amendment_result's field_data only contains keys the model chose to
    address - the caller fills in defaults for the rest.
    """
    print("  Sending to AI for combined raw extraction (Call 1: lease + latest amendment)...")

    try:
        client = get_openai_client()
    except RuntimeError as e:
        raise _make_ai_error(
            "OpenAI API key not found. Place your key in "
            "C:\\seedJura\\openai_api_key.txt or set the OPENAI_API_KEY "
            "environment variable.",
            str(e),
        )

    prompt = build_combined_extraction_prompt(agreement, lease_text, latest_text, latest_sub_type, latest_label)
    system_prompt = agreement.system_prompt or _DEFAULT_SYSTEM_PROMPT

    response = _call_openai_with_retry(
        client,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=16000,
    )

    raw_response = response.choices[0].message.content.strip()
    if raw_response.startswith("```"):
        raw_response = re.sub(r"^```(?:json)?\s*", "", raw_response)
        raw_response = re.sub(r"\s*```$", "", raw_response)

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as e:
        print(f"  WARNING: AI response not valid JSON: {e}")
        parsed = _attempt_json_recovery(raw_response)
        if not parsed:
            parsed = {}

    lease_result = _parse_extraction_json(parsed.get("lease", {}) if isinstance(parsed, dict) else {})
    amendment_result = _parse_extraction_json(parsed.get("amendment", {}) if isinstance(parsed, dict) else {})

    lease_filled = sum(1 for v in lease_result[0].values() if v)
    amendment_filled = sum(1 for v in amendment_result[0].values() if v)
    print(f"  Lease: {lease_filled}/{len(agreement.fields)} fields")
    print(f"  {latest_label}: {amendment_filled} field(s) addressed")

    return lease_result, amendment_result


def analyze_documents_parallel(
    agreement: AgreementType,
    doc_jobs: List[dict],
    max_workers: int = 4,
    on_progress=None,
) -> Dict[str, Tuple[dict, dict, dict, dict]]:
    """
    CALL 2 (multi-file) - Raw extraction for a batch of secondary documents
    (earlier amendments, guaranty, etc.) run concurrently. Each job is scoped
    to only the fields that document type can plausibly address (via
    only_fields) and allowed to omit unaddressed fields (require_all=False),
    so these calls stay small and fast - these documents are read purely for
    history/audit trail, not for determining current values.

    doc_jobs: list of dicts, each with keys:
      "key"          - identifier (e.g. filename), used in the returned dict
      "text"         - document text
      "sub_type"     - sub-type for prompt instructions (e.g. "amendment")
      "only_fields"  - dict subset of agreement.fields to request
      "require_all"  - bool, usually False for these secondary documents

    on_progress(done, total): optional callback fired after each document
    completes (success or failure), for live progress reporting.

    Returns {key: (field_data, anchors, dates, sections)}. A document whose
    call fails non-fatally (isolated per-doc failure) maps to all-empty dicts
    so the pipeline can continue with the rest.

    Fatal conditions (raised, not swallowed): auth/quota errors (no point
    burning further calls on a dead account), and a timeout circuit breaker -
    if roughly half or more of the batch times out, the remaining jobs are
    aborted rather than each grinding through its own full retry cycle.
    """
    if not doc_jobs:
        return {}

    try:
        client = get_openai_client()
    except RuntimeError as e:
        raise _make_ai_error(
            "OpenAI API key not found. Place your key in "
            "C:\\seedJura\\openai_api_key.txt or set the OPENAI_API_KEY "
            "environment variable.",
            str(e),
        )

    print(f"  Sending to AI for batch raw extraction (Call 2): {len(doc_jobs)} document(s), "
          f"up to {max_workers} in parallel...")

    def _run_one(job: dict) -> Tuple[dict, dict, dict, dict]:
        prompt = build_extraction_prompt(
            agreement, job["text"], sub_type=job.get("sub_type", ""),
            only_fields=job.get("only_fields"), require_all=job.get("require_all", False),
        )
        system_prompt = agreement.system_prompt or _DEFAULT_SYSTEM_PROMPT
        response = _call_openai_with_retry(
            client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8000,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = _attempt_json_recovery(raw)
        return _parse_extraction_json(parsed or {})

    results: Dict[str, Tuple[dict, dict, dict, dict]] = {}
    timeout_failures = 0
    timeout_circuit_breaker = max(2, len(doc_jobs) // 2)
    tripped = False
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {executor.submit(_run_one, job): job for job in doc_jobs}
        for future in as_completed(future_to_job):
            job = future_to_job[future]
            key = job["key"]
            try:
                results[key] = future.result()
                filled = sum(1 for v in results[key][0].values() if v)
                print(f"    [{key}]: {filled} field(s) addressed")
            except Exception as e:
                kind = getattr(e, "kind", "")
                if kind in ("auth", "quota"):
                    # Dead account - no point continuing to burn calls.
                    for f in future_to_job:
                        f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise
                print(f"    [{key}] FAILED: {e}")
                results[key] = ({}, {}, {}, {})
                if kind == "timeout":
                    timeout_failures += 1
                if timeout_failures >= timeout_circuit_breaker and not tripped:
                    tripped = True
                    print(f"    Circuit breaker: {timeout_failures} document(s) timed out - "
                          f"aborting remaining documents.")
                    for f in future_to_job:
                        f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    completed += 1
                    if on_progress:
                        try:
                            on_progress(completed, len(doc_jobs))
                        except Exception:
                            pass
                    break

            completed += 1
            if on_progress:
                try:
                    on_progress(completed, len(doc_jobs))
                except Exception:
                    pass

    if tripped:
        raise _make_ai_error(
            f"Batch extraction aborted: {timeout_failures}/{len(doc_jobs)} document(s) timed out. "
            "The OpenAI service appears to be slow or unresponsive right now.",
            "", kind="circuit_breaker",
        )

    print(f"  Batch extraction complete: {len(results)}/{len(doc_jobs)} document(s) processed")
    return results


# =============================================================================
# SOURCE VERIFICATION - AGREEMENT-TYPE DRIVEN
# =============================================================================

# Anchor patterns in field_anchors.json chain multiple ".*" wildcards
# together (e.g. "tenant.*pay.*utility charges"). That's fine matched
# against a short snippet, but against a full multi-hundred-thousand-
# character document it causes catastrophic exponential regex backtracking
# when no match exists nearby - this hung the server indefinitely on real
# documents. Bounding every ".*" to a fixed max span makes matching
# effectively linear and eliminates the blowup. 300 chars is generous
# slack for "these words appear near each other in the same clause", which
# is what these anchors are meant to catch anyway.
_ANCHOR_WILDCARD_BOUND = 300


def _bound_anchor_pattern(pattern: str) -> str:
    """Replace unbounded '.*' in an anchor regex with a bounded quantifier."""
    return pattern.replace('.*', f'.{{0,{_ANCHOR_WILDCARD_BOUND}}}')


def _keyword_fallback_search(field_name: str, source_text: str, field_anchors: dict) -> Optional[str]:
    """
    Keyword anchor fallback search using agreement type's field_anchors.
    """
    anchors = field_anchors.get(field_name)
    if not anchors:
        return None

    norm_source = _normalize_text(source_text)

    # First pass: exact regex matching (wildcards bounded - see
    # _bound_anchor_pattern - to avoid catastrophic backtracking against
    # full-length document text).
    for anchor in anchors:
        try:
            match = re.search(_bound_anchor_pattern(anchor), norm_source)
        except re.error:
            continue
        if match:
            norm_start = match.start()
            orig_start = _map_normalized_pos_to_original(source_text, norm_start)
            sentence_start = _find_sentence_start(source_text, orig_start)
            norm_end_pos = match.end()
            orig_end = _map_normalized_pos_to_original(source_text, norm_end_pos)
            sentence_end = _find_sentence_end(source_text, orig_end)

            extracted = source_text[sentence_start:sentence_end].strip()
            extracted = re.sub(r'[ \t]+', ' ', extracted)
            extracted = re.sub(r'\n{3,}', '\n', extracted)
            extracted = re.sub(r'^\s*\n', '', extracted)
            extracted = re.sub(r'^[\d\s]{1,5}(?=\s*[A-Z])', '', extracted).strip()

            if len(extracted) > 600:
                cut_pos = extracted.rfind('. ', 0, 600)
                if cut_pos > len(extracted) // 3:
                    extracted = extracted[:cut_pos + 1]
                else:
                    extracted = extracted[:600]

            if len(extracted) > 20:
                return extracted

    # Second pass: fuzzy matching
    try:
        from thefuzz import fuzz
    except ImportError:
        return None

    for anchor in anchors:
        plain = re.sub(r'\.\*', ' ', anchor)
        plain = re.sub(r'[\\.*+?^${}()|[\]]', '', plain)
        plain = plain.strip()
        if len(plain) < 8:
            continue

        window_size = len(plain) + 20
        best_score = 0
        best_pos = -1

        for i in range(0, max(1, len(norm_source) - window_size), 50):
            window = norm_source[i:i + window_size]
            score = fuzz.partial_ratio(plain, window)
            if score > best_score:
                best_score = score
                best_pos = i

        if best_score >= 75 and best_pos >= 0:
            refine_start = max(0, best_pos - 50)
            refine_end = min(len(norm_source), best_pos + window_size + 50)
            for i in range(refine_start, refine_end - window_size, 10):
                window = norm_source[i:i + window_size]
                score = fuzz.partial_ratio(plain, window)
                if score > best_score:
                    best_score = score
                    best_pos = i

            if best_score >= 80:
                orig_start = _map_normalized_pos_to_original(source_text, best_pos)
                sentence_start = _find_sentence_start(source_text, orig_start)
                sentence_end = _find_sentence_end(source_text, orig_start + 50)

                extracted = source_text[sentence_start:sentence_end].strip()
                extracted = re.sub(r'[ \t]+', ' ', extracted)
                extracted = re.sub(r'\n{3,}', '\n', extracted)
                extracted = re.sub(r'^\s*\n', '', extracted)
                extracted = re.sub(r'^[\d\s]{1,5}(?=\s*[A-Z])', '', extracted).strip()

                if len(extracted) > 600:
                    cut_pos = extracted.rfind('. ', 0, 600)
                    if cut_pos > len(extracted) // 3:
                        extracted = extracted[:cut_pos + 1]
                    else:
                        extracted = extracted[:600]

                if len(extracted) > 20:
                    return extracted

    return None


def _locate_in_source(value: str, source_text: str, norm_source: str) -> Optional[Tuple[int, int]]:
    """
    Best-effort lookup of a (possibly short/verbose) value's character span in
    source_text, without expanding to sentence boundaries. Used to attach a
    position to fields that were accepted as-is (short fields, keyword
    fallback results) so a snippet can still be built for them later.
    Returns (start, end) in original source_text coordinates, or None.
    """
    if not value or not value.strip():
        return None

    norm_value = _normalize_text(value)
    if not norm_value:
        return None

    idx = norm_source.find(norm_value)
    if idx >= 0:
        orig_start = _map_normalized_pos_to_original(source_text, idx)
        orig_end = _map_normalized_pos_to_original(source_text, idx + len(norm_value))
        return (orig_start, orig_end)

    match = _find_best_match(value, source_text)
    if match:
        norm_start, norm_end, score = match
        if score >= 0.5:
            orig_start = _map_normalized_pos_to_original(source_text, norm_start)
            orig_end = _map_normalized_pos_to_original(source_text, norm_end)
            return (orig_start, orig_end)

    return None


def verify_and_expand(
    agreement: AgreementType,
    field_data: dict,
    source_text: str,
    anchors: dict = None,
) -> Tuple[dict, dict, list, dict]:
    """
    Verify extracted fields against source text using agreement type config.
    Returns (verified_data, report, flagged_fields, positions).
    - positions: {field_name: (start, end)} character offsets into the
      ORIGINAL source_text passed in (not any internally-windowed slice -
      every windowed slice used below starts at index 0, so offsets found
      within it are already valid absolute positions) for fields where a
      source location was found. Used downstream to build small ±N-char
      snippets for the interpretation pass (Call 2) instead of re-sending
      the whole document. Fields with no resolvable location are simply
      absent from this dict.
    - Date_* and Amendment_Effective_Date fields are searched only within
      the first DATE_SEARCH_WINDOW_CHARS characters (see multi_file.py) -
      a document's own execution date always sits on its opening page(s),
      never buried past a table of contents or deep in an amendment's
      history recital, and searching the full document is both slower and
      more prone to matching an unrelated date mentioned in passing later
      in the text.
    """
    if anchors is None:
        anchors = {}

    verified_data = {}
    flagged_fields = []
    positions = {}
    report = {"exact": 0, "expanded": 0, "anchor_verified": 0,
              "short_field": 0, "not_found": 0, "none_value": 0}

    norm_source = _normalize_text(source_text)
    short_fields = agreement.short_fields
    field_anchors = agreement.field_anchors

    # A date field's real value always sits on a document's opening page(s)
    # - never buried past a table of contents or deep in an amendment's
    # history recital. Restricting the text searched for these fields to
    # the first DATE_SEARCH_WINDOW_CHARS characters (rather than the full
    # document) keeps matching fast and avoids a long recital of prior
    # amendment dates confusing which date is THIS document's own. Every
    # other field still searches the full document as before.
    full_source_text = source_text
    full_norm_source = norm_source

    for field_name, value in field_data.items():
        if field_name.startswith("Date_") or field_name == "Amendment_Effective_Date":
            source_text = full_source_text[:DATE_SEARCH_WINDOW_CHARS]
            norm_source = _normalize_text(source_text)
        else:
            source_text = full_source_text
            norm_source = full_norm_source

        if not value or not value.strip():
            verified_data[field_name] = value
            continue

        # "None." values
        if value.strip().lower() in ('none', 'none.', 'n/a', 'not applicable',
                                     'see original lease', 'see original lease.',
                                     'see original agreement', 'see original agreement.'):
            if value.strip().lower().startswith('see original'):
                verified_data[field_name] = value
                report["none_value"] += 1
                continue
            if field_name in field_anchors and field_name not in short_fields:
                fallback = _keyword_fallback_search(field_name, source_text, field_anchors)
                if fallback and len(fallback) > 20:
                    verified_data[field_name] = fallback
                    report["expanded"] += 1
                    pos = _locate_in_source(fallback, source_text, norm_source)
                    if pos:
                        positions[field_name] = pos
                    continue
            verified_data[field_name] = value
            report["none_value"] += 1
            continue

        # Short fields: accept without expansion
        if field_name in short_fields:
            verified_data[field_name] = value
            report["short_field"] += 1
            pos = _locate_in_source(value, source_text, norm_source)
            if pos:
                positions[field_name] = pos
            continue

        # Try AI anchor phrase first
        anchor_phrase = anchors.get(field_name, "")
        anchor_used = False
        if anchor_phrase and len(anchor_phrase) > 10:
            anchor_pos = _verify_ai_anchor(anchor_phrase, source_text)
            if anchor_pos >= 0:
                orig_start = _map_normalized_pos_to_original(source_text, anchor_pos)
                sentence_start = _find_sentence_start(source_text, orig_start)
                sentence_end = _find_sentence_end(source_text, orig_start + 50)

                extracted = source_text[sentence_start:sentence_end].strip()
                extracted = re.sub(r'[ \t]+', ' ', extracted)
                extracted = re.sub(r'\n{3,}', '\n', extracted)
                extracted = re.sub(r'^\s*\n', '', extracted)
                extracted = re.sub(r'^[\d\s]{1,5}(?=\s*[A-Z])', '', extracted).strip()

                if len(extracted) > 600:
                    cut_pos = extracted.rfind('. ', 0, 600)
                    if cut_pos > len(extracted) // 3:
                        extracted = extracted[:cut_pos + 1]
                    else:
                        extracted = extracted[:600]

                # Validate with field anchors if available
                if field_name in field_anchors and len(extracted) > 15:
                    norm_ext = _normalize_text(extracted)
                    anchor_relevant = False
                    for pattern in field_anchors[field_name]:
                        try:
                            if re.search(_bound_anchor_pattern(pattern), norm_ext):
                                anchor_relevant = True
                                break
                        except re.error:
                            continue
                    if not anchor_relevant:
                        flagged_fields.append(field_name)
                    else:
                        verified_data[field_name] = extracted
                        report["anchor_verified"] += 1
                        positions[field_name] = (sentence_start, sentence_end)
                        anchor_used = True
                elif len(extracted) > 15:
                    verified_data[field_name] = extracted
                    report["anchor_verified"] += 1
                    positions[field_name] = (sentence_start, sentence_end)
                    anchor_used = True

        if anchor_used:
            continue

        # Exact match (normalized)
        norm_value = _normalize_text(value)
        if norm_value in norm_source:
            verified_data[field_name] = value
            report["exact"] += 1
            idx = norm_source.find(norm_value)
            orig_start = _map_normalized_pos_to_original(source_text, idx)
            orig_end = _map_normalized_pos_to_original(source_text, idx + len(norm_value))
            positions[field_name] = (orig_start, orig_end)
            continue

        # Fuzzy find
        match = _find_best_match(value, source_text)
        if match:
            norm_start, norm_end, score = match
            orig_start = _map_normalized_pos_to_original(source_text, norm_start)
            orig_end = _map_normalized_pos_to_original(source_text, norm_end)
            sentence_start = _find_sentence_start(source_text, orig_start)
            sentence_end = _find_sentence_end(source_text, orig_end)

            extracted = source_text[sentence_start:sentence_end].strip()
            extracted = re.sub(r'[ \t]+', ' ', extracted)
            extracted = re.sub(r'\n{3,}', '\n', extracted)
            extracted = re.sub(r'^\s*\n', '', extracted)
            extracted = re.sub(r'^[\d\s]{1,5}(?=\s*[A-Z])', '', extracted).strip()

            if len(extracted) > 600:
                cut_pos = extracted.rfind('. ', 0, 600)
                if cut_pos > len(extracted) // 2:
                    extracted = extracted[:cut_pos + 1]
                else:
                    extracted = extracted[:600]

            if field_name in field_anchors and score < 1.0:
                fallback = _keyword_fallback_search(field_name, source_text, field_anchors)
                if fallback and len(fallback) > 20:
                    norm_extracted = _normalize_text(extracted)
                    norm_fallback = _normalize_text(fallback)
                    overlap = norm_fallback[:50] in norm_extracted or norm_extracted[:50] in norm_fallback
                    if not overlap:
                        extracted = fallback
                elif score < 0.5:
                    flagged_fields.append(field_name)

            verified_data[field_name] = extracted
            report["expanded"] += 1
            positions[field_name] = (sentence_start, sentence_end)
        else:
            fallback = _keyword_fallback_search(field_name, source_text, field_anchors)
            if fallback:
                verified_data[field_name] = fallback
                report["expanded"] += 1
                pos = _locate_in_source(fallback, source_text, norm_source)
                if pos:
                    positions[field_name] = pos
            else:
                verified_data[field_name] = value
                report["not_found"] += 1

    report["flagged"] = len(flagged_fields)
    return verified_data, report, flagged_fields, positions


def build_snippets(
    source_text: str,
    positions: dict,
    window: int = 500,
) -> Dict[str, str]:
    """
    Build a small ±`window`-char snippet of source_text around each field's
    verified position. Used by the interpretation pass (Call 2) so it reads
    a short excerpt instead of the entire document per field/batch.

    Fields absent from `positions` (no resolvable source location) are
    simply absent from the returned dict — the caller should fall back to
    just the verified raw text for those fields.
    """
    snippets = {}
    doc_len = len(source_text)
    for field_name, (start, end) in positions.items():
        snip_start = max(0, start - window)
        snip_end = min(doc_len, end + window)
        snippet = source_text[snip_start:snip_end].strip()
        # Collapse excessive whitespace so the snippet is compact.
        snippet = re.sub(r'[ \t]+', ' ', snippet)
        snippet = re.sub(r'\n{3,}', '\n\n', snippet)
        snippets[field_name] = snippet
    return snippets


def build_snippets_multi_source(
    field_sources: Dict[str, str],
    doc_texts: Dict[str, str],
    doc_positions: Dict[str, Dict[str, tuple]],
    window: int = 500,
) -> Dict[str, str]:
    """
    Multi-document version of build_snippets(), for the multi-file pipeline.
    Each field's CURRENT value may have come from a different source document
    (the original lease, or the latest amendment that overrode it) - this
    builds exactly one ±window-char snippet per field, taken from whichever
    document that field's current value actually came from.

    field_sources: {field_name: doc_key} - which document each field's
      current value came from (e.g. FieldHistory.current_source, or a
      filename used as the key in doc_texts/doc_positions).
    doc_texts: {doc_key: full_document_text}
    doc_positions: {doc_key: {field_name: (start, end)}} - the positions dict
      verify_and_expand() returned for that document.

    Fields with no resolvable position (missing doc_key, or field not in
    that document's positions) are simply absent from the result.
    """
    snippets = {}
    for field_name, doc_key in field_sources.items():
        text = doc_texts.get(doc_key)
        positions = doc_positions.get(doc_key)
        if not text or not positions or field_name not in positions:
            continue
        start, end = positions[field_name]
        snip_start = max(0, start - window)
        snip_end = min(len(text), end + window)
        snippet = text[snip_start:snip_end].strip()
        snippet = re.sub(r'[ \t]+', ' ', snippet)
        snippet = re.sub(r'\n{3,}', '\n\n', snippet)
        snippets[field_name] = snippet
    return snippets


# =============================================================================
# INTERPRETATION - AGREEMENT-TYPE DRIVEN (CALL 2)
# =============================================================================

_DEFAULT_INTERPRETATION_RULES = """Give a precise, useful reading of each field's raw text:
- Prefer a single precise value over a sentence: a dollar figure (e.g. "$13,825"), a bare
  number ("125 months", "5 business days"), or "Yes"/"Yes, with Landlord's consent"/"No"
  instead of the full clause, whenever the field is naturally a single fact.
- For a clause/provision with multiple distinct parts (insurance, OPEX, assignment, repair
  obligations, etc.), break it into a lettered list: (a) ..., (b) ..., (c) ...
- If the raw text is "None." or genuinely has nothing to interpret, return exactly "None"
  (capital N, no period).
- Do not include section references - those are tracked separately."""


def _build_interpretation_batch_prompt(
    agreement: AgreementType,
    batch: Dict[str, str],
    field_data: dict,
    snippets: Dict[str, str],
) -> str:
    """
    Build the Call 2 prompt for a single batch of fields. Each field gets its
    verified raw text plus a small ±N-char snippet of surrounding source text
    (NOT the full document) - keeps this call's input and output both small.
    """
    interpretation_rules = agreement.interpretation_rules or _DEFAULT_INTERPRETATION_RULES

    parts = []
    for field_name, description in batch.items():
        raw_value = field_data.get(field_name, "")
        snippet = snippets.get(field_name, "")
        block = [f'FIELD: "{field_name}"', f"DESCRIPTION: {description}", f"RAW TEXT: {raw_value or 'None.'}"]
        if snippet and snippet.strip() != (raw_value or "").strip():
            block.append(f"SURROUNDING CONTEXT (source excerpt): {snippet}")
        parts.append("\n".join(block))

    fields_block = "\n\n".join(parts)

    return f"""You are a legal document analyst. For EACH field below, you are given the field's
verbatim raw text (already extracted and verified against the source document) and a short
excerpt of surrounding context. Produce a precise interpretation of each field's raw text.

INTERPRETATION RULES:
{interpretation_rules}

FIELDS:
{fields_block}

Respond with ONLY a valid JSON object mapping each field name to its interpretation string, e.g.:
{{"{next(iter(batch), 'FieldName')}": "..."}}

No markdown, no explanation, no extra keys."""


def _interpret_batch(
    client,
    agreement: AgreementType,
    batch: Dict[str, str],
    field_data: dict,
    snippets: Dict[str, str],
) -> Dict[str, str]:
    """Run Call 2 for a single batch of fields. Returns {field_name: interpretation}."""
    prompt = _build_interpretation_batch_prompt(agreement, batch, field_data, snippets)

    response = _call_openai_with_retry(
        client,
        messages=[
            {"role": "system", "content": (
                "You are a precise legal-document interpreter. You read verbatim contract "
                "language and restate it as short, exact, reusable values or lettered "
                "summaries. You never invent facts not present in the text."
            )},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = _attempt_json_recovery(raw)

    # Normalize to flat {field: interpretation_string}
    result = {}
    for key, val in parsed.items():
        if key not in batch:
            continue
        if isinstance(val, dict):
            result[key] = val.get("interpretation", "") or val.get("text", "")
        else:
            result[key] = val or ""
    return result


def interpret_fields(
    agreement: AgreementType,
    field_data: dict,
    snippets: Dict[str, str],
    batch_size: int = 30,
    max_workers: int = 4,
    on_progress=None,
) -> Dict[str, str]:
    """
    CALL 2 - Interpretation pass.
    Splits fields into batches (default 30/batch) and runs them concurrently,
    each batch getting only its fields' verified raw text + a small source
    snippet (not the full document). Merges results by field name.

    on_progress: optional callback(done_count, total_batches) invoked after
    each batch completes (success or failure) - lets the caller surface live
    progress (e.g. "batch 2/4 done") in a job status file for UI polling.

    Returns {field_name: interpretation}. Fields the AI omits or that fail to
    parse are simply absent from the result (caller falls back to raw text).
    """
    try:
        client = get_openai_client()
    except RuntimeError as e:
        raise _make_ai_error(
            "OpenAI API key not found. Place your key in "
            "C:\\seedJura\\openai_api_key.txt or set the OPENAI_API_KEY "
            "environment variable.",
            str(e),
        )

    # Only interpret fields that actually have raw text worth interpreting.
    fields_to_interpret = {
        name: desc for name, desc in agreement.fields.items()
        if field_data.get(name, "").strip()
        and field_data.get(name, "").strip().lower() not in ("none", "none.")
    }

    if not fields_to_interpret:
        return {}

    names = list(fields_to_interpret.keys())
    batches = [
        {n: fields_to_interpret[n] for n in names[i:i + batch_size]}
        for i in range(0, len(names), batch_size)
    ]

    print(f"  Sending to AI for interpretation (Call 2): {len(fields_to_interpret)} fields "
          f"in {len(batches)} batch(es), up to {max_workers} in parallel...")

    interpretations: Dict[str, str] = {}
    errors = []
    timeout_failures = 0
    # If this many (or more) batches time out, the OpenAI service is almost
    # certainly slow/unresponsive right now - stop feeding it more work and
    # fail the job cleanly instead of grinding through every remaining batch's
    # own 3x retry-with-backoff cycle (each up to ~6 min) one by one.
    timeout_circuit_breaker = max(2, len(batches) // 2)
    tripped = False

    completed_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {
            executor.submit(_interpret_batch, client, agreement, batch, field_data, snippets): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(future_to_batch):
            batch_idx = future_to_batch[future]
            try:
                batch_result = future.result()
                interpretations.update(batch_result)
                print(f"    Batch {batch_idx + 1}/{len(batches)}: {len(batch_result)} interpretation(s)")
            except Exception as e:
                errors.append((batch_idx, str(e)))
                print(f"    Batch {batch_idx + 1}/{len(batches)} FAILED: {e}")
                if getattr(e, "kind", "") == "timeout":
                    timeout_failures += 1
                if timeout_failures >= timeout_circuit_breaker and not tripped:
                    tripped = True
                    print(f"    Circuit breaker: {timeout_failures} batch(es) timed out - "
                          f"aborting remaining batches instead of continuing to retry.")
                    # Best-effort cancel of anything not yet started; running
                    # threads can't be interrupted, but we stop waiting on them.
                    for f in future_to_batch:
                        f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    completed_count += 1
                    if on_progress:
                        try:
                            on_progress(completed_count, len(batches))
                        except Exception:
                            pass
                    break

            completed_count += 1
            if on_progress:
                try:
                    on_progress(completed_count, len(batches))
                except Exception:
                    pass  # progress reporting must never break the pipeline

    if tripped:
        raise _make_ai_error(
            f"Interpretation pass aborted: {timeout_failures}/{len(batches)} batch(es) timed out. "
            "The OpenAI service appears to be slow or unresponsive right now. "
            "Try again later, or check status.openai.com.",
            "; ".join(f"batch {i}: {msg}" for i, msg in errors),
            kind="circuit_breaker",
        )

    if errors and not interpretations:
        # Every batch failed - surface as a real error rather than silently
        # falling back to empty interpretations everywhere.
        raise _make_ai_error(
            f"Interpretation pass failed for all {len(batches)} batch(es).",
            "; ".join(f"batch {i}: {msg}" for i, msg in errors),
        )

    print(f"  AI provided {len(interpretations)}/{len(fields_to_interpret)} interpretation(s)")
    return interpretations


# =============================================================================
# COMPLETENESS CHECK (CODE, NO AI)
# =============================================================================

def check_completeness(
    agreement: AgreementType,
    field_data: dict,
    interpretations: Dict[str, str],
    flagged_fields: list,
) -> dict:
    """
    Pure-code completeness pass over the merged extraction+interpretation
    result. No AI call - just structural checks so the pipeline knows what
    (if anything) still needs a targeted retry before generating output.

    Returns a report dict:
      {
        "missing_expected": [field, ...],   # expected_fields still empty/None
        "flagged_from_verify": [field, ...],# carried over from verify_and_expand
        "missing_interpretation": [field, ...],  # has raw text but no interpretation
        "suspect": [{"field": ..., "reason": ...}, ...],  # basic sanity-check misses
        "total_fields": int,
        "filled_fields": int,
        "interpreted_fields": int,
        "needs_retry": [field, ...],  # union of missing_expected + flagged_from_verify
      }
    """
    none_values = ('none', 'none.', 'n/a', '', 'not applicable', 'not found', 'not found.')

    missing_expected = [
        f for f in agreement.expected_fields
        if field_data.get(f, "").strip().lower() in none_values
    ]

    missing_interpretation = [
        f for f, v in field_data.items()
        if v and v.strip().lower() not in none_values and f not in interpretations
    ]

    suspect = []
    date_like = {f for f in agreement.fields if "date" in f.lower()}
    amount_like = {f for f in agreement.fields if "amt" in f.lower() or "rent" in f.lower()}

    for f in date_like:
        interp = interpretations.get(f, "")
        raw = field_data.get(f, "")
        if raw and raw.strip().lower() not in none_values and interp:
            if not re.search(r'\d', interp):
                suspect.append({"field": f, "reason": "date field interpretation has no digits"})

    for f in amount_like:
        interp = interpretations.get(f, "")
        raw = field_data.get(f, "")
        if raw and raw.strip().lower() not in none_values and interp:
            if not re.search(r'\d', interp):
                suspect.append({"field": f, "reason": "dollar/amount field interpretation has no digits"})

    filled_fields = sum(
        1 for v in field_data.values() if v and v.strip().lower() not in none_values
    )

    needs_retry = sorted(set(missing_expected) | set(flagged_fields or []))

    report = {
        "missing_expected": missing_expected,
        "flagged_from_verify": list(flagged_fields or []),
        "missing_interpretation": missing_interpretation,
        "suspect": suspect,
        "total_fields": len(agreement.fields),
        "filled_fields": filled_fields,
        "interpreted_fields": len(interpretations),
        "needs_retry": needs_retry,
    }

    print(f"  Completeness check: {filled_fields}/{len(agreement.fields)} filled, "
          f"{len(interpretations)} interpreted, {len(missing_expected)} missing expected, "
          f"{len(flagged_fields or [])} flagged, {len(suspect)} suspect")

    return report


# =============================================================================
# AI QA / FEEDBACK PASS (CALL 4) - SUGGESTIONS ONLY, NOT APPLIED TO THIS JOB
# =============================================================================

def suggest_improvements(
    agreement: AgreementType,
    source_text: str,
    field_data: dict,
    interpretations: Dict[str, str],
    sections: Dict[str, str],
    max_field_chars: int = 400,
) -> dict:
    """
    CALL 4 - Full-document QA pass.
    Reads the full source document plus the complete extraction/interpretation
    table and asks the model whether it's happy with the result. Output is a
    JSON list of suggested improvements (e.g. ambiguous field descriptions,
    a value that looks inconsistent with another field, a field that seems
    to have been missed) - NOT corrected values. This is a feedback artifact
    for improving the agreement type's config/prompts over time; it is saved
    alongside the job but never used to alter the current job's output.
    """
    try:
        client = get_openai_client()
    except RuntimeError as e:
        raise _make_ai_error(
            "OpenAI API key not found. Place your key in "
            "C:\\seedJura\\openai_api_key.txt or set the OPENAI_API_KEY "
            "environment variable.",
            str(e),
        )

    # Build a compact result table: field, section, interpretation (or raw
    # text if no interpretation), truncated so the table itself stays small -
    # the model has the full source text separately for cross-checking.
    none_values = ('none', 'none.', 'n/a', '', 'not applicable', 'not found', 'not found.')
    rows = []
    for field_name, description in agreement.fields.items():
        raw = field_data.get(field_name, "")
        if raw.strip().lower() in none_values:
            continue
        value = interpretations.get(field_name, "") or raw
        if len(value) > max_field_chars:
            value = value[:max_field_chars] + "…"
        section = sections.get(field_name, "")
        rows.append(f'  "{field_name}" ({description}) [{section}]: {value}')

    table = "\n".join(rows)

    prompt = f"""You are QA-reviewing an automated legal-document field extraction. You are given
the FULL source document and the extraction result table (field: description [section]: value).

Review the result for:
- Fields that look wrong given the full document context (e.g. contradicts another field,
  or the value doesn't match what the document actually says elsewhere)
- Fields that appear to have been missed or under-extracted despite being present in the document
- Field descriptions in the schema that seem ambiguous or led to a questionable extraction
- Anything else worth flagging for someone improving this extraction schema/prompts later

Do NOT provide corrected values - only describe the issue and suggest what should change about
the extraction rules, field description, or approach. Keep each suggestion to 1-2 sentences.

EXTRACTION RESULT TABLE:
{table}

FULL SOURCE DOCUMENT:
{source_text[:100000]}

Respond with ONLY a JSON object of this shape:
{{
  "overall_assessment": "one or two sentences on how the extraction is doing overall",
  "suggestions": [
    {{"field": "FieldName or 'general'", "issue": "what looks wrong", "suggestion": "what to change"}}
  ]
}}
If you have no suggestions, return an empty "suggestions" list. No markdown, no explanation."""

    print("  Sending to AI for QA/feedback pass (Call 4)...")

    response = _call_openai_with_retry(
        client,
        messages=[
            {"role": "system", "content": (
                "You are a meticulous QA reviewer for automated legal-document data "
                "extraction. You give concise, actionable feedback for improving the "
                "extraction schema and prompts - you do not rewrite the data yourself."
            )},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = _attempt_json_recovery(raw)
        if not parsed or "suggestions" not in parsed:
            parsed = {"overall_assessment": "", "suggestions": [], "parse_error": True, "raw_response": raw[:2000]}

    suggestions = parsed.get("suggestions", [])
    print(f"  QA pass: {len(suggestions)} suggestion(s)")
    return parsed


# =============================================================================
# AI RETRY - AGREEMENT-TYPE DRIVEN
# =============================================================================

def ai_retry_fields(
    agreement: AgreementType,
    field_data: dict,
    source_text: str,
    flagged_fields: list = None,
) -> Tuple[dict, int]:
    """
    Targeted AI retry for expected fields that came back empty and flagged fields.
    Uses agreement type's expected_fields and retry_hints.
    """
    if flagged_fields is None:
        flagged_fields = []

    retry_fields = {}

    # Expected fields that are None/empty
    for field_name in agreement.expected_fields:
        val = field_data.get(field_name, "")
        if val.strip().lower() in ('none', 'none.', 'n/a', '', 'not applicable'):
            retry_fields[field_name] = agreement.fields.get(field_name, field_name)

    # Explicitly flagged fields
    for field_name in flagged_fields:
        if field_name not in retry_fields:
            retry_fields[field_name] = agreement.fields.get(field_name, field_name)

    if not retry_fields:
        return field_data, 0

    print(f"  Targeted AI retry for {len(retry_fields)} field(s)...")
    for f in retry_fields:
        print(f"    - {f}")

    # Build prompt with hints
    fields_with_hints = []
    for k, desc in retry_fields.items():
        hint = agreement.retry_hints.get(k, "")
        hint_str = f" HINT: {hint}" if hint else ""
        fields_with_hints.append(f'  "{k}": "{desc}"{hint_str}')

    fields_desc = "\n".join(fields_with_hints)

    prompt = f"""You are re-reading a legal document to find specific provisions that were missed in a first pass.
The document may contain OCR errors (misspellings, garbled characters, missing spaces).

RULES:
- Copy/paste the EXACT text from the document, even if it has OCR typos
- Start from the beginning of the relevant sentence or clause
- Include up to 250 words of the relevant provision
- Return "Not found." ONLY if you genuinely cannot locate the provision after careful search
- Do NOT make up or paraphrase text

FIELDS TO FIND (with hints on where to look):
{fields_desc}

DOCUMENT TEXT:
{source_text[:80000]}

Return a JSON object mapping field names to extracted text. No markdown."""

    try:
        client = get_openai_client()
        response = _call_openai_with_retry(
            client,
            messages=[
                {"role": "system", "content": "You are an expert at reading OCR'd legal documents. You can identify clauses even when text contains spelling errors or formatting issues. You copy text exactly as it appears, never paraphrasing."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8000,
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        retried = json.loads(raw)
    except (ProcessingError,):
        # Auth/quota/timeout errors from _call_openai_with_retry are real
        # failures the caller should know about, not silently swallowed.
        raise
    except (json.JSONDecodeError, Exception) as e:
        print(f"    Retry failed: {e}")
        return field_data, 0

    # Apply recovered fields - verify each exists in source
    recovered = 0
    norm_source = _normalize_text(source_text)

    for field_name, value in retried.items():
        if not value or value.strip().lower() in ('not found', 'not found.', 'none', 'none.', ''):
            continue

        norm_val = _normalize_text(value)
        found_in_source = False
        if len(norm_val) > 15 and norm_val[:40] in norm_source:
            found_in_source = True
        elif _find_best_match(value, source_text):
            found_in_source = True

        if found_in_source:
            field_data[field_name] = value
            recovered += 1
            print(f"    Recovered: {field_name} ({len(value.split())}w)")
        else:
            print(f"    Rejected (not in source): {field_name}")

    return field_data, recovered


# =============================================================================
# TEMPLATE POPULATION
# =============================================================================

def populate_template(agreement: AgreementType, field_data: dict, output_path: str) -> str:
    """Populate the agreement type's template with extracted fields."""
    from docx import Document
    from lease_summary_tool import TEMPLATE_PATH as DEFAULT_TEMPLATE

    template_path = agreement.template_path

    # If it's just a filename (not absolute), search known locations
    if template_path and not os.path.isabs(template_path):
        search_dirs = [
            agreement.base_path,
            os.path.dirname(os.path.abspath(__file__)),
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            r"C:\seedJura",
            "/mnt/c/seedJura",
        ]
        for d in search_dirs:
            candidate = os.path.join(d, template_path)
            if os.path.exists(candidate):
                template_path = candidate
                break

    # Fall back to the main TEMPLATE_PATH from lease_summary_tool
    if not template_path or not os.path.exists(template_path):
        template_path = DEFAULT_TEMPLATE

    if not os.path.exists(template_path):
        raise FileNotFoundError(
            f"Template not found: {agreement.template_path}\n"
            f"Searched paths include: {template_path}\n"
            f"Please place the template in C:\\seedJura\\ or next to the executable."
        )

    return _populate_template_raw(field_data, output_path)


# =============================================================================
# FULL PIPELINE
# =============================================================================

def process_document(
    input_file: str,
    agreement_type_id: str = None,
    output_dir: str = None,
    preparer: str = "",
    purpose: str = "",
) -> dict:
    """
    Full pipeline: ingest → detect type → PII scan → AI extract → verify → retry → save.

    If agreement_type_id is None, attempts auto-detection.
    Returns a result dict with all metadata.
    """
    from lease_summary_tool import DEFAULT_OUTPUT_DIR

    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    result = {
        "input_file": input_file,
        "status": "processing",
        "phases": {},
    }

    # Phase 1: Ingest
    print("[Phase 1] Ingesting document...")
    raw_text = ingest_document(input_file)
    print(f"  Extracted {len(raw_text):,} characters")
    result["phases"]["ingest"] = f"done ({len(raw_text):,} chars)"

    # Resolve agreement type
    if agreement_type_id:
        agreement = get_type(agreement_type_id)
        if not agreement:
            raise ValueError(f"Unknown agreement type: {agreement_type_id}")
    else:
        # Auto-detect
        detected = detect_agreement_type(raw_text, os.path.basename(input_file))
        if detected:
            agreement = get_type(detected)
            print(f"  Auto-detected agreement type: {agreement.name}")
        else:
            # Default to lease for backward compatibility
            agreement = get_type("lease")
            if not agreement:
                raise ValueError("No agreement type detected and 'lease' type not available.")
            print("  Defaulting to: Commercial Lease")

    result["agreement_type"] = agreement.type_id
    result["agreement_name"] = agreement.name

    # Detect sub-type (e.g., amendment)
    sub_type = agreement.detect_sub_type(raw_text, os.path.basename(input_file))
    if sub_type != agreement.type_id:
        print(f"  Document sub-type: {sub_type.upper()}")
    result["sub_type"] = sub_type

    # Phase 2: PII scan
    print("\n[Phase 2] Scanning for PII...")
    text_for_ai, pii_findings = redact_and_capture_pii(raw_text)
    result["phases"]["pii"] = f"done ({len(pii_findings)} items)"
    result["pii_count"] = len(pii_findings)

    # Phase 3: AI raw extraction (Call 1)
    print("\n[Phase 3] AI raw extraction (Call 1)...")
    field_data, ai_anchors, normalized_dates, field_sections = analyze_with_ai(
        agreement, text_for_ai, sub_type=sub_type
    )

    # Apply user overrides (generic metadata fields)
    if preparer:
        # Find a "preparer" field by convention
        for key in agreement.fields:
            if "preparer" in key.lower():
                field_data[key] = preparer
                break
    if purpose:
        for key in agreement.fields:
            if "purpose" in key.lower():
                field_data[key] = purpose
                break
    # Set date if there's a summary date field
    for key in agreement.fields:
        if "summary_date" in key.lower() and not field_data.get(key):
            field_data[key] = datetime.now().strftime("%B %d, %Y")
            break

    result["phases"]["ai"] = f"done ({sum(1 for v in field_data.values() if v)}/{len(agreement.fields)} fields)"

    # Phase 3B: Source verification (also resolves per-field source positions)
    print("\n[Phase 3B] Verifying against source text...")
    field_data, verify_report, flagged, positions = verify_and_expand(agreement, field_data, raw_text, ai_anchors)
    print(f"  Anchor-verified: {verify_report.get('anchor_verified', 0)}")
    print(f"  Exact matches: {verify_report['exact']}")
    print(f"  Expanded from source: {verify_report['expanded']}")
    print(f"  Short/lookup fields: {verify_report['short_field']}")
    print(f"  Not found in source: {verify_report['not_found']}")
    if flagged:
        print(f"  Flagged for retry: {len(flagged)}")

    result["phases"]["verify"] = verify_report

    # Phase 3C: AI interpretation (Call 2) - batched + parallel, small snippets
    print("\n[Phase 3C] AI interpretation (Call 2)...")
    snippets = build_snippets(raw_text, positions, window=500)
    interpretations = interpret_fields(agreement, field_data, snippets)
    result["phases"]["interpret"] = f"done ({len(interpretations)} fields)"

    # Phase 3D: Completeness check (code, no AI) + targeted retry for gaps
    completeness = check_completeness(agreement, field_data, interpretations, flagged)
    result["completeness"] = completeness

    retry_count = 0
    if completeness["needs_retry"]:
        print("\n[Phase 3D] AI retry for incomplete/flagged fields...")
        field_data, retry_count = ai_retry_fields(agreement, field_data, raw_text, completeness["needs_retry"])
        if retry_count > 0:
            print(f"  Recovered {retry_count} field(s)")
            retried_fields = {f: v for f, v in field_data.items() if f in completeness["needs_retry"] and v}
            if retried_fields:
                retry_positions = {f: p for f, p in positions.items() if f in retried_fields}
                retry_snippets = build_snippets(raw_text, retry_positions, window=500)
                interpretations.update(interpret_fields(agreement, retried_fields, retry_snippets))

    result["phases"]["retry"] = f"done (recovered {retry_count})"
    result["fields_extracted"] = sum(1 for v in field_data.values() if v)
    result["fields_total"] = len(agreement.fields)

    # Phase 3E: AI QA/feedback pass (Call 4) - suggestions only, saved as an
    # artifact, never applied to this job's output.
    print("\n[Phase 3E] AI QA/feedback pass (Call 4)...")
    try:
        qa_feedback = suggest_improvements(agreement, raw_text, field_data, interpretations, field_sections)
        result["qa_feedback"] = qa_feedback
        print(f"  {len(qa_feedback.get('suggestions', []))} suggestion(s)")
    except Exception as e:
        print(f"  QA pass failed (non-fatal): {e}")
        result["qa_feedback"] = {"error": str(e)}

    # Build the 3-variant field set (FieldName / FieldName_Int / FieldName_Raw)
    from field_variants import build_field_variants, doc_type_label
    doc_label = doc_type_label(sub_type, fallback=sub_type)
    full_field_data = build_field_variants(
        agreement.fields.keys(), field_data,
        interpretations=interpretations, sections=field_sections,
        doc_label=doc_label,
    )
    result["field_data"] = full_field_data
    result["interpretations"] = interpretations
    result["sections"] = field_sections

    # Phase 4: Generate output
    print("\n[Phase 4] Populating template and saving...")
    output_filename = _generate_output_filename(input_file, output_dir)
    saved_path = populate_template(agreement, full_field_data, output_filename)
    print(f"  Saved: {saved_path}")

    result["output_path"] = saved_path
    result["output_filename"] = os.path.basename(saved_path)
    result["status"] = "complete"

    # JSON sidecar
    json_path = output_filename.replace(".docx", "_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"  Data: {json_path}")

    # XML sidecar (GlobalFormVars format)
    try:
        from xml_export import field_data_to_xml_pretty
        xml_path = output_filename.replace(".docx", "_GlobalFormVars.xml")
        xml_content = field_data_to_xml_pretty(full_field_data, normalized_dates)
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        result["xml_path"] = xml_path
        print(f"  XML:  {xml_path}")
    except ImportError:
        pass

    return result


def _generate_output_filename(input_file: str, output_dir: str) -> str:
    """Generate output filename."""
    base_name = Path(input_file).stem
    clean_name = re.sub(
        r"(?i)[\s_-]*(fully[\s_-]*executed|execution|final|signed|copy)",
        "", base_name,
    )
    clean_name = re.sub(r"[\s_-]+$", "", clean_name)
    clean_name = re.sub(r"\s+", "_", clean_name)
    date_str = datetime.now().strftime("%m-%d-%y")
    filename = f"{clean_name}_summary_{date_str}.docx"
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, filename)


# =============================================================================
# DEFAULTS
# =============================================================================

_DEFAULT_SYSTEM_PROMPT = (
    "You are a legal document data extractor. "
    "You ONLY copy and paste exact text from documents. "
    "You NEVER summarize, paraphrase, or use your own words. "
    "Every value you return must appear verbatim in the source document."
)

_DEFAULT_EXTRACTION_RULES = """CRITICAL RULES:
- You MUST copy/paste exact language from the document. Do NOT summarize, paraphrase, or reword.
- Every value you return must be text that appears verbatim in the document.
- If a provision is not found or not applicable, return "None." (with period).
- For dates, copy the exact phrasing.
- For dollar amounts, copy exactly as written including $ sign.
- For percentages, copy exactly as written.
- Include section/article references when they appear near the relevant text.
- Start each extraction at the BEGINNING of the relevant sentence or clause.
- For long provisions: copy the FULL relevant clause. Include up to 300 words."""
