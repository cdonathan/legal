#!/usr/bin/env python3
"""
Integration test runner — processes a real NDA through the full pipeline.
Uses local provisions.db (no SQL Server needed).
Requires OpenAI API key in openai_api_key.txt.

Usage:
    python3 run_integration_test.py /path/to/nda.docx [form_type]
    python3 run_integration_test.py  # Uses built-in sample text
"""

import os
import sys
import json
import time
from datetime import datetime

# Ensure we can import from the project
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from models import ProposedChange
from evaluation_module import EvaluationModule
from cascade_engine import CascadeEngine
from provenance_verifier import ProvenanceVerifier
from rules_engine import RulesEngine
from clause_repository import ClauseRepository
from document_processor import DocumentProcessor
from redaction import apply_hex_redaction
from context_extractor import extract_context
from audit_logger import AuditLogger
from text_utils import locate_text_in_document

# Built-in sample NDA for testing without a file
SAMPLE_NDA = """CONFIDENTIALITY AND NON-DISCLOSURE AGREEMENT

This Agreement is entered into as of _______ by and between Greenfield Properties LLC ("Disclosing Party") and the undersigned ("Receiving Party").

1. CONFIDENTIAL INFORMATION. The Disclosing Party may disclose certain confidential and proprietary information relating to its business operations and a potential real estate transaction to the Receiving Party. The Receiving Party agrees to hold all such information in strict confidence and shall take all steps necessary to prevent unauthorized disclosure.

2. USE RESTRICTIONS. The Receiving Party shall use the Confidential Information solely for the purpose of evaluating the potential transaction. The Receiving Party shall not disclose the information to anyone other than its employees and legal counsel who have a need to know.

3. RETURN OF MATERIALS. Upon termination of this Agreement, the Receiving Party shall immediately return all materials containing Confidential Information to the Disclosing Party.

4. NON-CIRCUMVENTION. The Receiving Party shall not directly or indirectly contact any third party introduced by the Disclosing Party without prior written consent.

5. REMEDIES. The Receiving Party acknowledges that any breach of this Agreement may cause irreparable harm to the Disclosing Party. The Disclosing Party shall be entitled to seek injunctive relief and the Receiving Party shall pay all attorney's fees and costs incurred in enforcing this Agreement.

6. TERM. The obligations under this Agreement shall survive in perpetuity.

7. MISCELLANEOUS. This Agreement may be executed in counterparts. Facsimile signatures shall be deemed valid and binding. This Agreement constitutes the entire agreement between the parties.
"""


