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


# =============================================================================
# AI EXTRACTION - AGREEMENT-TYPE DRIVEN
# =============================================================================

def build_extraction_prompt(agreement: AgreementType, text: str, sub_type: str = "") -> str:
    """Build AI extraction prompt from agreement type config."""
    fields_list = "\n".join(
        f'  "{k}": "{v}"' for k, v in agreement.fields.items()
    )

    # Sub-type instruction (e.g., amendment-specific rules)
    sub_type_instruction = ""
    if sub_type and sub_type != agreement.type_id:
        sub_type_instruction = agreement.get_sub_type_instruction(sub_type)
        if sub_type_instruction:
            sub_type_instruction = f"\n{sub_type_instruction}\n"

    # Use agreement-specific extraction rules, or fall back to generic
    extraction_rules = agreement.extraction_rules or _DEFAULT_EXTRACTION_RULES

    prompt = f"""You are a legal document analyst. Analyze the following document and extract the requested information into a JSON object.
{sub_type_instruction}
{extraction_rules}

HANDWRITTEN DATE HANDLING:
- This document may contain OCR artifacts from handwritten dates on fill-in-the-blank templates.
- If you see "[handwritten: X]" markers, the original handwritten text was garbled by OCR. Use context clues (execution dates, commencement dates, surrounding text) to infer the correct value.
- Common OCR misreads: "Bias" = "1st", "Znd" = "2nd", garbled text before "day of <Month>" = a handwritten day number.
- If a date field contains garbled/nonsensical text (e.g., "Bias day of March"), report your best interpretation with the corrected value.

DATE FIELD FORMAT:
For ANY field that contains a date (Date_Lease, Date_Commencment, Date_Expiration, Date_EarlyAccess, Rent_Abatement_Commencement, Rent_Abatement_Expiration, or any other date-related field), return an object with THREE keys:
- "text": The full verbatim language from the document (include conditional language, context)
- "date": Your best-guess normalized date in mm/dd/yyyy format. If the date is conditional or cannot be determined to a specific date, use your best estimate of the most likely date based on context.
- "anchor": The first 8 words of the source sentence (same as other fields)

Example for a simple date:
  "Date_Lease": {{"text": "1st day of March, 2021", "date": "03/01/2021", "anchor": ""}}

Example for a conditional/complex date:
  "Date_Commencment": {{"text": "The earlier to occur of A) November 1, 2022, or B) the date Tenant opens for business", "date": "11/01/2022", "anchor": "The earlier to occur of A November"}}

Example for expiration:
  "Date_Expiration": {{"text": "shall expire on March 31, 2028, unless renewed, terminated or extended", "date": "03/31/2028", "anchor": "shall expire on March 31 2028 unless"}}

If a date truly cannot be determined, use "date": "TBD".

RESPONSE FORMAT (for non-date fields):
Return a JSON object where each field maps to an object with two keys:
- "text": The extracted verbatim text from the document
- "anchor": The first 8 words of the sentence where you found this text (used to verify location)

For short values (names, amounts, Yes/No), the "anchor" can be empty string "".
For longer clause extractions, "anchor" MUST contain the first 8 words of the source sentence.

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


def analyze_with_ai(agreement: AgreementType, text: str, sub_type: str = "") -> Tuple[dict, dict, dict]:
    """
    Send document text to AI for field extraction using agreement type config.
    Returns (field_data, anchors, dates).
    - field_data: {field_name: extracted_text}
    - anchors: {field_name: anchor_phrase}
    - dates: {field_name: "mm/dd/yyyy"} for date fields
    """
    print("  Sending to AI for analysis...")
    client = get_openai_client()

    prompt = build_extraction_prompt(agreement, text, sub_type=sub_type)
    system_prompt = agreement.system_prompt or _DEFAULT_SYSTEM_PROMPT

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=16000,
        response_format={"type": "json_object"},
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
            return {}, {}

    # Parse format: {"field": {"text": "...", "anchor": "...", "date": "..."}} or flat
    field_data = {}
    anchors = {}
    dates = {}  # Normalized dates in mm/dd/yyyy for date fields

    for key, val in parsed.items():
        if isinstance(val, dict):
            field_data[key] = val.get("text", "")
            anchors[key] = val.get("anchor", "")
            if "date" in val and val["date"]:
                dates[key] = val["date"]
        else:
            field_data[key] = val if val else ""
            anchors[key] = ""

    filled = sum(1 for v in field_data.values() if v)
    print(f"  AI extracted {filled}/{len(agreement.fields)} fields")
    anchored = sum(1 for v in anchors.values() if v)
    print(f"  AI provided {anchored} anchor phrases")
    if dates:
        print(f"  AI normalized {len(dates)} date(s)")
    return field_data, anchors, dates


# =============================================================================
# SOURCE VERIFICATION - AGREEMENT-TYPE DRIVEN
# =============================================================================

def _keyword_fallback_search(field_name: str, source_text: str, field_anchors: dict) -> Optional[str]:
    """
    Keyword anchor fallback search using agreement type's field_anchors.
    """
    anchors = field_anchors.get(field_name)
    if not anchors:
        return None

    norm_source = _normalize_text(source_text)

    # First pass: exact regex matching
    for anchor in anchors:
        try:
            match = re.search(anchor, norm_source)
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


def verify_and_expand(
    agreement: AgreementType,
    field_data: dict,
    source_text: str,
    anchors: dict = None,
) -> Tuple[dict, dict, list]:
    """
    Verify extracted fields against source text using agreement type config.
    Returns (verified_data, report, flagged_fields).
    """
    if anchors is None:
        anchors = {}

    verified_data = {}
    flagged_fields = []
    report = {"exact": 0, "expanded": 0, "anchor_verified": 0,
              "short_field": 0, "not_found": 0, "none_value": 0}

    norm_source = _normalize_text(source_text)
    short_fields = agreement.short_fields
    field_anchors = agreement.field_anchors

    for field_name, value in field_data.items():
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
                    continue
            verified_data[field_name] = value
            report["none_value"] += 1
            continue

        # Short fields: accept without expansion
        if field_name in short_fields:
            verified_data[field_name] = value
            report["short_field"] += 1
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
                            if re.search(pattern, norm_ext):
                                anchor_relevant = True
                                break
                        except re.error:
                            continue
                    if not anchor_relevant:
                        flagged_fields.append(field_name)
                    else:
                        verified_data[field_name] = extracted
                        report["anchor_verified"] += 1
                        anchor_used = True
                elif len(extracted) > 15:
                    verified_data[field_name] = extracted
                    report["anchor_verified"] += 1
                    anchor_used = True

        if anchor_used:
            continue

        # Exact match (normalized)
        norm_value = _normalize_text(value)
        if norm_value in norm_source:
            verified_data[field_name] = value
            report["exact"] += 1
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
        else:
            fallback = _keyword_fallback_search(field_name, source_text, field_anchors)
            if fallback:
                verified_data[field_name] = fallback
                report["expanded"] += 1
            else:
                verified_data[field_name] = value
                report["not_found"] += 1

    report["flagged"] = len(flagged_fields)
    return verified_data, report, flagged_fields


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
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert at reading OCR'd legal documents. You can identify clauses even when text contains spelling errors or formatting issues. You copy text exactly as it appears, never paraphrasing."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=8000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        retried = json.loads(raw)
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

    # Phase 3: AI extraction
    print("\n[Phase 3] AI analysis and field extraction...")
    field_data, ai_anchors, normalized_dates = analyze_with_ai(agreement, text_for_ai, sub_type=sub_type)

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

    # Phase 3B: Source verification
    print("\n[Phase 3B] Verifying against source text...")
    field_data, verify_report, flagged = verify_and_expand(agreement, field_data, raw_text, ai_anchors)
    print(f"  Anchor-verified: {verify_report.get('anchor_verified', 0)}")
    print(f"  Exact matches: {verify_report['exact']}")
    print(f"  Expanded from source: {verify_report['expanded']}")
    print(f"  Short/lookup fields: {verify_report['short_field']}")
    print(f"  Not found in source: {verify_report['not_found']}")
    if flagged:
        print(f"  Flagged for retry: {len(flagged)}")

    result["phases"]["verify"] = verify_report

    # Phase 3C: AI retry
    retry_count = 0
    if flagged or any(
        field_data.get(f, "").strip().lower() in ('none', 'none.', '')
        for f in agreement.expected_fields
    ):
        print("\n[Phase 3C] AI retry for flagged fields...")
        field_data, retry_count = ai_retry_fields(agreement, field_data, raw_text, flagged)
        if retry_count > 0:
            print(f"  Recovered {retry_count} field(s)")

    result["phases"]["retry"] = f"done (recovered {retry_count})"
    result["field_data"] = field_data
    result["fields_extracted"] = sum(1 for v in field_data.values() if v)
    result["fields_total"] = len(agreement.fields)

    # Phase 4: Generate output
    print("\n[Phase 4] Populating template and saving...")
    output_filename = _generate_output_filename(input_file, output_dir)
    saved_path = populate_template(agreement, field_data, output_filename)
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
        xml_content = field_data_to_xml_pretty(field_data)
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
