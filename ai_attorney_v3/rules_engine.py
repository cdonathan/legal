"""
Deterministic rules engine — exact-match pattern replacements.
Runs before AI evaluation. No AI involved. No cascade needed.
These are hardcoded corrections that are always correct.
"""

import re
from dataclasses import dataclass
from typing import Optional

from models import ProposedChange
from context_extractor import extract_context
import config


@dataclass
class Rule:
    """A single deterministic replacement rule."""
    name: str
    pattern: str          # Regex pattern to find
    replacement: str      # Exact replacement text
    reasoning: str        # Why this change is needed
    priority: str = "high"


# Minimum rule set — these are always correct, attorney-approved replacements
RULES: list[Rule] = [
    Rule(
        name="Reasonable Attorney's Fees",
        pattern=r"(?i)(?<!reasonable\s)attorney'?s?'?\s+fees",
        replacement="reasonable attorney's fees",
        reasoning="Attorney's fees should be qualified as 'reasonable' to limit exposure",
        priority="high",
    ),
    Rule(
        name="Commercially Reasonable Efforts",
        pattern=r"(?i)\bbest\s+efforts\b",
        replacement="commercially reasonable efforts",
        reasoning="'Best efforts' is onerous; 'commercially reasonable efforts' is market standard",
        priority="high",
    ),
    Rule(
        name="Commercially Reasonable Steps",
        pattern=r"(?i)\btake\s+all\s+steps\b",
        replacement="take commercially reasonable steps",
        reasoning="'All steps' is an absolute obligation; qualify with commercially reasonable",
        priority="high",
    ),
    Rule(
        name="Term Limitation - Perpetuity",
        pattern=r"(?i)\bin\s+perpetuity\b",
        replacement="for a period of two (2) years from the Effective Date",
        reasoning="Perpetual obligations are unreasonable; standard NDA term is 2-3 years",
        priority="high",
    ),
    Rule(
        name="Execution Flexibility",
        pattern=r"(?i)\boriginal\s+signature(?:s)?\s+only\b",
        replacement="original or electronic signatures",
        reasoning="Allow electronic execution for practical convenience",
        priority="low",
    ),
    Rule(
        name="Expanded Disclosure Recipients",
        pattern=r"(?i)directors,?\s+officers,?\s+employees,?\s+and\s+agents\b",
        replacement="directors, officers, employees, agents, partners, clients, legal counsel, investors, members, managers, and advisors",
        reasoning="Disclosure recipients should include all parties who may need access for legitimate business purposes",
        priority="high",
    ),
]


class RulesEngine:
    """Deterministic pattern-matching replacements — no AI, no cascade."""

    def __init__(self, additional_rules: Optional[list[Rule]] = None):
        self.rules = list(RULES)
        if additional_rules:
            self.rules.extend(additional_rules)

    def apply(self, document_text: str) -> list[ProposedChange]:
        """
        Apply all rules against document text.
        Returns list of ProposedChange with source="rules_engine" and 150-word context.
        """
        changes = []
        change_id = 1000  # Rules engine IDs start at 1000 to avoid collision with cascade

        for rule in self.rules:
            compiled = re.compile(rule.pattern)
            for match in compiled.finditer(document_text):
                found_text = match.group(0)

                # Skip if already has the replacement (avoid double-applying)
                if self._already_applied(rule, found_text, document_text, match.start()):
                    continue

                # Extract 150-word context
                ctx = extract_context(
                    document_text,
                    match.start(),
                    match.end(),
                    word_count=config.CONTEXT_WORD_COUNT
                )

                changes.append(ProposedChange(
                    id=change_id,
                    type="replace",
                    find=found_text,
                    replace=rule.replacement,
                    before_context=ctx.before_text,
                    after_context=ctx.after_text,
                    confidence="exact",  # Rules are always exact
                    source="rules_engine",
                    clause_id=None,
                    clause_desc=rule.name,
                    reasoning=rule.reasoning,
                    priority=rule.priority,
                    document_position=match.start(),
                    similarity_score=None,
                ))
                change_id += 1

        return changes

    def _already_applied(self, rule: Rule, found_text: str, document_text: str, match_start: int) -> bool:
        """Check if the replacement is already present (avoid adding 'reasonable' twice, etc.)."""
        # For "reasonable attorney's fees" rule — check if "reasonable" already precedes
        if "reasonable" in rule.replacement.lower() and "reasonable" not in found_text.lower():
            # Look back 15 chars for "reasonable"
            lookback = document_text[max(0, match_start - 15):match_start].lower()
            if "reasonable" in lookback:
                return True

        # For expanded recipients — check if expanded terms already present nearby
        if "investors" in rule.replacement.lower():
            context = document_text[match_start:match_start + 200].lower()
            if "investors" in context or "members" in context:
                return True

        return False
