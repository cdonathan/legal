"""
Evaluation Module — AI boundary enforcement.
AI evaluates documents and references approved clauses by ID.
AI NEVER generates replacement legal language.
"""

import re
import json
import logging
from typing import Optional

from models import AIFinding, ClauseRecord
from text_utils import normalize_whitespace
import config

logger = logging.getLogger(__name__)


class EvaluationModule:
    """Constrains AI to evaluation-only output. Sends clauses by ID, receives references back."""

    def __init__(self, openai_client):
        self.client = openai_client
        self.model = config.OPENAI_MODEL
        self.batch_size = config.CLAUSE_BATCH_SIZE

    def evaluate(self, redacted_text: str, clauses: list[ClauseRecord], form_type: str) -> list[AIFinding]:
        """
        Send document + clause list to AI in batches.
        Returns list of AIFinding with clause references — no replacement text.
        """
        if not clauses:
            return []

        # Batch clauses into groups
        batches = [clauses[i:i + self.batch_size] for i in range(0, len(clauses), self.batch_size)]
        all_findings: list[AIFinding] = []

        for batch_num, batch in enumerate(batches, 1):
            logger.info(f"Evaluation batch {batch_num}/{len(batches)} ({len(batch)} clauses)")
            batch_findings = self._evaluate_batch(redacted_text, batch, form_type, batch_num, len(batches))
            all_findings.extend(batch_findings)

        # Reassign sequential IDs
        for i, f in enumerate(all_findings, 1):
            f.id = i

        return all_findings

    def validate_response(
        self,
        findings: list[AIFinding],
        document_text: str,
        clauses: list[ClauseRecord]
    ) -> list[AIFinding]:
        """
        Reject findings that fail boundary enforcement:
        1. document_section must exist verbatim in document_text
        2. suggested_portion must exist verbatim in the referenced clause text
        """
        valid = []
        doc_normalized = normalize_whitespace(document_text)

        for finding in findings:
            # Check document_section exists in document
            doc_section_norm = normalize_whitespace(finding.document_section)
            if doc_section_norm not in doc_normalized and finding.document_section not in document_text:
                logger.warning(
                    f"Finding {finding.id}: document_section not found in document — REJECTED"
                )
                continue

            # Check suggested_portion exists in referenced clause
            if finding.clause_id < 1 or finding.clause_id > len(clauses):
                logger.warning(
                    f"Finding {finding.id}: clause_id {finding.clause_id} out of range — REJECTED"
                )
                continue

            clause = clauses[finding.clause_id - 1]
            clause_text_norm = normalize_whitespace(clause.clean_text)
            suggested_norm = normalize_whitespace(finding.suggested_portion)

            if suggested_norm not in clause_text_norm and finding.suggested_portion not in clause.clean_text:
                logger.warning(
                    f"Finding {finding.id}: suggested_portion not found in clause {finding.clause_id} — REJECTED"
                )
                continue

            valid.append(finding)

        logger.info(f"Boundary enforcement: {len(valid)}/{len(findings)} findings passed")
        return valid

    def _evaluate_batch(
        self,
        document_text: str,
        batch: list[ClauseRecord],
        form_type: str,
        batch_num: int,
        total_batches: int
    ) -> list[AIFinding]:
        """Evaluate a single batch of clauses against the document."""
        prompt = self._build_prompt(document_text, batch, form_type, batch_num, total_batches)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=16000,
                temperature=config.OPENAI_TEMPERATURE,
            )
            content = response.choices[0].message.content
            return self._parse_response(content)
        except Exception as e:
            logger.error(f"AI evaluation batch {batch_num} failed: {e}")
            return []

    def _build_prompt(
        self,
        document_text: str,
        batch: list[ClauseRecord],
        form_type: str,
        batch_num: int,
        total_batches: int
    ) -> str:
        """
        Build evaluation prompt that constrains AI to references only.
        AI receives clause IDs + text. Must return clause_id and verbatim quotes only.
        """
        # Build clause list
        clauses_section = f"\n\nAPPROVED CLAUSES (Batch {batch_num} of {total_batches}):\n"
        for clause in batch:
            clauses_section += f"\n[CLAUSE {clause.id}] {clause.prov_desc} (Risk: {clause.risk_level})\n"
            clauses_section += f"{clause.clean_text}\n"

        prompt = f"""You are reviewing a {form_type} document on behalf of the BUYER/RECIPIENT.

YOUR TASK: Compare the document against EACH Approved Clause below. For each clause where the document falls short, report the deficiency.

CRITICAL RULES:
1. You are an EVALUATOR only. You identify gaps — you do NOT write replacement language.
2. "document_section" MUST be an EXACT verbatim quote (30-150 chars) from the BODY TEXT of the document below — NOT from the table of contents, headers, page numbers, section indexes, or signature blocks.
3. "suggested_portion" MUST be an EXACT verbatim quote from the CLAUSE TEXT above that addresses the gap. Copy it character-for-character from the clause. Quote ONLY the minimal necessary portion — the fewest words that fix the deficiency. Do NOT quote the entire clause. If the fix is adding 5 words, quote only those 5 words from the clause. If the fix requires a full sentence, quote only that sentence — not the paragraph around it.
4. Do NOT paraphrase, summarize, or compose any legal language. Only quote existing text.
5. Be AGGRESSIVE: if the document's language is weaker, vaguer, or less protective than the Approved Clause, FLAG IT. The document must use language at least as strong as the approved provisions. "Close enough" is not acceptable — the approved clause language exists for a reason.
6. If a topic is covered but with materially different or weaker wording than the Approved Clause, flag it and provide the approved language as the suggested_portion.
7. Do NOT flag only formatting differences or clause numbering.
8. If a protection is entirely ABSENT from the document, quote the nearest relevant section IN THE BODY where it should be added.
9. Evaluate EVERY clause in this batch — do not skip clauses. If the clause is not relevant to this document type, return it with priority "low".
10. NEVER quote from tables of contents, section indexes, headers, footers, or page number listings. Only quote from the substantive body paragraphs where the actual legal language lives. If a section is referenced in the TOC, find the actual body text of that section and quote from there.

{clauses_section}

Return ONLY a JSON array (no markdown fencing):
[
  {{
    "id": 1,
    "clause_id": N,
    "document_section": "exact verbatim quote from document 30-150 chars",
    "issue": "what is missing or deficient (1 sentence)",
    "suggested_portion": "exact verbatim quote from the clause text that addresses this gap",
    "priority": "high|medium|low"
  }}
]

If no deficiencies are found for this batch, return an empty array: []

DOCUMENT TEXT:
{document_text}"""

        return prompt

    def _parse_response(self, content: str) -> list[AIFinding]:
        """Parse AI JSON response into AIFinding list. Handles truncated responses."""
        if not content:
            return []

        # Strip markdown fencing if present
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*", "", content)
        content = content.strip()

        # Try to parse as complete JSON array
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                items = json.loads(content[start:end])
                return [self._item_to_finding(item) for item in items if self._is_valid_item(item)]
            except json.JSONDecodeError:
                pass

        # Truncated response — recover complete JSON objects
        if start >= 0:
            return self._recover_truncated(content[start:])

        return []

    def _recover_truncated(self, fragment: str) -> list[AIFinding]:
        """Recover complete JSON objects from a truncated response."""
        results = []
        i = 1
        while i < len(fragment):
            if fragment[i] == '{':
                depth = 0
                in_string = False
                escape_next = False
                for j in range(i, len(fragment)):
                    ch = fragment[j]
                    if escape_next:
                        escape_next = False
                        continue
                    if ch == '\\' and in_string:
                        escape_next = True
                        continue
                    if ch == '"' and not escape_next:
                        in_string = not in_string
                    if not in_string:
                        if ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth == 0:
                                try:
                                    obj = json.loads(fragment[i:j + 1])
                                    if self._is_valid_item(obj):
                                        results.append(self._item_to_finding(obj))
                                except json.JSONDecodeError:
                                    pass
                                i = j + 1
                                break
                else:
                    break
            i += 1
        return results

    def _is_valid_item(self, item: dict) -> bool:
        """Check if a parsed item has required fields."""
        return (
            isinstance(item, dict) and
            "clause_id" in item and
            "document_section" in item and
            "suggested_portion" in item
        )

    def _item_to_finding(self, item: dict) -> AIFinding:
        """Convert a parsed dict to an AIFinding dataclass."""
        return AIFinding(
            id=item.get("id", 0),
            clause_id=item.get("clause_id", 0),
            document_section=item.get("document_section", ""),
            issue=item.get("issue", ""),
            suggested_portion=item.get("suggested_portion", ""),
            priority=item.get("priority", "medium"),
        )