def main():
    start_time = time.time()
    print("=" * 70)
    print("AI Attorney v3 — Integration Test")
    print("=" * 70)

    # Determine input
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        form_type = sys.argv[2] if len(sys.argv) > 2 else "NDA"
        print(f"\n📄 Input: {input_path}")
        print(f"📋 Type: {form_type}")
        processor = DocumentProcessor()
        text = processor.extract_text(input_path)
    else:
        form_type = "NDA"
        text = SAMPLE_NDA
        print(f"\n📄 Input: Built-in sample NDA")
        print(f"📋 Type: {form_type}")

    print(f"📊 Word count: {len(text.split())}")

    # Step 1: PII Redaction
    print(f"\n[Step 1] PII Redaction...")
    redacted_text, pii_mapping = apply_hex_redaction(text)
    print(f"   ✓ Redacted {len(pii_mapping)} PII items")
    for original, label in list(pii_mapping.items())[:5]:
        print(f"     {label}: {original[:30]}...")

    # Step 2: Fetch clauses
    print(f"\n[Step 2] Fetching clauses...")
    repo = ClauseRepository()
    clauses = repo.get_clauses_by_form_type(form_type)
    print(f"   ✓ {len(clauses)} clauses loaded ({repo.get_connection_mode()})")
    if not clauses:
        print("   ❌ No clauses found! Check provisions.db")
        return

    # Step 3: Rules Engine
    print(f"\n[Step 3] Rules Engine (deterministic)...")
    rules = RulesEngine()
    rules_changes = rules.apply(redacted_text)
    print(f"   ✓ {len(rules_changes)} deterministic changes found")
    for rc in rules_changes:
        print(f"     • {rc.clause_desc}: '{rc.find}' → '{rc.replace[:50]}...'")

    # Step 4: AI Evaluation
    print(f"\n[Step 4] AI Evaluation...")
    api_key = config.get_openai_api_key()
    if not api_key:
        print("   ❌ No OpenAI API key found. Skipping AI evaluation.")
        print("   (Place key in openai_api_key.txt)")
        print("\n   Running with rules engine only...\n")
        all_changes = rules_changes
    else:
        import openai
        client = openai.OpenAI(api_key=api_key)
        evaluator = EvaluationModule(client)

        print(f"   🔄 Sending to GPT-4o ({len(clauses)} clauses in {(len(clauses)-1)//25 + 1} batch(es))...")
        findings = evaluator.evaluate(redacted_text, clauses, form_type)
        print(f"   ✓ AI returned {len(findings)} findings")

        # Step 5: Boundary Enforcement
        print(f"\n[Step 5] Boundary Enforcement...")
        valid_findings = evaluator.validate_response(findings, redacted_text, clauses)
        rejected = len(findings) - len(valid_findings)
        print(f"   ✓ {len(valid_findings)} passed, {rejected} rejected")

        # Step 6: Cascade Resolution
        print(f"\n[Step 6] Cascade Resolution...")
        audit = AuditLogger()
        audit.set_metadata("integration-test", form_type, "sample_nda")
        cascade = CascadeEngine(audit=audit)

        cascade_changes: list[ProposedChange] = []
        change_id = 1

        for finding in valid_findings:
            clause = repo.get_clause_by_id(finding.clause_id, form_type, clauses)
            if not clause:
                print(f"   ⚠ Clause {finding.clause_id} not found, skipping")
                continue

            result = cascade.resolve(finding, clause, redacted_text)
            print(f"   • Finding {finding.id} ({clause.prov_desc[:40]}): {result.confidence}"
                  f"{f' ({result.similarity_score:.2f})' if result.similarity_score else ''}")

            if result.confidence == "manual":
                change = ProposedChange(
                    id=change_id, type="replace",
                    find=finding.document_section, replace="",
                    before_context="", after_context="",
                    confidence="manual", source="cascade_engine",
                    clause_id=clause.id, clause_desc=clause.prov_desc,
                    reasoning=finding.issue, priority=finding.priority,
                    full_clause_text=result.full_clause_text,
                )
            else:
                change = ProposedChange(
                    id=change_id, type="replace",
                    find=finding.document_section,
                    replace=result.replacement_text or "",
                    before_context="", after_context="",
                    confidence=result.confidence, source="cascade_engine",
                    clause_id=clause.id, clause_desc=clause.prov_desc,
                    reasoning=finding.issue, priority=finding.priority,
                    similarity_score=result.similarity_score,
                )
            cascade_changes.append(change)
            change_id += 1

        # Step 7: Provenance Verification
        print(f"\n[Step 7] Provenance Verification...")
        verifier = ProvenanceVerifier()
        verified = verifier.verify_all(cascade_changes, clauses)
        manual_count = sum(1 for c in verified if c.confidence == "manual")
        print(f"   ✓ {len(verified)} changes verified ({manual_count} flagged for human review)")

        # Add context
        for change in verified:
            location = locate_text_in_document(redacted_text, change.find)
            if location:
                change.document_position = location.start
                ctx = extract_context(redacted_text, location.start, location.end, config.CONTEXT_WORD_COUNT)
                change.before_context = ctx.before_text
                change.after_context = ctx.after_text

        # Combine with rules
        all_changes = list(rules_changes) + [c for c in verified if c.find.lower() not in {rc.find.lower() for rc in rules_changes}]

        # Save audit
        audit.save("integration-test", config.JOBS_DIR)
        print(f"   ✓ Audit saved to {config.JOBS_DIR}/integration-test_audit.json")

    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'=' * 70}")
    print(f"✅ INTEGRATION TEST COMPLETE — {elapsed:.1f}s")
    print(f"{'=' * 70}")
    print(f"\n📊 Results:")
    print(f"   Total proposed changes: {len(all_changes)}")

    # Tier distribution
    tiers = {}
    for c in all_changes:
        key = f"{c.source}/{c.confidence}"
        tiers[key] = tiers.get(key, 0) + 1
    for tier, count in sorted(tiers.items()):
        print(f"   • {tier}: {count}")

    # Show each change
    print(f"\n📋 Proposed Changes:")
    for i, change in enumerate(all_changes, 1):
        badge = "🟢" if change.confidence == "exact" else "🟡" if change.confidence == "fuzzy" else "🟠" if change.confidence == "full_clause" else "🔴"
        print(f"\n   {badge} Change {i}: [{change.confidence}] {change.clause_desc or change.source}")
        print(f"      Find:    '{change.find[:80]}{'...' if len(change.find) > 80 else ''}'")
        if change.replace:
            print(f"      Replace: '{change.replace[:80]}{'...' if len(change.replace) > 80 else ''}'")
        else:
            print(f"      Replace: [MANUAL REVIEW REQUIRED]")
        print(f"      Reason:  {change.reasoning[:80]}")
        if change.before_context:
            print(f"      Context: ...{change.before_context[-50:]} [CHANGE] {change.after_context[:50]}...")

    # Provenance check
    print(f"\n🔒 Provenance Check:")
    all_verified = True
    for change in all_changes:
        if change.source == "rules_engine":
            continue
        if change.confidence == "manual":
            continue
        if change.replace and change.clause_id:
            clause = repo.get_clause_by_id(change.clause_id, form_type, clauses)
            if clause and change.replace not in clause.clean_text:
                print(f"   ❌ Change {change.id}: PROVENANCE FAILED — text not in clause {change.clause_id}")
                all_verified = False

    if all_verified:
        print(f"   ✓ All replacement text verified as clause-sourced")
    else:
        print(f"   ❌ PROVENANCE FAILURES DETECTED — review required")

    # Apply to DOCX if input was a file
    if len(sys.argv) > 1 and sys.argv[1].endswith('.docx'):
        applicable = [c for c in all_changes if c.confidence != "manual" and c.replace]
        if applicable:
            print(f"\n📝 Applying {len(applicable)} changes to document...")
            output_dir = os.path.join(config.JOBS_DIR, "integration-test")
            os.makedirs(output_dir, exist_ok=True)

            base = os.path.splitext(os.path.basename(sys.argv[1]))[0]
            redline_path = os.path.join(output_dir, f"{base}_redline.docx")
            clean_path = os.path.join(output_dir, f"{base}_clean.docx")

            processor = DocumentProcessor()
            processor.apply_changes(sys.argv[1], applicable, redline_path, redline=True)
            processor.apply_changes(sys.argv[1], applicable, clean_path, redline=False)

            print(f"   ✓ Redline: {redline_path}")
            print(f"   ✓ Clean:   {clean_path}")


if __name__ == "__main__":
    main()
