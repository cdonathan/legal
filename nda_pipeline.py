#!/usr/bin/env python3
"""
Smart Attorney NDA Redlining System v3
Main pipeline: PII redaction → AI analysis → dual scoring → rules engine → surgical edits
"""

import os
import sys
import json
import shutil
import subprocess
from datetime import datetime

from nda_core import ConfigLoader, PIIRedactor
from nda_analyzer import AIAnalyzer, CodeScorer, resolve_scores, apply_thresholds
from nda_rules import RulesEngine
from nda_editor import DocumentEditor

OUTPUT_DIR = "/home/cliff/redact/TestOutput"


def convert_to_docx(input_path):
    """Convert non-docx files to docx via LibreOffice."""
    if input_path.endswith('.docx'):
        return input_path
    try:
        cmd = ['libreoffice', '--headless', '--convert-to', 'docx', '--outdir', '/tmp', input_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        base = os.path.splitext(os.path.basename(input_path))[0]
        output = f"/tmp/{base}.docx"
        if result.returncode == 0 and os.path.exists(output):
            return output
        # Try alternate name
        output2 = f"/tmp/{base}_converted.docx"
        if os.path.exists(output2):
            return output2
        print(f"   ❌ Conversion failed: {result.stderr}")
    except Exception as e:
        print(f"   ❌ Conversion error: {e}")
    return None


def extract_text(docx_path):
    """Extract plain text from docx via LibreOffice."""
    try:
        cmd = ['libreoffice', '--headless', '--convert-to', 'txt', '--outdir', '/tmp', docx_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            txt = f"/tmp/{os.path.splitext(os.path.basename(docx_path))[0]}.txt"
            if os.path.exists(txt):
                with open(txt, 'r', encoding='utf-8') as f:
                    return f.read()
    except Exception as e:
        print(f"   ❌ Text extraction error: {e}")
    return None


def save_analysis_report(base_name, analysis, ai_scores, code_scores, final_scores,
                         applied_items, total_score, edits, output_dir):
    """Save human-readable analysis report."""
    path = os.path.join(output_dir, f"{base_name}_Smart_Attorney_Analysis.md")
    with open(path, 'w') as f:
        f.write(f"# Smart Attorney Analysis: {base_name}\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**System:** v3 Rules Engine\n\n")

        # Terminology
        f.write("## Terminology\n")
        for k, v in analysis.get('terminology', {}).items():
            f.write(f"- **{k}:** {v}\n")

        # Dual scoring
        f.write(f"\n## Scores (Total: {total_score})\n\n")
        f.write("| Category | AI Score | Code Score | Final Score |\n")
        f.write("|----------|----------|------------|-------------|\n")
        for key in sorted(final_scores.keys()):
            ai_s = ai_scores.get(key, '-')
            code_s = code_scores.get(key, '-')
            final_s = final_scores[key]
            marker = " ✓" if key in applied_items else ""
            f.write(f"| {key} | {ai_s} | {code_s} | **{final_s}**{marker} |\n")

        # Applied items
        f.write(f"\n## Applied ({len(applied_items)} items)\n")
        for item in applied_items:
            reason = analysis.get('analysis', {}).get(item, {}).get('reason', '')
            f.write(f"- **{item}** (score {final_scores.get(item, '?')}): {reason}\n")

        # Edits
        f.write(f"\n## Edits ({len(edits)})\n\n")
        for i, edit in enumerate(edits, 1):
            f.write(f"{i}. [{edit.get('category')}] {edit.get('type')}")
            if edit.get('find'):
                f.write(f" — find: \"{edit['find'][:60]}\"")
            if edit.get('content'):
                f.write(f" — content: \"{edit['content'][:80]}\"")
            f.write("\n")

        # Raw analysis per category
        f.write("\n## Detailed Analysis\n\n")
        for key, val in analysis.get('analysis', {}).items():
            if isinstance(val, dict):
                f.write(f"### {key}\n")
                f.write(f"- **Score:** {val.get('score', 'N/A')}\n")
                f.write(f"- **Reason:** {val.get('reason', 'N/A')}\n")
                ql = val.get('quoted_language', '')
                if ql:
                    f.write(f"- **Quoted:** {ql[:200]}\n")
                f.write("\n")

    # Also save raw JSON
    json_path = os.path.join(output_dir, f"{base_name}_analysis.json")
    with open(json_path, 'w') as f:
        json.dump({
            'analysis': analysis,
            'ai_scores': ai_scores,
            'code_scores': code_scores,
            'final_scores': final_scores,
            'applied_items': applied_items,
            'total_score': total_score,
            'edits': edits
        }, f, indent=2)

    return path


def process(input_path, config_name="default_receiver"):
    """Main pipeline."""
    print(f"\n{'='*60}")
    print(f"🔄 Smart Attorney v3: {os.path.basename(input_path)}")
    print(f"{'='*60}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load config
    print("\n[1] Loading config...")
    config = ConfigLoader(config_name)
    print(f"   ✓ Config: {config.config.get('client_name')} ({config.config.get('role')})")

    # Convert to docx
    print("\n[2] Converting to DOCX...")
    docx_path = convert_to_docx(input_path)
    if not docx_path:
        print("❌ Could not convert to DOCX")
        return
    base_name = os.path.splitext(os.path.basename(docx_path))[0]

    # PII redaction
    print("\n[3] Redacting PII...")
    pii = PIIRedactor()
    redacted_path, mapping_path = pii.redact_docx(docx_path, base_name)
    if not redacted_path:
        print("❌ PII redaction failed")
        return

    # Extract text
    print("\n[4] Extracting text...")
    text = extract_text(redacted_path)
    if not text:
        print("❌ Text extraction failed")
        return

    # AI analysis
    print("\n[5] AI analysis...")
    analyzer = AIAnalyzer(config)
    analysis = analyzer.analyze(text, base_name, OUTPUT_DIR)
    if not analysis:
        print("❌ AI analysis failed")
        return

    # Dual scoring
    print("\n[6] Dual scoring...")
    code_scorer = CodeScorer(config)
    code_scores = code_scorer.score(analysis)
    final_scores, ai_scores, code_scores = resolve_scores(analysis, code_scores)

    total = sum(final_scores.values())
    print(f"   📊 Total score: {total}")
    for key in sorted(final_scores.keys()):
        if final_scores[key] > 0:
            ai_s = ai_scores.get(key, 0)
            code_s = code_scores.get(key, 0)
            winner = "AI" if ai_s > code_s else ("CODE" if code_s > ai_s else "AGREE")
            print(f"      {key}: AI={ai_s} CODE={code_s} → {final_scores[key]} ({winner})")

    # Threshold logic
    print("\n[7] Applying thresholds...")
    applied_items, total_score = apply_thresholds(final_scores, config.config)
    print(f"   📋 {len(applied_items)} items qualify:")
    for item in applied_items:
        print(f"      ✓ {item} (score {final_scores.get(item, '?')})")

    # Rules engine
    print("\n[8] Generating edits...")
    rules = RulesEngine(config)
    edits = rules.generate_edits(analysis, applied_items)
    print(f"   ✓ {len(edits)} surgical edits generated")
    for edit in edits:
        print(f"      [{edit.get('category')}] {edit.get('type')}: {edit.get('find', edit.get('content', ''))[:60]}")

    # Save analysis report
    report = save_analysis_report(base_name, analysis, ai_scores, code_scores,
                                  final_scores, applied_items, total_score, edits, OUTPUT_DIR)
    print(f"   ✓ Analysis: {os.path.basename(report)}")

    if not edits:
        print("\n✅ Document is adequate — no changes needed")
        shutil.copy2(docx_path, os.path.join(OUTPUT_DIR, f"{base_name}_Original.docx"))
        return

    # Apply edits to document
    print("\n[9] Applying edits to document...")
    editor = DocumentEditor(OUTPUT_DIR)
    outputs = editor.apply_edits(edits, redacted_path, base_name, mapping_path, pii)

    # Save originals
    print("\n[10] Saving final outputs...")
    shutil.copy2(docx_path, os.path.join(OUTPUT_DIR, f"{base_name}_Original.docx"))
    shutil.copy2(mapping_path, os.path.join(OUTPUT_DIR, f"{base_name}_Mapping.json"))

    print(f"\n{'='*60}")
    print(f"✅ COMPLETE — Output: {OUTPUT_DIR}")
    print(f"{'='*60}")
    print(f"   Original:               {base_name}_Original.docx")
    print(f"   Analysis:               {os.path.basename(report)}")
    for label, path in outputs.items():
        print(f"   {label}: {os.path.basename(path)}")
    print(f"   Edits applied:          {len(edits)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 nda_pipeline.py <input_file> [config_name]")
        print("  config_name defaults to 'default_receiver'")
        sys.exit(1)

    input_file = sys.argv[1]
    config_name = sys.argv[2] if len(sys.argv) > 2 else "default_receiver"

    if not os.path.exists(input_file):
        print(f"Error: File not found — {input_file}")
        sys.exit(1)

    process(input_file, config_name)
