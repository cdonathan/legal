"""
Tests for the Rules Engine — deterministic pattern matching.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from rules_engine import RulesEngine


@pytest.fixture
def engine():
    return RulesEngine()


class TestReasonableAttorneysFees:
    def test_finds_attorneys_fees(self, engine):
        """Detects 'attorney's fees' and adds 'reasonable'."""
        text = "The breaching party shall pay all attorney's fees incurred by the non-breaching party."
        changes = engine.apply(text)
        assert len(changes) == 1
        assert changes[0].find == "attorney's fees"
        assert changes[0].replace == "reasonable attorney's fees"
        assert changes[0].source == "rules_engine"

    def test_skips_already_reasonable(self, engine):
        """Does not flag 'reasonable attorney's fees'."""
        text = "The breaching party shall pay reasonable attorney's fees."
        changes = engine.apply(text)
        assert len(changes) == 0

    def test_finds_attorneys_plural(self, engine):
        """Handles 'attorneys' fees' (plural possessive)."""
        text = "Including all attorneys' fees and costs of litigation."
        changes = engine.apply(text)
        assert len(changes) == 1
        assert "reasonable" in changes[0].replace

    def test_finds_attorneys_no_apostrophe(self, engine):
        """Handles 'attorneys fees' without apostrophe."""
        text = "All attorneys fees shall be borne by the losing party."
        changes = engine.apply(text)
        assert len(changes) == 1


class TestCommerciallyReasonableEfforts:
    def test_finds_best_efforts(self, engine):
        """Detects 'best efforts' and replaces."""
        text = "The Receiving Party shall use best efforts to protect the information."
        changes = engine.apply(text)
        assert len(changes) == 1
        assert changes[0].find == "best efforts"
        assert changes[0].replace == "commercially reasonable efforts"

    def test_case_insensitive(self, engine):
        """Matches regardless of case."""
        text = "Each party shall use Best Efforts to comply with the terms."
        changes = engine.apply(text)
        assert len(changes) == 1

    def test_no_false_positive_reasonable_efforts(self, engine):
        """Does not match 'commercially reasonable efforts'."""
        text = "The party shall use commercially reasonable efforts."
        changes = engine.apply(text)
        # Should not match "best efforts" anywhere
        best_efforts_changes = [c for c in changes if "best efforts" in c.find.lower()]
        assert len(best_efforts_changes) == 0


class TestCommerciallyReasonableSteps:
    def test_finds_take_all_steps(self, engine):
        """Detects 'take all steps' and replaces."""
        text = "Recipient shall take all steps necessary to prevent disclosure."
        changes = engine.apply(text)
        matching = [c for c in changes if "take all steps" in c.find.lower()]
        assert len(matching) == 1
        assert matching[0].replace == "take commercially reasonable steps"


class TestTermLimitation:
    def test_finds_in_perpetuity(self, engine):
        """Detects 'in perpetuity' and replaces with 2-year term."""
        text = "This obligation shall survive in perpetuity."
        changes = engine.apply(text)
        matching = [c for c in changes if "perpetuity" in c.find.lower()]
        assert len(matching) == 1
        assert "two (2) years" in matching[0].replace


class TestExecutionFlexibility:
    def test_finds_original_signatures_only(self, engine):
        """Detects 'original signatures only'."""
        text = "This agreement requires original signatures only for execution."
        changes = engine.apply(text)
        matching = [c for c in changes if "original" in c.find.lower() and "signature" in c.find.lower()]
        assert len(matching) == 1
        assert "electronic" in matching[0].replace


class TestExpandedRecipients:
    def test_finds_narrow_list(self, engine):
        """Detects narrow 'directors, officers, employees, and agents' list."""
        text = "Information may be shared with directors, officers, employees, and agents of the Receiving Party."
        changes = engine.apply(text)
        matching = [c for c in changes if "directors" in c.find.lower()]
        assert len(matching) == 1
        assert "investors" in matching[0].replace
        assert "members" in matching[0].replace
        assert "partners" in matching[0].replace

    def test_skips_when_already_expanded(self, engine):
        """Does not flag when investors/members already present nearby."""
        text = "Disclosed to directors, officers, employees, and agents as well as investors and members."
        changes = engine.apply(text)
        matching = [c for c in changes if "directors" in c.find.lower()]
        assert len(matching) == 0


class TestContextExtraction:
    def test_changes_have_context(self, engine):
        """Every change includes before and after context."""
        text = " ".join(["word"] * 200) + " attorney's fees " + " ".join(["word"] * 200)
        changes = engine.apply(text)
        assert len(changes) == 1
        assert len(changes[0].before_context) > 0
        assert len(changes[0].after_context) > 0

    def test_changes_have_document_position(self, engine):
        """Every change has a document_position set."""
        text = "The party shall pay attorney's fees."
        changes = engine.apply(text)
        assert len(changes) == 1
        assert changes[0].document_position >= 0


class TestMultipleMatches:
    def test_multiple_patterns_in_one_doc(self, engine):
        """Multiple different patterns can fire on the same document."""
        text = "The party shall use best efforts and take all steps to protect information. All attorney's fees shall be paid in perpetuity."
        changes = engine.apply(text)
        patterns_found = {c.clause_desc for c in changes}
        assert "Commercially Reasonable Efforts" in patterns_found
        assert "Commercially Reasonable Steps" in patterns_found
        assert "Reasonable Attorney's Fees" in patterns_found
        assert "Term Limitation - Perpetuity" in patterns_found

    def test_same_pattern_multiple_occurrences(self, engine):
        """Same pattern matching multiple times in a document."""
        text = "Pay attorney's fees. Also, all attorney's fees for appeals."
        changes = engine.apply(text)
        fees_changes = [c for c in changes if "attorney" in c.find.lower()]
        assert len(fees_changes) == 2
