"""
Integration tests — end-to-end pipeline validation.
Tests the full flow from text through cascade to provenance verification.
Does NOT call the actual OpenAI API (uses mocked AI responses).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models import AIFinding, ClauseRecord, ProposedChange
from cascade_engine import CascadeEngine
from provenance_verifier import ProvenanceVerifier
from rules_engine import RulesEngine
from context_extractor import extract_context
from text_utils import normalize_whitespace, clean_clause_html, locate_text_in_document
from audit_logger import AuditLogger


# ============================================================
# Sample data simulating a real NDA processing scenario
# ============================================================

SAMPLE_NDA_TEXT = """CONFIDENTIALITY AND NON-DISCLOSURE AGREEMENT

This Agreement is entered into as of _______ by and between ABC Properties LLC ("Disclosing Party") and the undersigned ("Receiving Party").

1. CONFIDENTIAL INFORMATION. The Disclosing Party may disclose certain confidential and proprietary information to the Receiving Party. The Receiving Party agrees to hold all such information in strict confidence.

2. USE RESTRICTIONS. The Receiving Party shall use the Confidential Information solely for the purpose of evaluating a potential transaction. The Receiving Party shall not disclose the information to anyone other than its employees and legal counsel.

3. RETURN OF MATERIALS. Upon termination of this Agreement, the Receiving Party shall immediately return all materials to the Disclosing Party.

4. REMEDIES. The Receiving Party acknowledges that any breach may cause irreparable harm. The Disclosing Party shall be entitled to any and all forms and types of remuneration and the Receiving Party shall pay all attorney's fees incurred in enforcing this Agreement.

5. TERM. This Agreement shall survive in perpetuity.

