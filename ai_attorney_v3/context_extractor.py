"""
Context extraction for change presentation.
Extracts 150 words before and after each change location with word-boundary snapping.
"""

from models import ContextWindow


def extract_context(document_text: str, match_start: int, match_end: int, word_count: int = 150) -> ContextWindow:
    """
    Extract word-bounded context around a match location.

    Args:
        document_text: Full document text
        match_start: Character offset where the match begins
        match_end: Character offset where the match ends
        word_count: Number of words to include before and after (default 150)

    Returns:
        ContextWindow with before_text, match_text, after_text, and char offsets
    """
    match_text = document_text[match_start:match_end]

    # --- Before context ---
    before_text_raw = document_text[:match_start]
    before_words = before_text_raw.split()

    if len(before_words) <= word_count:
        before_text = before_text_raw
        before_start = 0
    else:
        # Take last N words
        target_words = before_words[-word_count:]
        # Find where these words start in the original text
        # Join and find from the right side
        target_str = ' '.join(target_words)
        # Find the approximate start by working backwards
        before_start = _find_word_boundary_start(before_text_raw, word_count)
        before_text = document_text[before_start:match_start]

    # --- After context ---
    after_text_raw = document_text[match_end:]
    after_words = after_text_raw.split()

    if len(after_words) <= word_count:
        after_text = after_text_raw
        after_end = len(document_text)
    else:
        # Take first N words
        after_end = _find_word_boundary_end(after_text_raw, word_count) + match_end
        after_text = document_text[match_end:after_end]

    return ContextWindow(
        before_text=before_text.strip(),
        match_text=match_text,
        after_text=after_text.strip(),
        before_start=before_start,
        after_end=after_end
    )


def _find_word_boundary_start(text: str, word_count: int) -> int:
    """
    Find the character position where the last `word_count` words begin.
    Snaps to word boundary (doesn't cut words).
    """
    words = text.split()
    if len(words) <= word_count:
        return 0

    # Count backwards from end to find where our target starts
    # We need to skip (total - word_count) words from the beginning
    skip_count = len(words) - word_count
    pos = 0
    words_skipped = 0

    i = 0
    while i < len(text) and words_skipped < skip_count:
        # Skip whitespace
        while i < len(text) and text[i] in ' \t\n\r':
            i += 1
        if i >= len(text):
            break
        # Skip word
        while i < len(text) and text[i] not in ' \t\n\r':
            i += 1
        words_skipped += 1

    # Skip trailing whitespace to land at start of next word
    while i < len(text) and text[i] in ' \t\n\r':
        i += 1

    return i


def _find_word_boundary_end(text: str, word_count: int) -> int:
    """
    Find the character position after the first `word_count` words.
    Snaps to word boundary.
    """
    words_counted = 0
    i = 0

    while i < len(text) and words_counted < word_count:
        # Skip whitespace
        while i < len(text) and text[i] in ' \t\n\r':
            i += 1
        if i >= len(text):
            break
        # Read word
        while i < len(text) and text[i] not in ' \t\n\r':
            i += 1
        words_counted += 1

    return i
