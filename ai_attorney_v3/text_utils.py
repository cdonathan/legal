"""
Text utility functions for normalization, HTML cleaning, and text location.
Used across cascade engine, rules engine, and document processor.
"""

import re
from difflib import SequenceMatcher
from typing import Optional
from models import TextLocation


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace (tabs, newlines, multiple spaces) to single spaces and strip."""
    return re.sub(r'\s+', ' ', text).strip()


def clean_clause_html(html: str) -> str:
    """
    Convert clause HTML content to clean plaintext.
    1. Strip HTML tags
    2. Decode HTML entities
    3. Replace template placeholders with ___
    4. Normalize whitespace
    """
    if not html:
        return ""
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Decode common HTML entities
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', text)
    # Replace template placeholders
    text = re.sub(r'\[!@[^\]]*\]', '___', text)
    text = re.sub(r'\[\*[^\]]*\]', '___', text)
    text = re.sub(r'\[@[^\]]*\]', '___', text)
    # Normalize whitespace
    text = normalize_whitespace(text)
    return text


def fix_ligatures(text: str) -> str:
    """Replace common PDF ligature characters with standard ASCII."""
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
    text = text.replace("\ufb00", "ff").replace("\ufb03", "ffi").replace("\ufb04", "ffl")
    text = re.sub(r"\ufffd(?=[ilI])", "f", text)
    text = text.replace("\ufffd", "f")
    return text


def locate_text_in_document(document_text: str, search_text: str, threshold: float = 0.85) -> Optional[TextLocation]:
    """
    Multi-strategy text location within a document.
    Tries in order:
    1. Exact substring match
    2. Normalized match (collapse whitespace, normalize punctuation)
    3. Fuzzy match using SequenceMatcher at the given threshold

    Returns TextLocation with start, end, confidence, and method — or None if not found.
    """
    if not search_text or not document_text:
        return None

    # Strategy 1: Exact match
    idx = document_text.find(search_text)
    if idx >= 0:
        return TextLocation(
            start=idx,
            end=idx + len(search_text),
            confidence=1.0,
            method="exact"
        )

    # Strategy 2: Normalized match
    search_norm = normalize_whitespace(search_text)
    doc_norm = normalize_whitespace(document_text)
    idx_norm = doc_norm.find(search_norm)
    if idx_norm >= 0:
        # Map normalized position back to original document
        original_span = find_original_span(document_text, search_norm)
        if original_span:
            start, end = original_span
            return TextLocation(
                start=start,
                end=end,
                confidence=0.95,
                method="normalized"
            )

    # Strategy 3: Fuzzy match — slide a window across normalized document
    if len(search_norm) < 10:
        return None  # Too short for reliable fuzzy matching

    best_score = 0.0
    best_start = 0
    best_length = len(search_norm)
    window_size = len(search_norm)

    # Allow ±20% window variation
    min_window = max(10, int(window_size * 0.8))
    max_window = int(window_size * 1.2)

    for ws in range(min_window, max_window + 1, max(1, (max_window - min_window) // 5)):
        step = max(1, ws // 10)
        for start in range(0, len(doc_norm) - ws + 1, step):
            candidate = doc_norm[start:start + ws]
            score = SequenceMatcher(None, search_norm, candidate).ratio()
            if score > best_score:
                best_score = score
                best_start = start
                best_length = ws

    if best_score >= threshold:
        # Map back to original positions (approximate)
        original_span = _map_norm_offset_to_original(document_text, best_start, best_length)
        if original_span:
            return TextLocation(
                start=original_span[0],
                end=original_span[1],
                confidence=best_score,
                method="fuzzy"
            )

    return None


def find_original_span(original_text: str, normalized_search: str) -> Optional[tuple[int, int]]:
    """
    Given original text and a normalized search string, find the actual
    character span in the original that corresponds to the normalized match.
    """
    orig_norm = normalize_whitespace(original_text)
    idx = orig_norm.find(normalized_search)
    if idx < 0:
        return None

    return _map_norm_offset_to_original(original_text, idx, len(normalized_search))


def _map_norm_offset_to_original(original_text: str, norm_offset: int, norm_length: int) -> Optional[tuple[int, int]]:
    """
    Map a position in normalized text back to the original text.
    Builds a character-by-character mapping from normalized positions to original positions.
    """
    # Build mapping: for each position in normalized text, track original position
    norm_to_orig = []
    orig_i = 0
    in_whitespace = False

    # Skip leading whitespace in original
    while orig_i < len(original_text) and original_text[orig_i] in ' \t\n\r':
        orig_i += 1

    for orig_i_scan in range(orig_i, len(original_text)):
        ch = original_text[orig_i_scan]
        if ch in ' \t\n\r':
            if not in_whitespace:
                # First whitespace char maps to the normalized single space
                norm_to_orig.append(orig_i_scan)
                in_whitespace = True
            # Subsequent whitespace chars are collapsed — no mapping entry
        else:
            norm_to_orig.append(orig_i_scan)
            in_whitespace = False

    if norm_offset >= len(norm_to_orig):
        return None

    start = norm_to_orig[norm_offset]
    end_norm_pos = norm_offset + norm_length
    if end_norm_pos >= len(norm_to_orig):
        end = len(original_text)
    else:
        end = norm_to_orig[end_norm_pos]

    return (start, end)
