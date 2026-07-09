"""
PII redaction system — hex mapping approach.
Redacts personally identifiable information before AI sees document text.
Reconstructs PII in output documents after changes are applied.

Ported from ai_attorney_standalone/app.py with same 3-pass structure.
"""

import os
import re
from typing import Optional

from text_utils import fix_ligatures
import config


# Module-level caches
_WHITELIST: Optional[set] = None
_BLACKLIST_PATTERNS: Optional[list] = None


def get_whitelist() -> set:
    """Load the redaction whitelist — words that should NOT be treated as PII."""
    global _WHITELIST
    if _WHITELIST is not None:
        return _WHITELIST

    whitelist = set()
    if os.path.exists(config.WHITELIST_PATH):
        with open(config.WHITELIST_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip().lower()
                if word and not word.startswith('#'):
                    whitelist.add(word)

    _WHITELIST = whitelist
    return whitelist


def get_blacklist_patterns() -> list:
    """Load blacklist entries (known company names) and build regex patterns."""
    global _BLACKLIST_PATTERNS
    if _BLACKLIST_PATTERNS is not None:
        return _BLACKLIST_PATTERNS

    entries = []
    if os.path.exists(config.BLACKLIST_DIR):
        for filename in sorted(os.listdir(config.BLACKLIST_DIR)):
            if not filename.endswith('.txt'):
                continue
            filepath = os.path.join(config.BLACKLIST_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and len(line) >= 5:
                        entries.append(line)

    # Sort longest first for greedy matching
    entries = sorted(set(entries), key=len, reverse=True)
    patterns = []
    for entry in entries:
        escaped = re.escape(entry)
        escaped = re.sub(r'\\ ', r'\\s+', escaped)
        patterns.append((re.compile(r'\b' + escaped + r'\b', re.IGNORECASE), entry))

    _BLACKLIST_PATTERNS = patterns
    return patterns


def apply_hex_redaction(text: str) -> tuple[str, dict]:
    """
    Redact PII in 3 passes:
      1. Blacklist — known company names (exact whole-word match)
      2. Patterns — email, phone, address, zip, amounts, dates, SSN, EIN, company
      3. Non-whitelist — remaining capitalized word pairs not in whitelist (person names)

    Returns:
        (redacted_text, mapping) where mapping is {original_value: label}
    """
    whitelist = get_whitelist()
    blacklist_patterns = get_blacklist_patterns()
    mapping = {}
    redacted = text

    # --- PASS 1: Blacklist (known companies) ---
    found = True
    while found:
        found = False
        for pattern, entry_name in blacklist_patterns:
            match = pattern.search(redacted)
            if match and '[REDACTED]' not in match.group():
                mapping[match.group()] = "COMPANY"
                redacted = redacted[:match.start()] + '[REDACTED]' + redacted[match.end():]
                found = True
                break

    # --- PASS 2: Structural patterns ---
    structural_patterns = [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "EMAIL"),
        (r"\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "PHONE"),
        (r"\$[\d,]+(?:\.\d{2})?\b", "AMOUNT"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
        (r"\b\d{2}-\d{7}\b", "EIN"),
        (r"\b[A-Z][A-Za-z\s&,.'-]{1,30}(?:LLC|L\.L\.C\.|Inc|Inc\.|Corp|Corp\.|Corporation|Company|Co\.|LP|L\.P\.|LLP|L\.L\.P\.|Associates|Association|Group|Partners|Partnership|Holdings|Enterprises|Trust|Fund|REIT|Properties|Realty|Development|Investments|Capital|Ventures|Services|Solutions|Management|International|Global|National)\b", "COMPANY"),
        (r"(?i)\bP\.?\s*O\.?\s*Box\s+\d+\b", "ADDRESS"),
        (r"\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)?\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Way|Court|Ct)\.?(?:\s*[,#]\s*(?:Suite|Ste|Apt|Unit|#)?\s*\d+)?", "ADDRESS"),
        (r"\b\d{5}(?:-\d{4})?\b", "ZIP"),
        (r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b", "DATE"),
        (r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "DATE"),
    ]
    for pattern, label in structural_patterns:
        for match in re.finditer(pattern, redacted):
            value = match.group()
            if len(value.strip()) < 3 or '[REDACTED]' in value:
                continue
            mapping[value] = label
            redacted = redacted.replace(value, "[REDACTED]", 1)

    # --- PASS 3: Non-whitelist catch (person names) ---
    person_pattern = re.compile(
        r"\b[A-Z][a-z]+\s+(?:[A-Z]\.?\s+)?[A-Z][a-z]+(?:\s+(?:Jr|Sr|III|IV|II))?\b"
    )
    for match in person_pattern.finditer(redacted):
        value = match.group()
        if '[REDACTED]' in value:
            continue
        if all(w.lower() in whitelist for w in value.split()):
            continue
        mapping[value] = "PERSON"
        redacted = redacted.replace(value, "[REDACTED]", 1)

    return redacted, mapping


def reconstruct_pii(text: str, mapping: dict) -> str:
    """
    Reverse PII redaction — replace [REDACTED] tokens with original values.
    Replaces in reverse order of original text length (longest first) to avoid
    partial replacements.
    """
    if not mapping:
        return text

    result = text
    # Sort by length descending to replace longer matches first
    sorted_items = sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True)

    for original, label in sorted_items:
        # Replace one [REDACTED] at a time for each original value
        if '[REDACTED]' in result:
            result = result.replace('[REDACTED]', original, 1)

    return result


def reconstruct_pii_in_docx(docx_path: str, mapping: dict) -> bool:
    """
    Restore PII in a DOCX file by replacing [REDACTED] tokens with originals.
    Handles run-level replacement with paragraph-merge fallback.
    """
    if not mapping:
        return True

    try:
        from docx import Document
        doc = Document(docx_path)
        restored = 0

        # Sort by length descending
        sorted_items = sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True)

        for para in doc.paragraphs:
            if '[REDACTED]' not in para.text:
                continue

            for original, label in sorted_items:
                if '[REDACTED]' not in para.text:
                    break

                # Try run-level replacement
                found_in_run = False
                for run in para.runs:
                    if '[REDACTED]' in run.text:
                        run.text = run.text.replace('[REDACTED]', original, 1)
                        found_in_run = True
                        restored += 1
                        break

                # Fallback: merge paragraph text
                if not found_in_run and '[REDACTED]' in para.text and para.runs:
                    full = para.text.replace('[REDACTED]', original, 1)
                    para.runs[0].text = full
                    for run in para.runs[1:]:
                        run.text = ""
                    restored += 1

        doc.save(docx_path)
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"PII reconstruction failed: {e}")
        return False
