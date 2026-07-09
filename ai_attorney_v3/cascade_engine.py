"""
Cascade Engine — Four-tier validation for replacement text resolution.
Ensures all replacement text is verifiably sourced from the clause database.

Tier 1: Exact substring match
Tier 2: Fuzzy match (≥90% similarity)
Tier 3: Full clause replacement (locate section at ≥85%)
Tier 4: Human review flag
"""

import logging
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

from models import AIFinding, ClauseRecord, CascadeResult, AuditEntry, TextLocation
from text_utils import normalize_whitespace, locate_text_in_document, find_original_span
from audit_logger import AuditLogger
import config

logger = logging.getLogger(__name__)


class CascadeEngine:
    """Four-tier validation cascade for replacement text resolution."""

    def __init__(self, audit: Optional[AuditLogger] = None):
        self.audit = audit or AuditLogger()

    def resolve(self, finding: AIFinding, clause: ClauseRecord, document_text: str) -> CascadeResult:
        """
        Run the four-tier cascade for a single finding.
        Returns CascadeResult with verified replacement text or human review flag.
        """
        audit_trail = []

        # Tier 1: Exact substring match
        result = self._tier1_exact(finding, clause, audit_trail)
        if result:
            result.audit_trail = audit_trail
            return result

        # Tier 2: Fuzzy match
        result = self._tier2_fuzzy(finding, clause, audit_trail)
        if result:
            result.audit_trail = audit_trail
            return result

        # Tier 3: Full clause replacement
        result = self._tier3_full_clause(finding, clause, document_text, audit_trail)
        if result:
            result.audit_trail = audit_trail
            return result

        # Tier 4: Human review (always succeeds)
        result = self._tier4_human_review(finding, clause, audit_trail)
        result.audit_trail = audit_trail
        return result

    def _tier1_exact(
        self,
        finding: AIFinding,
        clause: ClauseRecord,
        audit_trail: list
    ) -> Optional[CascadeResult]:
        """
        Tier 1: Check if suggested_portion is a verbatim substring of the clause text.
        Normalizes whitespace before comparison but returns the actual clause text.
        """
        suggested = finding.suggested_portion
        clause_text = clause.clean_text

        if not suggested or not clause_text:
            entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                tier="tier1_exact",
                input_text=suggested[:100] if suggested else "",
                result="fail",
                reason="Empty suggested_portion or clause_text"
            )
            audit_trail.append(entry)
            self.audit.log_tier_attempt(finding.id, "tier1_exact", suggested or "", "fail", "empty input")
            return None

        # Try exact match first
        if suggested in clause_text:
            offset = clause_text.index(suggested)
            entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                tier="tier1_exact",
                input_text=suggested[:100],
                result="pass",
                reason=f"Exact match at offset {offset}"
            )
            audit_trail.append(entry)
            self.audit.log_tier_attempt(finding.id, "tier1_exact", suggested[:100], "pass", f"offset={offset}")

            return CascadeResult(
                replacement_text=suggested,
                confidence="exact",
                clause_id=clause.id,
                char_offset=offset,
            )

        # Try normalized match
        suggested_norm = normalize_whitespace(suggested)
        clause_norm = normalize_whitespace(clause_text)

        if suggested_norm in clause_norm:
            # Find the actual substring in original clause text
            span = find_original_span(clause_text, suggested_norm)
            if span:
                actual_text = clause_text[span[0]:span[1]]
                entry = AuditEntry(
                    timestamp=datetime.now().isoformat(),
                    tier="tier1_exact",
                    input_text=suggested[:100],
                    result="pass",
                    reason=f"Normalized match at offset {span[0]}"
                )
                audit_trail.append(entry)
                self.audit.log_tier_attempt(
                    finding.id, "tier1_exact", suggested[:100], "pass",
                    f"normalized match offset={span[0]}"
                )

                return CascadeResult(
                    replacement_text=actual_text,
                    confidence="exact",
                    clause_id=clause.id,
                    char_offset=span[0],
                )

        # Tier 1 failed
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            tier="tier1_exact",
            input_text=suggested[:100],
            result="fail",
            reason="Not a substring of clause text (exact or normalized)"
        )
        audit_trail.append(entry)
        self.audit.log_tier_attempt(finding.id, "tier1_exact", suggested[:100], "fail", "not found")
        return None

    def _tier2_fuzzy(
        self,
        finding: AIFinding,
        clause: ClauseRecord,
        audit_trail: list,
        threshold: float = None
    ) -> Optional[CascadeResult]:
        """
        Tier 2: Sliding window fuzzy match using difflib.SequenceMatcher.
        Finds the best matching substring of the clause at ≥90% similarity.
        """
        threshold = threshold or config.FUZZY_MATCH_THRESHOLD
        suggested = normalize_whitespace(finding.suggested_portion)
        clause_text = clause.clean_text
        clause_norm = normalize_whitespace(clause_text)

        if not suggested or len(suggested) < 10:
            entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                tier="tier2_fuzzy",
                input_text=suggested[:100] if suggested else "",
                result="fail",
                reason="Suggested text too short for fuzzy matching"
            )
            audit_trail.append(entry)
            self.audit.log_tier_attempt(finding.id, "tier2_fuzzy", suggested or "", "fail", "too short")
            return None

        # Window size range: ±20% of suggested length
        window_min = max(10, int(len(suggested) * 0.8))
        window_max = int(len(suggested) * 1.2)

        best_score = 0.0
        best_start = 0
        best_length = 0

        # Two-pass for long clauses
        if len(clause_norm) > 500:
            # Coarse pass: step=10
            candidate_regions = []
            for ws in range(window_min, window_max + 1, max(1, (window_max - window_min) // 3)):
                for start in range(0, len(clause_norm) - ws + 1, 10):
                    candidate = clause_norm[start:start + ws]
                    score = SequenceMatcher(None, suggested, candidate).ratio()
                    if score > 0.75:  # Candidate threshold
                        candidate_regions.append((start, ws, score))
                    if score > best_score:
                        best_score = score
                        best_start = start
                        best_length = ws

            # Fine pass in candidate regions
            for region_start, region_ws, _ in candidate_regions:
                fine_start = max(0, region_start - 50)
                fine_end = min(len(clause_norm), region_start + region_ws + 50)
                for ws in range(window_min, window_max + 1, max(1, (window_max - window_min) // 5)):
                    for start in range(fine_start, min(fine_end, len(clause_norm) - ws + 1)):
                        candidate = clause_norm[start:start + ws]
                        score = SequenceMatcher(None, suggested, candidate).ratio()
                        if score > best_score:
                            best_score = score
                            best_start = start
                            best_length = ws
        else:
            # Short clause — full scan
            for ws in range(window_min, window_max + 1, max(1, (window_max - window_min) // 5)):
                for start in range(0, len(clause_norm) - ws + 1):
                    candidate = clause_norm[start:start + ws]
                    score = SequenceMatcher(None, suggested, candidate).ratio()
                    if score > best_score:
                        best_score = score
                        best_start = start
                        best_length = ws

        if best_score >= threshold:
            # Map back to original clause text
            span = self._map_norm_to_original(clause_text, best_start, best_length)
            if span:
                actual_text = clause_text[span[0]:span[1]]
            else:
                actual_text = clause_norm[best_start:best_start + best_length]

            entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                tier="tier2_fuzzy",
                input_text=suggested[:100],
                result="pass",
                reason=f"Score {best_score:.3f} at offset {best_start}",
                score=best_score
            )
            audit_trail.append(entry)
            self.audit.log_tier_attempt(
                finding.id, "tier2_fuzzy", suggested[:100], "pass",
                f"score={best_score:.3f}", best_score
            )

            return CascadeResult(
                replacement_text=actual_text,
                confidence="fuzzy",
                clause_id=clause.id,
                char_offset=best_start,
                similarity_score=best_score,
            )

        # Tier 2 failed
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            tier="tier2_fuzzy",
            input_text=suggested[:100],
            result="fail",
            reason=f"Best score {best_score:.3f} below threshold {threshold}",
            score=best_score
        )
        audit_trail.append(entry)
        self.audit.log_tier_attempt(
            finding.id, "tier2_fuzzy", suggested[:100], "fail",
            f"best={best_score:.3f} < {threshold}", best_score
        )
        return None

    def _tier3_full_clause(
        self,
        finding: AIFinding,
        clause: ClauseRecord,
        document_text: str,
        audit_trail: list
    ) -> Optional[CascadeResult]:
        """
        Tier 3: Use the full clause text as replacement.
        ONLY applies when the clause is short enough to be a reasonable replacement
        (under 200 chars) AND the document section is a similar length.
        Otherwise, skip to Tier 4 — full clause insertion into a short phrase is never correct.
        """
        threshold = config.FULL_CLAUSE_LOCATION_THRESHOLD

        # Guard: don't insert a full clause if it's much longer than what we're replacing
        # This prevents shoving a paragraph into a spot that needs a few words changed
        clause_len = len(clause.clean_text)
        find_len = len(finding.document_section)

        if clause_len > 200 or clause_len > find_len * 3:
            entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                tier="tier3_full_clause",
                input_text=finding.document_section[:100],
                result="fail",
                reason=f"Clause too long for full replacement ({clause_len} chars vs {find_len} char find). Skipping to human review.",
                score=0.0
            )
            audit_trail.append(entry)
            self.audit.log_tier_attempt(
                finding.id, "tier3_full_clause", finding.document_section[:100], "fail",
                f"clause_len={clause_len} too long vs find_len={find_len}"
            )
            return None

        location = locate_text_in_document(
            document_text,
            finding.document_section,
            threshold=threshold
        )

        if location and location.confidence >= threshold:
            entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                tier="tier3_full_clause",
                input_text=finding.document_section[:100],
                result="pass",
                reason=f"Located at [{location.start}:{location.end}] confidence={location.confidence:.3f} method={location.method}",
                score=location.confidence
            )
            audit_trail.append(entry)
            self.audit.log_tier_attempt(
                finding.id, "tier3_full_clause", finding.document_section[:100], "pass",
                f"confidence={location.confidence:.3f}", location.confidence
            )

            return CascadeResult(
                replacement_text=clause.clean_text,
                confidence="full_clause",
                clause_id=clause.id,
                char_offset=0,
            )

        # Tier 3 failed
        conf = location.confidence if location else 0.0
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            tier="tier3_full_clause",
            input_text=finding.document_section[:100],
            result="fail",
            reason=f"Location confidence {conf:.3f} below threshold {threshold}" if location else "Could not locate section in document",
            score=conf
        )
        audit_trail.append(entry)
        self.audit.log_tier_attempt(
            finding.id, "tier3_full_clause", finding.document_section[:100], "fail",
            f"confidence={conf:.3f}" if location else "not found", conf
        )
        return None

    def _tier4_human_review(
        self,
        finding: AIFinding,
        clause: ClauseRecord,
        audit_trail: list
    ) -> CascadeResult:
        """
        Tier 4: Flag for human review. Always succeeds.
        No replacement text is applied — user must handle manually.
        """
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            tier="tier4_human_review",
            input_text=finding.document_section[:100],
            result="pass",
            reason="Flagged for manual review after tiers 1-3 failed"
        )
        audit_trail.append(entry)
        self.audit.log_tier_attempt(
            finding.id, "tier4_human_review", finding.document_section[:100], "pass",
            "escalated to human"
        )

        return CascadeResult(
            replacement_text=None,
            confidence="manual",
            clause_id=clause.id,
            requires_human=True,
            full_clause_text=clause.clean_text,
            ai_issue=finding.issue,
            ai_document_section=finding.document_section,
        )

    def _map_norm_to_original(self, original: str, norm_offset: int, norm_length: int) -> Optional[tuple[int, int]]:
        """Map normalized text offset back to original text positions."""
        from text_utils import _map_norm_offset_to_original
        return _map_norm_offset_to_original(original, norm_offset, norm_length)