6. MISCELLANEOUS. This Agreement may be executed in counterparts. Facsimile signatures shall be deemed valid."""


SAMPLE_CLAUSES = [
    ClauseRecord(
        id=1, form_type="NDA", category_id=1,
        prov_desc="Confidentiality Exceptions",
        html_data_text="",
        clean_text="Confidential Information does not include information that: 1. becomes publicly available without breach of this Agreement 2. was previously known by the Receiving Party 3. is received from a third party without confidentiality obligation 4. is independently developed by the Receiving Party",
        risk_level="high"
    ),
    ClauseRecord(
        id=2, form_type="NDA", category_id=2,
        prov_desc="Permitted Recipients",
        html_data_text="",
        clean_text="The Receiving Party may disclose Confidential Information to its directors, officers, employees, affiliates, attorneys, accountants, financial advisors, consultants, lenders, investors, or other professional advisors who have a need to know such information for the Purpose.",
        risk_level="high"
    ),
    ClauseRecord(
        id=3, form_type="NDA", category_id=3,
        prov_desc="Return or Destruction",
        html_data_text="",
        clean_text="Upon written request, the Receiving Party shall promptly return or destroy all Confidential Information.",
        risk_level="medium"
    ),
    ClauseRecord(
        id=4, form_type="NDA", category_id=4,
        prov_desc="Term of Agreement",
        html_data_text="",
        clean_text="This Agreement shall remain in effect for one (1) year from the Effective Date.",
        risk_level="high"
    ),
    ClauseRecord(
        id=5, form_type="NDA", category_id=5,
        prov_desc="Electronic Signatures",
        html_data_text="",
        clean_text="This Agreement may be executed in counterparts and electronic signatures shall be deemed valid.",
        risk_level="low"
    ),
]


# Simulated AI findings (what AI would return after evaluation)
MOCK_AI_FINDINGS = [
    AIFinding(
        id=1, clause_id=1,
        document_section="The Receiving Party agrees to hold all such information in strict confidence",
        issue="No carve-outs for publicly available, previously known, or independently developed information",
        suggested_portion="Confidential Information does not include information that: 1. becomes publicly available without breach of this Agreement 2. was previously known by the Receiving Party 3. is received from a third party without confidentiality obligation 4. is independently developed by the Receiving Party",
        priority="high"
    ),
    AIFinding(
        id=2, clause_id=2,
        document_section="shall not disclose the information to anyone other than its employees and legal counsel",
        issue="Disclosure list too narrow — missing investors, partners, financial advisors",
        suggested_portion="The Receiving Party may disclose Confidential Information to its directors, officers, employees, affiliates, attorneys, accountants, financial advisors, consultants, lenders, investors, or other professional advisors who have a need to know such information for the Purpose.",
        priority="high"
    ),
    AIFinding(
        id=3, clause_id=3,
        document_section="the Receiving Party shall immediately return all materials to the Disclosing Party",
        issue="No destroy option, automatic trigger instead of upon request",
        suggested_portion="Upon written request, the Receiving Party shall promptly return or destroy all Confidential Information.",
        priority="medium"
    ),
    AIFinding(
        id=4, clause_id=5,
        document_section="Facsimile signatures shall be deemed valid",
        issue="Only facsimile mentioned, no electronic signatures",
        suggested_portion="electronic signatures shall be deemed valid",
        priority="low"
    ),
]


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestEndToEndCascade:
    def test_all_findings_resolve_through_cascade(self):
        """All mock findings should resolve through the cascade (most at tier 1)."""
        audit = AuditLogger()
        engine = CascadeEngine(audit=audit)

        results = []
        for finding in MOCK_AI_FINDINGS:
            clause = SAMPLE_CLAUSES[finding.clause_id - 1]
            result = engine.resolve(finding, clause, SAMPLE_NDA_TEXT)
            results.append(result)

        # All should resolve (not all necessarily at tier 1)
        assert len(results) == 4
        # None should require human review for these clean findings
        manual_count = sum(1 for r in results if r.confidence == "manual")
        assert manual_count == 0, f"Expected 0 manual, got {manual_count}"

    def test_all_replacements_pass_provenance(self):
        """Every replacement text must be verifiable against clause database."""
        audit = AuditLogger()
        engine = CascadeEngine(audit=audit)
        verifier = ProvenanceVerifier()

        for finding in MOCK_AI_FINDINGS:
            clause = SAMPLE_CLAUSES[finding.clause_id - 1]
            result = engine.resolve(finding, clause, SAMPLE_NDA_TEXT)

            if result.replacement_text:
                # Build a ProposedChange for verification
                change = ProposedChange(
                    id=finding.id, type="replace",
                    find=finding.document_section,
                    replace=result.replacement_text,
                    before_context="", after_context="",
                    confidence=result.confidence,
                    source="cascade_engine",
                    clause_id=clause.id,
                    reasoning=finding.issue
                )
                verification = verifier.verify(change, clause)
                assert verification.verified, (
                    f"Finding {finding.id} ({clause.prov_desc}): "
                    f"Replacement text failed provenance verification!\n"
                    f"Replace: '{result.replacement_text[:80]}...'\n"
                    f"Clause: '{clause.clean_text[:80]}...'"
                )


class TestRulesEngineOnSampleNDA:
    def test_rules_find_expected_patterns(self):
        """Rules engine should catch attorney's fees and perpetuity in sample NDA."""
        engine = RulesEngine()
        changes = engine.apply(SAMPLE_NDA_TEXT)

        pattern_names = {c.clause_desc for c in changes}
        assert "Reasonable Attorney's Fees" in pattern_names
        assert "Term Limitation - Perpetuity" in pattern_names

    def test_rules_changes_have_context(self):
        """All rules engine changes have non-empty context."""
        engine = RulesEngine()
        changes = engine.apply(SAMPLE_NDA_TEXT)

        for change in changes:
            assert change.before_context, f"Change {change.id} missing before_context"
            assert change.after_context, f"Change {change.id} missing after_context"
            assert change.document_position >= 0


class TestContextExtraction:
    def test_150_word_context(self):
        """Context extraction returns approximately 150 words before and after."""
        # Build a document with known word counts
        words_before = " ".join([f"word{i}" for i in range(200)])
        match_text = "THIS IS THE MATCH"
        words_after = " ".join([f"after{i}" for i in range(200)])
        doc = f"{words_before} {match_text} {words_after}"

        start = doc.index(match_text)
        end = start + len(match_text)
        ctx = extract_context(doc, start, end, word_count=150)

        before_word_count = len(ctx.before_text.split())
        after_word_count = len(ctx.after_text.split())

        # Should be approximately 150 words (may vary slightly due to boundaries)
        assert 145 <= before_word_count <= 155, f"Before: {before_word_count} words"
        assert 145 <= after_word_count <= 155, f"After: {after_word_count} words"
        assert ctx.match_text == match_text

    def test_short_document_context(self):
        """Context handles documents shorter than 150 words gracefully."""
        doc = "Short document with few words and a match here for testing."
        start = doc.index("match here")
        end = start + len("match here")
        ctx = extract_context(doc, start, end, word_count=150)

        assert ctx.match_text == "match here"
        assert len(ctx.before_text) > 0
        assert len(ctx.after_text) > 0


