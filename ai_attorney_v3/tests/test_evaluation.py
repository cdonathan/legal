"""
Tests for the Evaluation Module — AI boundary enforcement.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models import AIFinding, ClauseRecord
from evaluation_module import EvaluationModule


@pytest.fixture
def sample_clauses():
    return [
        ClauseRecord(
            id=1, form_type="NDA", category_id=1,
            prov_desc="Confidentiality Exceptions",
            html_data_text="",
            clean_text="Confidential Information does not include information that becomes publicly available without breach of this Agreement or was previously known by the Receiving Party.",
            risk_level="high"
        ),
        ClauseRecord(
            id=2, form_type="NDA", category_id=2,
            prov_desc="Permitted Recipients",
            html_data_text="",
            clean_text="The Receiving Party may disclose to its directors, officers, employees, affiliates, attorneys, accountants, financial advisors, consultants, lenders, and investors.",
            risk_level="high"
        ),
        ClauseRecord(
            id=3, form_type="NDA", category_id=3,
            prov_desc="Term of Agreement",
            html_data_text="",
            clean_text="This Agreement shall remain in effect for one (1) year from the Effective Date.",
            risk_level="medium"
        ),
    ]


@pytest.fixture
def sample_document():
    return "This Confidentiality Agreement is entered into between the parties. The Recipient agrees to keep all information strictly confidential and shall not disclose to anyone. This agreement shall survive indefinitely."


class TestBoundaryEnforcement:
    def test_valid_finding_passes(self, sample_clauses, sample_document):
        """Finding with valid document_section and suggested_portion passes."""
        evaluator = EvaluationModule(openai_client=None)
        findings = [
            AIFinding(
                id=1, clause_id=1,
                document_section="The Recipient agrees to keep all information strictly confidential",
                issue="No carve-outs for public information",
                suggested_portion="Confidential Information does not include information that becomes publicly available without breach of this Agreement",
                priority="high"
            )
        ]
        valid = evaluator.validate_response(findings, sample_document, sample_clauses)
        assert len(valid) == 1

    def test_invalid_document_section_rejected(self, sample_clauses, sample_document):
        """Finding with document_section NOT in document is rejected."""
        evaluator = EvaluationModule(openai_client=None)
        findings = [
            AIFinding(
                id=1, clause_id=1,
                document_section="This text does not exist in the document at all",
                issue="test",
                suggested_portion="Confidential Information does not include",
                priority="high"
            )
        ]
        valid = evaluator.validate_response(findings, sample_document, sample_clauses)
        assert len(valid) == 0

    def test_invalid_suggested_portion_rejected(self, sample_clauses, sample_document):
        """Finding with suggested_portion NOT in clause is rejected."""
        evaluator = EvaluationModule(openai_client=None)
        findings = [
            AIFinding(
                id=1, clause_id=1,
                document_section="The Recipient agrees to keep all information strictly confidential",
                issue="test",
                suggested_portion="AI made up this legal language that is not in the clause database",
                priority="high"
            )
        ]
        valid = evaluator.validate_response(findings, sample_document, sample_clauses)
        assert len(valid) == 0

    def test_out_of_range_clause_id_rejected(self, sample_clauses, sample_document):
        """Finding with clause_id outside valid range is rejected."""
        evaluator = EvaluationModule(openai_client=None)
        findings = [
            AIFinding(
                id=1, clause_id=99,  # Only 3 clauses exist
                document_section="The Recipient agrees to keep all information strictly confidential",
                issue="test",
                suggested_portion="some text",
                priority="high"
            )
        ]
        valid = evaluator.validate_response(findings, sample_document, sample_clauses)
        assert len(valid) == 0

    def test_zero_clause_id_rejected(self, sample_clauses, sample_document):
        """Finding with clause_id=0 is rejected."""
        evaluator = EvaluationModule(openai_client=None)
        findings = [
            AIFinding(
                id=1, clause_id=0,
                document_section="The Recipient agrees to keep all information",
                issue="test",
                suggested_portion="some text",
                priority="high"
            )
        ]
        valid = evaluator.validate_response(findings, sample_document, sample_clauses)
        assert len(valid) == 0

    def test_normalized_whitespace_match_passes(self, sample_clauses, sample_document):
        """Finding passes when document_section matches after whitespace normalization."""
        evaluator = EvaluationModule(openai_client=None)
        findings = [
            AIFinding(
                id=1, clause_id=3,
                document_section="This agreement  shall survive  indefinitely",  # Extra spaces
                issue="No term limit",
                suggested_portion="This Agreement shall remain in effect for one (1) year from the Effective Date.",
                priority="high"
            )
        ]
        valid = evaluator.validate_response(findings, sample_document, sample_clauses)
        assert len(valid) == 1

    def test_multiple_findings_partial_rejection(self, sample_clauses, sample_document):
        """Some findings pass, some rejected — partial results returned."""
        evaluator = EvaluationModule(openai_client=None)
        findings = [
            AIFinding(
                id=1, clause_id=1,
                document_section="The Recipient agrees to keep all information strictly confidential",
                issue="No carve-outs",
                suggested_portion="Confidential Information does not include information that becomes publicly available",
                priority="high"
            ),
            AIFinding(
                id=2, clause_id=2,
                document_section="NOT IN THE DOCUMENT AT ALL",
                issue="test",
                suggested_portion="directors, officers",
                priority="medium"
            ),
            AIFinding(
                id=3, clause_id=3,
                document_section="This agreement shall survive indefinitely",
                issue="No term",
                suggested_portion="This Agreement shall remain in effect for one (1) year",
                priority="high"
            ),
        ]
        valid = evaluator.validate_response(findings, sample_document, sample_clauses)
        assert len(valid) == 2  # Finding 2 rejected
        assert valid[0].id == 1
        assert valid[1].id == 3


class TestResponseParsing:
    def test_parse_valid_json(self):
        """Parses a clean JSON array."""
        evaluator = EvaluationModule(openai_client=None)
        content = '[{"id": 1, "clause_id": 5, "document_section": "some text", "issue": "missing", "suggested_portion": "clause text", "priority": "high"}]'
        findings = evaluator._parse_response(content)
        assert len(findings) == 1
        assert findings[0].clause_id == 5
        assert findings[0].document_section == "some text"

    def test_parse_json_with_markdown_fencing(self):
        """Strips markdown code fencing before parsing."""
        evaluator = EvaluationModule(openai_client=None)
        content = '```json\n[{"id": 1, "clause_id": 3, "document_section": "text", "issue": "gap", "suggested_portion": "clause", "priority": "low"}]\n```'
        findings = evaluator._parse_response(content)
        assert len(findings) == 1

    def test_parse_empty_array(self):
        """Empty array returns empty list."""
        evaluator = EvaluationModule(openai_client=None)
        content = '[]'
        findings = evaluator._parse_response(content)
        assert len(findings) == 0

    def test_parse_truncated_response(self):
        """Recovers complete objects from a truncated response."""
        evaluator = EvaluationModule(openai_client=None)
        content = '[{"id": 1, "clause_id": 2, "document_section": "text here", "issue": "problem", "suggested_portion": "fix", "priority": "high"}, {"id": 2, "clause_id": 3, "document_sec'
        findings = evaluator._parse_response(content)
        assert len(findings) == 1  # First object recovered, second truncated

    def test_parse_invalid_items_skipped(self):
        """Items missing required fields are skipped."""
        evaluator = EvaluationModule(openai_client=None)
        content = '[{"id": 1, "clause_id": 2, "document_section": "text", "issue": "ok", "suggested_portion": "clause", "priority": "high"}, {"id": 2, "only_this": "field"}]'
        findings = evaluator._parse_response(content)
        assert len(findings) == 1

    def test_parse_empty_string(self):
        """Empty string returns empty list."""
        evaluator = EvaluationModule(openai_client=None)
        findings = evaluator._parse_response("")
        assert len(findings) == 0

    def test_parse_none(self):
        """None input returns empty list."""
        evaluator = EvaluationModule(openai_client=None)
        findings = evaluator._parse_response(None)
        assert len(findings) == 0


class TestPromptConstruction:
    def test_prompt_contains_clause_ids(self, sample_clauses):
        """Prompt includes clause IDs for reference."""
        evaluator = EvaluationModule(openai_client=None)
        prompt = evaluator._build_prompt("Document text here.", sample_clauses, "NDA", 1, 1)
        assert "[CLAUSE 1]" in prompt
        assert "[CLAUSE 2]" in prompt
        assert "[CLAUSE 3]" in prompt

    def test_prompt_contains_clause_text(self, sample_clauses):
        """Prompt includes actual clause text for AI to reference."""
        evaluator = EvaluationModule(openai_client=None)
        prompt = evaluator._build_prompt("Document text here.", sample_clauses, "NDA", 1, 1)
        assert "Confidential Information does not include" in prompt
        assert "directors, officers, employees" in prompt

    def test_prompt_contains_document_text(self, sample_clauses):
        """Prompt includes the document text at the end."""
        evaluator = EvaluationModule(openai_client=None)
        doc = "This is the actual NDA document text for analysis."
        prompt = evaluator._build_prompt(doc, sample_clauses, "NDA", 1, 1)
        assert doc in prompt

    def test_prompt_instructs_no_legal_language(self, sample_clauses):
        """Prompt explicitly forbids AI from writing replacement language."""
        evaluator = EvaluationModule(openai_client=None)
        prompt = evaluator._build_prompt("Doc text.", sample_clauses, "NDA", 1, 1)
        assert "EVALUATOR only" in prompt or "do NOT write replacement" in prompt.lower() or "Do NOT paraphrase" in prompt
