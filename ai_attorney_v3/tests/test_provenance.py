"""
Tests for the Provenance Verifier — ensures all replacement text traces to clause DB.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models import ProposedChange, ClauseRecord
from provenance_verifier import ProvenanceVerifier


@pytest.fixture
def verifier():
    return ProvenanceVerifier()


@pytest.fixture
def sample_clause():
    return ClauseRecord(
        id=5,
        form_type="NDA",
        category_id=2,
        prov_desc="Permitted Recipients",
        html_data_text="",
        clean_text="The Receiving Party may disclose Confidential Information to its directors, officers, employees, affiliates, attorneys, accountants, financial advisors, consultants, lenders, investors, or other professional advisors who have a need to know such information for the Purpose.",
        risk_level="high"
    )


class TestProvenanceVerification:
    def test_verify_exact_substring_passes(self, verifier, sample_clause):
        """Passes when replacement text is verbatim in clause."""
        change = ProposedChange(
            id=1, type="replace",
            find="employees and agents",
            replace="directors, officers, employees, affiliates, attorneys, accountants, financial advisors, consultants, lenders, investors, or other professional advisors",
            before_context="", after_context="",
            confidence="exact", source="cascade_engine",
            clause_id=5, reasoning="test"
        )
        result = verifier.verify(change, sample_clause)
        assert result.verified is True
        assert result.method == "exact"
        assert result.char_offset is not None
        assert result.char_length == len(change.replace)

    def test_verify_fails_when_text_not_in_clause(self, verifier, sample_clause):
        """Fails when replacement text is not from the clause."""
        change = ProposedChange(
            id=1, type="replace",
            find="employees and agents",
            replace="any person or entity that the Receiving Party deems appropriate in its sole discretion",
            before_context="", after_context="",
            confidence="fuzzy", source="cascade_engine",
            clause_id=5, reasoning="test"
        )
        result = verifier.verify(change, sample_clause)
        assert result.verified is False
        assert result.method == "provenance_failed"

    def test_verify_rules_engine_always_passes(self, verifier):
        """Rules engine changes always pass (they're hardcoded, not AI-sourced)."""
        change = ProposedChange(
            id=1, type="replace",
            find="attorney's fees",
            replace="reasonable attorney's fees",
            before_context="", after_context="",
            confidence="exact", source="rules_engine",
            reasoning="test"
        )
        result = verifier.verify(change, None)
        assert result.verified is True
        assert result.method == "rules_engine"

    def test_verify_manual_review_passes(self, verifier, sample_clause):
        """Manual review items pass with human_review method."""
        change = ProposedChange(
            id=1, type="replace",
            find="some text",
            replace="",
            before_context="", after_context="",
            confidence="manual", source="cascade_engine",
            clause_id=5, reasoning="test"
        )
        result = verifier.verify(change, sample_clause)
        assert result.verified is True
        assert result.method == "human_review"

    def test_verify_no_clause_fails(self, verifier):
        """Fails when no clause is provided for cascade changes."""
        change = ProposedChange(
            id=1, type="replace",
            find="some text",
            replace="some replacement",
            before_context="", after_context="",
            confidence="exact", source="cascade_engine",
            clause_id=5, reasoning="test"
        )
        result = verifier.verify(change, None)
        assert result.verified is False

    def test_verify_normalized_whitespace_passes(self, verifier):
        """Passes when only whitespace differs between replacement and clause."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Test",
            html_data_text="",
            clean_text="Upon written request the Receiving Party shall promptly return or destroy all Confidential Information.",
            risk_level="high"
        )
        change = ProposedChange(
            id=1, type="replace",
            find="old text",
            replace="Upon written request  the Receiving Party  shall promptly return or destroy all Confidential Information.",
            before_context="", after_context="",
            confidence="fuzzy", source="cascade_engine",
            clause_id=1, reasoning="test"
        )
        result = verifier.verify(change, clause)
        assert result.verified is True


class TestVerifyAll:
    def test_verify_all_escalates_failures(self, verifier, sample_clause):
        """verify_all escalates failed verifications to manual review."""
        changes = [
            ProposedChange(
                id=1, type="replace",
                find="old", replace="directors, officers, employees",
                before_context="", after_context="",
                confidence="exact", source="cascade_engine",
                clause_id=5, reasoning="test"
            ),
            ProposedChange(
                id=2, type="replace",
                find="old", replace="AI hallucinated this text completely",
                before_context="", after_context="",
                confidence="fuzzy", source="cascade_engine",
                clause_id=5, reasoning="test"
            ),
        ]
        result = verifier.verify_all(changes, [sample_clause] * 5)
        # Both should be in result (second one escalated to manual)
        assert len(result) == 2
        assert result[0].confidence == "exact"
        assert result[1].confidence == "manual"


class TestGenerateReport:
    def test_report_structure(self, verifier, sample_clause):
        """Report has expected structure and counts."""
        changes = [
            ProposedChange(
                id=1, type="replace",
                find="old", replace="directors, officers, employees",
                before_context="", after_context="",
                confidence="exact", source="cascade_engine",
                clause_id=5, reasoning="test"
            ),
            ProposedChange(
                id=2, type="replace",
                find="fees", replace="reasonable attorney's fees",
                before_context="", after_context="",
                confidence="exact", source="rules_engine",
                reasoning="test"
            ),
        ]
        report = verifier.generate_report(changes, [sample_clause] * 5)
        assert report["total_changes"] == 2
        assert report["rules_count"] == 1
        assert "changes" in report
        assert len(report["changes"]) == 2
