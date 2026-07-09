"""
Provenance Verifier — Final gate before presenting changes to user.
Ensures every replacement text is verifiably a substring of the clause database.
No AI-generated language can pass this check.
"""

import logging
from typing import Optional

from models import ProposedChange, ClauseRecord, VerificationResult
from text_utils import normalize_whitespace

logger = logging.getLogger(__name__)


class ProvenanceVerifier:
    """Ensures all replacement text traces back to attorney-approved clause text."""

    def verify(self, change: ProposedChange, clause: Optional[ClauseRecord]) -> VerificationResult:
        """
        Confirm that change.replace is a verbatim substring of clause.clean_text.
        This is the FINAL check before presenting to the user.

        Rules engine changes pass automatically (source is hardcoded).
        Manual/human review items pass as "human_review" (no auto-apply).
        """
        # Rules engine changes are hardcoded — always verified
        if change.source == "rules_engine":
            return VerificationResult(
                verified=True,
                method="rules_engine",
                clause_id=None,
            )

        # Manual items don't have replacement text — they're for human review
        if change.confidence == "manual" or change.replace is None:
            return VerificationResult(
                verified=True,
                method="human_review",
                clause_id=change.clause_id,
            )

        # Must have a clause to verify against
        if not clause:
            logger.warning(f"Change {change.id}: No clause provided for verification — REJECTED")
            return VerificationResult(verified=False, method="provenance_failed")

        # Check exact substring
        if change.replace in clause.clean_text:
            offset = clause.clean_text.index(change.replace)
            return VerificationResult(
                verified=True,
                method=change.confidence,
                clause_id=clause.id,
                char_offset=offset,
                char_length=len(change.replace),
            )

        # Try normalized comparison
        replace_norm = normalize_whitespace(change.replace)
        clause_norm = normalize_whitespace(clause.clean_text)

        if replace_norm in clause_norm:
            offset = clause_norm.index(replace_norm)
            return VerificationResult(
                verified=True,
                method=f"{change.confidence}_normalized",
                clause_id=clause.id,
                char_offset=offset,
                char_length=len(replace_norm),
            )

        # FAILED — replacement text is not from this clause
        logger.warning(
            f"Change {change.id}: Replacement text NOT found in clause {clause.id} — REJECTED"
        )
        return VerificationResult(verified=False, method="provenance_failed")

    def verify_all(self, changes: list[ProposedChange], clauses: list[ClauseRecord]) -> list[ProposedChange]:
        """
        Verify all proposed changes. Returns only verified changes.
        Unverified cascade changes are escalated to manual review.
        """
        verified_changes = []

        for change in changes:
            # Find the referenced clause
            clause = None
            if change.clause_id and clauses:
                if 1 <= change.clause_id <= len(clauses):
                    clause = clauses[change.clause_id - 1]

            result = self.verify(change, clause)

            if result.verified:
                verified_changes.append(change)
            else:
                # Escalate to manual review
                logger.info(f"Change {change.id}: Escalated to manual review (provenance failed)")
                change.confidence = "manual"
                change.full_clause_text = clause.clean_text if clause else None
                change.replace = ""  # Clear the unverified replacement
                verified_changes.append(change)

        return verified_changes

    def generate_report(self, changes: list[ProposedChange], clauses: list[ClauseRecord]) -> dict:
        """
        Generate a provenance report for the entire document.
        Lists every change with its verification status and source.
        """
        report = {
            "total_changes": len(changes),
            "verified_count": 0,
            "manual_count": 0,
            "rules_count": 0,
            "changes": [],
        }

        for change in changes:
            clause = None
            if change.clause_id and clauses and 1 <= change.clause_id <= len(clauses):
                clause = clauses[change.clause_id - 1]

            result = self.verify(change, clause)

            entry = {
                "change_id": change.id,
                "confidence": change.confidence,
                "source": change.source,
                "clause_id": change.clause_id,
                "clause_desc": change.clause_desc,
                "verified": result.verified,
                "method": result.method,
            }

            if result.char_offset is not None:
                entry["char_offset"] = result.char_offset
                entry["char_length"] = result.char_length

            report["changes"].append(entry)

            if change.source == "rules_engine":
                report["rules_count"] += 1
            elif change.confidence == "manual":
                report["manual_count"] += 1
            elif result.verified:
                report["verified_count"] += 1

        return report
