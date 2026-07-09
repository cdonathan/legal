"""
Tests for the Cascade Engine — all four tiers.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models import AIFinding, ClauseRecord, CascadeResult
from cascade_engine import CascadeEngine
from audit_logger import AuditLogger


@pytest.fixture
def engine():
    return CascadeEngine(audit=AuditLogger())


@pytest.fixture
def sample_clause():
    return ClauseRecord(
        id=1,
        form_type="NDA",
        category_id=1,
        prov_desc="Confidentiality Exceptions",
        html_data_text="",
        clean_text="Confidential Information does not include information that: 1. becomes publicly available without breach of this Agreement 2. was previously known by the Receiving Party 3. is received from a third party without confidentiality obligation 4. is independently developed by the Receiving Party",
        risk_level="high"
    )


@pytest.fixture
def sample_finding():
    return AIFinding(
        id=1,
        clause_id=1,
        document_section="The Recipient agrees to keep all information confidential",
        issue="No carve-outs for publicly available or independently developed information",
        suggested_portion="Confidential Information does not include information that: 1. becomes publicly available without breach of this Agreement 2. was previously known by the Receiving Party",
        priority="high"
    )


# ============================================================
# TIER 1: Exact Substring Match
# ============================================================

class TestTier1Exact:
    def test_exact_match_verbatim(self, engine, sample_clause):
        """Tier 1 passes when suggested_portion is verbatim in clause."""
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="some doc text",
            issue="missing carve-outs",
            suggested_portion="becomes publicly available without breach of this Agreement",
            priority="high"
        )
        result = engine._tier1_exact(finding, sample_clause, [])
        assert result is not None
        assert result.confidence == "exact"
        assert result.replacement_text == "becomes publicly available without breach of this Agreement"
        assert result.char_offset is not None

    def test_exact_match_full_clause(self, engine, sample_clause):
        """Tier 1 passes when suggested is the entire clause text."""
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="doc text",
            issue="missing",
            suggested_portion=sample_clause.clean_text,
            priority="high"
        )
        result = engine._tier1_exact(finding, sample_clause, [])
        assert result is not None
        assert result.confidence == "exact"
        assert result.replacement_text == sample_clause.clean_text

    def test_exact_match_with_whitespace_normalization(self, engine):
        """Tier 1 passes when only whitespace differs."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Test",
            html_data_text="",
            clean_text="The Receiving Party shall return or destroy all Confidential Information",
            risk_level="high"
        )
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="doc text",
            issue="test",
            suggested_portion="The Receiving Party  shall  return or destroy all Confidential Information",
            priority="high"
        )
        result = engine._tier1_exact(finding, clause, [])
        assert result is not None
        assert result.confidence == "exact"

    def test_exact_match_fails_when_not_substring(self, engine, sample_clause):
        """Tier 1 fails when suggested text is not in clause."""
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="doc text",
            issue="test",
            suggested_portion="This text is completely made up and not in the clause at all",
            priority="high"
        )
        result = engine._tier1_exact(finding, sample_clause, [])
        assert result is None

    def test_exact_match_fails_on_empty_suggested(self, engine, sample_clause):
        """Tier 1 fails gracefully with empty suggested text."""
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="doc text",
            issue="test",
            suggested_portion="",
            priority="high"
        )
        result = engine._tier1_exact(finding, sample_clause, [])
        assert result is None

    def test_exact_match_case_sensitive(self, engine):
        """Tier 1 is case-sensitive (clause text must match exactly)."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Test",
            html_data_text="",
            clean_text="The Receiving Party shall maintain strict confidence",
            risk_level="high"
        )
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="doc text",
            issue="test",
            suggested_portion="the receiving party shall maintain strict confidence",
            priority="high"
        )
        # Normalized match should still work since normalization doesn't change case
        # but exact substring won't match due to case
        result = engine._tier1_exact(finding, clause, [])
        assert result is None


# ============================================================
# TIER 2: Fuzzy Match
# ============================================================

class TestTier2Fuzzy:
    def test_fuzzy_match_minor_difference(self, engine):
        """Tier 2 passes when text is 90%+ similar (minor punctuation diff)."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Test",
            html_data_text="",
            clean_text="The Receiving Party may disclose Confidential Information to its directors, officers, employees, affiliates, attorneys, accountants, financial advisors, consultants, lenders, investors, or other professional advisors who have a need to know such information for the Purpose.",
            risk_level="high"
        )
        # Minor diff: missing Oxford comma, slight rewording
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="doc text",
            issue="test",
            suggested_portion="The Receiving Party may disclose Confidential Information to its directors, officers, employees, affiliates, attorneys, accountants, financial advisors, consultants, lenders, investors or other professional advisors who have a need to know such information for the Purpose.",
            priority="high"
        )
        result = engine._tier2_fuzzy(finding, clause, [])
        assert result is not None
        assert result.confidence == "fuzzy"
        assert result.similarity_score >= 0.90
        # Replacement text should be from the CLAUSE, not the AI suggestion
        assert result.replacement_text in clause.clean_text or result.replacement_text.strip() in clause.clean_text

    def test_fuzzy_match_fails_below_threshold(self, engine):
        """Tier 2 fails when best match is below 90%."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Test",
            html_data_text="",
            clean_text="Upon written request the Receiving Party shall promptly return or destroy all Confidential Information",
            risk_level="high"
        )
        # Very different text
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="doc text",
            issue="test",
            suggested_portion="The agreement shall terminate after a period of two years from the effective date of signing",
            priority="high"
        )
        result = engine._tier2_fuzzy(finding, clause, [])
        assert result is None

    def test_fuzzy_match_short_text_rejected(self, engine):
        """Tier 2 rejects text shorter than 10 chars."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Test",
            html_data_text="",
            clean_text="Some long clause text here",
            risk_level="high"
        )
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="doc text",
            issue="test",
            suggested_portion="short",
            priority="high"
        )
        result = engine._tier2_fuzzy(finding, clause, [])
        assert result is None

    def test_fuzzy_returns_actual_clause_text(self, engine):
        """Tier 2 returns text from the actual clause, not the AI suggestion."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Test",
            html_data_text="",
            clean_text="Nothing in this Agreement obligates either Party to enter into any transaction or business relationship.",
            risk_level="high"
        )
        # AI slightly rephrased
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="doc text",
            issue="test",
            suggested_portion="Nothing in this Agreement obligates either Party to enter into any transaction or business relationship",
            priority="high"
        )
        result = engine._tier2_fuzzy(finding, clause, [])
        if result:
            # The returned text must be from the clause itself
            assert result.replacement_text in clause.clean_text


# ============================================================
# TIER 3: Full Clause Replacement
# ============================================================

class TestTier3FullClause:
    def test_full_clause_locates_section(self, engine):
        """Tier 3 passes when document section is locatable."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Term",
            html_data_text="",
            clean_text="This Agreement shall remain in effect for one (1) year from the Effective Date.",
            risk_level="high"
        )
        document_text = "This is the preamble. The parties agree to the following terms. This agreement shall continue indefinitely until terminated by either party. Additional clauses follow."
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="This agreement shall continue indefinitely until terminated by either party",
            issue="No term limit",
            suggested_portion="This Agreement shall remain in effect for one (1) year",
            priority="high"
        )
        result = engine._tier3_full_clause(finding, clause, document_text, [])
        assert result is not None
        assert result.confidence == "full_clause"
        assert result.replacement_text == clause.clean_text

    def test_full_clause_fails_when_section_not_found(self, engine):
        """Tier 3 fails when document section cannot be located."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Term",
            html_data_text="",
            clean_text="Some clause text",
            risk_level="high"
        )
        document_text = "Completely unrelated document text about other topics entirely."
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="This text is not in the document at all and cannot be found anywhere",
            issue="test",
            suggested_portion="Some clause text",
            priority="high"
        )
        result = engine._tier3_full_clause(finding, clause, document_text, [])
        assert result is None


# ============================================================
# TIER 4: Human Review
# ============================================================

class TestTier4HumanReview:
    def test_human_review_always_succeeds(self, engine, sample_finding, sample_clause):
        """Tier 4 always returns a result."""
        result = engine._tier4_human_review(sample_finding, sample_clause, [])
        assert result is not None
        assert result.confidence == "manual"
        assert result.requires_human is True
        assert result.replacement_text is None

    def test_human_review_includes_context(self, engine, sample_finding, sample_clause):
        """Tier 4 includes full clause text and AI issue for display."""
        result = engine._tier4_human_review(sample_finding, sample_clause, [])
        assert result.full_clause_text == sample_clause.clean_text
        assert result.ai_issue == sample_finding.issue
        assert result.ai_document_section == sample_finding.document_section


# ============================================================
# RESOLVE ORCHESTRATOR
# ============================================================

class TestResolve:
    def test_resolve_uses_tier1_when_exact(self, engine, sample_clause):
        """resolve() returns tier 1 result when exact match exists."""
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="some doc text here that is long enough",
            issue="test",
            suggested_portion="becomes publicly available without breach of this Agreement",
            priority="high"
        )
        doc = "some doc text here that is long enough for the test"
        result = engine.resolve(finding, sample_clause, doc)
        assert result.confidence == "exact"

    def test_resolve_cascades_to_tier4_when_nothing_matches(self, engine):
        """resolve() falls through to tier 4 when all tiers fail."""
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Test",
            html_data_text="",
            clean_text="Very specific clause language that will not match anything",
            risk_level="high"
        )
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="text not in document anywhere at all for sure",
            issue="test",
            suggested_portion="Completely different AI hallucinated text that is not in clause",
            priority="high"
        )
        doc = "A different document with completely unrelated content about something else entirely."
        result = engine.resolve(finding, clause, doc)
        assert result.confidence == "manual"
        assert result.requires_human is True

    def test_resolve_builds_audit_trail(self, engine, sample_clause):
        """resolve() records audit entries for each tier attempted."""
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="text not in document",
            issue="test",
            suggested_portion="text not in clause either",
            priority="high"
        )
        doc = "A document without matching text."
        result = engine.resolve(finding, sample_clause, doc)
        # Should have entries for tiers 1, 2, 3, and 4
        assert len(result.audit_trail) >= 4
        tiers = [e.tier for e in result.audit_trail]
        assert "tier1_exact" in tiers
        assert "tier2_fuzzy" in tiers
        assert "tier3_full_clause" in tiers
        assert "tier4_human_review" in tiers