class TestTextUtilities:
    def test_locate_exact(self):
        """locate_text_in_document finds exact matches."""
        doc = "The quick brown fox jumps over the lazy dog."
        result = locate_text_in_document(doc, "brown fox jumps")
        assert result is not None
        assert result.confidence == 1.0
        assert result.method == "exact"
        assert doc[result.start:result.end] == "brown fox jumps"

    def test_locate_normalized(self):
        """locate_text_in_document finds normalized matches (extra whitespace)."""
        doc = "The  quick\tbrown  fox   jumps over the lazy dog."
        result = locate_text_in_document(doc, "quick brown fox jumps")
        assert result is not None
        assert result.confidence >= 0.9

    def test_locate_not_found(self):
        """locate_text_in_document returns None when text not present."""
        doc = "The quick brown fox jumps over the lazy dog."
        result = locate_text_in_document(doc, "completely unrelated text that is nowhere in document")
        assert result is None

    def test_clean_clause_html(self):
        """clean_clause_html strips tags and entities properly."""
        html = '<p>The Receiving Party&nbsp;shall <b>maintain</b> strict confidence.</p>'
        result = clean_clause_html(html)
        assert "Receiving Party" in result
        assert "maintain" in result
        assert "<p>" not in result
        assert "&nbsp;" not in result

    def test_clean_clause_html_placeholders(self):
        """clean_clause_html replaces template placeholders with ___."""
        html = 'This Agreement is made by [!@Party Name] and [*Date].'
        result = clean_clause_html(html)
        assert "___" in result
        assert "[!@" not in result
        assert "[*" not in result


class TestAuditTrail:
    def test_audit_captures_all_tiers(self):
        """Audit log records entries for each tier attempted."""
        audit = AuditLogger()
        audit.set_metadata("test-job", "NDA", "test.docx")
        engine = CascadeEngine(audit=audit)

        # Use a finding that will fail all tiers
        clause = ClauseRecord(
            id=1, form_type="NDA", category_id=1, prov_desc="Test",
            html_data_text="",
            clean_text="Specific clause text here",
            risk_level="high"
        )
        finding = AIFinding(
            id=1, clause_id=1,
            document_section="text not in document anywhere at all",
            issue="test",
            suggested_portion="completely different text not in clause",
            priority="high"
        )
        engine.resolve(finding, clause, "Unrelated document content.")

        # Check audit has entries
        tier_entries = [e for e in audit.entries if e["type"] == "tier_attempt"]
        tiers_logged = {e["tier"] for e in tier_entries}
        assert "tier1_exact" in tiers_logged
        assert "tier2_fuzzy" in tiers_logged
        assert "tier3_full_clause" in tiers_logged
        assert "tier4_human_review" in tiers_logged

    def test_audit_saves_to_json(self, tmp_path):
        """Audit logger saves valid JSON file."""
        audit = AuditLogger()
        audit.set_metadata("test-job", "NDA", "test.docx")
        audit.log_tier_attempt(1, "tier1_exact", "input", "pass", "found at offset 0")
        audit.log_resolution(1, "replacement text", 5, "exact")
        audit.log_ai_response('{"findings": []}')

        filepath = audit.save("test-job", str(tmp_path))
        assert os.path.exists(filepath)

        import json
        with open(filepath) as f:
            data = json.load(f)
        assert data["metadata"]["job_id"] == "test-job"
        assert data["metadata"]["form_type"] == "NDA"
        assert len(data["entries"]) == 2
        assert len(data["ai_responses"]) == 1


class TestNoAILanguageLeakage:
    """
    Critical test: Verify that NO AI-generated text can reach the final output.
    Every replacement must be traceable to the clause database.
    """

    def test_hallucinated_text_blocked_by_provenance(self):
        """Text not in any clause is blocked by provenance verification."""
        verifier = ProvenanceVerifier()
        clause = SAMPLE_CLAUSES[0]

        # Simulate AI sneaking in its own language
        change = ProposedChange(
            id=1, type="replace",
            find="some document text",
            replace="The parties hereby agree that all information shall be treated with the utmost confidentiality and any breach shall result in immediate termination",
            before_context="", after_context="",
            confidence="exact",  # Even if cascade says "exact"
            source="cascade_engine",
            clause_id=1, reasoning="test"
        )
        result = verifier.verify(change, clause)
        assert result.verified is False, "AI-generated text should NEVER pass provenance"

    def test_partial_clause_text_passes(self):
        """A genuine substring of clause text passes provenance."""
        verifier = ProvenanceVerifier()
        clause = SAMPLE_CLAUSES[0]

        change = ProposedChange(
            id=1, type="replace",
            find="some document text",
            replace="becomes publicly available without breach of this Agreement",
            before_context="", after_context="",
            confidence="exact",
            source="cascade_engine",
            clause_id=1, reasoning="test"
        )
        result = verifier.verify(change, clause)
        assert result.verified is True
