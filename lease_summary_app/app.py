"""
SeedJura Agreement Summary Web App
====================================
FastAPI backend that wraps the agreement analysis engine with a web interface.
Upload an agreement (PDF/DOCX) → detect type → PII scan → AI extraction → preview → download.

Run:
  cd ~/redact/lease_summary_app
  python3 -m uvicorn app:app --host 0.0.0.0 --port 8083 --reload
"""

import os
import re
import sys
import uuid
import json
import shutil
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the generic engine
from engine import (
    process_document,
    analyze_with_ai,
    analyze_documents_parallel,
    verify_and_expand,
    build_snippets,
    build_snippets_multi_source,
    interpret_fields,
    check_completeness,
    ai_retry_fields,
    suggest_improvements,
    populate_template,
    _generate_output_filename,
)
from agreement_types import get_type, list_types, detect_agreement_type, discover_types

# Also keep backward-compat imports for the pipeline pieces
from lease_summary_tool import ingest_document, redact_and_capture_pii, find_snippet_screenshot
from field_variants import needs_verification

# XML export
from xml_export import field_data_to_xml, field_data_to_xml_pretty, XML_FIELDS

# Multi-file processing
from multi_file import (
    scan_folder, classify_document, sort_documents, merge_fields,
    merge_normalized_dates, format_field_with_history,
    format_field_interpretation, format_field_raw,
    GUARANTY_FIELDS,
    DocumentInfo, FieldHistory,
    parse_strict_date, is_confident_date, has_signature,
)

# Error types
from errors import ProcessingError
from lease_summary_tool import DocumentIngestError

# Structured logging
from app_logging import (
    get_logger, log_code, log_info, log_error, INGEST_KIND_TO_CODE,
)


def _friendly_error(e: Exception) -> str:
    """Extract a user-friendly message from an exception."""
    if isinstance(e, (ProcessingError, DocumentIngestError)):
        return e.message
    # Generic fallback — keep it clean
    msg = str(e)
    if not msg or len(msg) > 300:
        return "An unexpected error occurred while processing this document."
    return msg


# Maps AIServiceError.kind -> structured log code (see app_logging.CODES)
_AI_ERROR_KIND_TO_CODE = {
    "auth": "E201",
    "quota": "E202",
    "transient": "E203",
    "timeout": "E206",
    "circuit_breaker": "E207",
}


def _resolve_error_code(e: Exception, kind: str) -> str:
    """Pick the structured log code for a caught error, preferring the
    AIServiceError.kind mapping over the generic ingest-error fallback."""
    if isinstance(e, DocumentIngestError):
        return INGEST_KIND_TO_CODE.get(kind, "E100")
    return _AI_ERROR_KIND_TO_CODE.get(kind, "E205")

app = FastAPI(title="SeedJura Agreement Summary")

# Initialize logging
get_logger()
log_info("Application starting up")

# Discover available agreement types on startup
discover_types()

# Working directory for uploads and outputs
WORK_DIR = "/tmp/lease_summary_jobs"
os.makedirs(WORK_DIR, exist_ok=True)


# =============================================================================
# API ROUTES
# =============================================================================

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_settings.json")


def _load_settings() -> dict:
    """Load persisted user settings."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"output_folder": r"C:\seedJura\Summary_Output"}


def _save_settings(settings: dict):
    """Persist user settings."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def _win_to_wsl(win_path: str) -> str:
    """Convert Windows path (C:\\foo\\bar) to WSL path (/mnt/c/foo/bar).
    On native Windows, returns the path as-is (no conversion needed)."""
    import platform
    # If running on native Windows, no conversion needed
    if platform.system() == "Windows":
        return win_path.replace("/", "\\") if "/" in win_path else win_path

    path = win_path.replace("\\", "/")
    # Handle C:/ or C:
    if len(path) >= 2 and path[1] == ":":
        drive = path[0].lower()
        rest = path[2:] if len(path) > 2 else ""
        if rest.startswith("/"):
            rest = rest[1:]
        return f"/mnt/{drive}/{rest}".rstrip("/")
    # Already a WSL/Linux path
    return path


def _wsl_to_win(wsl_path: str) -> str:
    """Convert WSL path (/mnt/c/foo/bar) to Windows path (C:\\foo\\bar).
    On native Windows, returns the path as-is."""
    import platform
    # If running on native Windows, just normalize slashes
    if platform.system() == "Windows":
        return wsl_path.replace("/", "\\") if "/" in wsl_path else wsl_path

    if wsl_path.startswith("/mnt/") and len(wsl_path) >= 6:
        drive = wsl_path[5].upper()
        rest = wsl_path[6:] if len(wsl_path) > 6 else ""
        win = f"{drive}:{rest}".replace("/", "\\")
        return win
    # Not a /mnt/ path, return as-is
    return wsl_path


@app.get("/api/settings")
def get_settings():
    """Get current user settings (paths returned as Windows paths)."""
    settings = _load_settings()
    return settings


@app.put("/api/settings")
async def update_settings(
    output_folder: str = Form(...),
):
    """Update user settings (output folder). Accepts Windows or WSL paths."""
    # Convert to WSL for filesystem operations
    wsl_path = _win_to_wsl(output_folder)

    # Validate the folder exists or can be created
    if not os.path.isdir(wsl_path):
        try:
            os.makedirs(wsl_path, exist_ok=True)
        except OSError as e:
            raise HTTPException(400, f"Cannot create folder: {e}")

    # Store the Windows-style path for display
    win_path = _wsl_to_win(wsl_path)
    settings = _load_settings()
    settings["output_folder"] = win_path
    _save_settings(settings)
    return settings


@app.get("/api/browse-folders")
def browse_folders(path: str = "C:\\"):
    """List subdirectories at a given path for the folder browser. Accepts Windows paths."""
    # Convert to WSL path for filesystem access (no-op on native Windows)
    wsl_path = _win_to_wsl(path)

    if not os.path.isdir(wsl_path):
        raise HTTPException(400, f"Not a valid directory: {path}")

    entries = []
    try:
        for entry in sorted(os.scandir(wsl_path), key=lambda e: e.name.lower()):
            if entry.is_dir() and not entry.name.startswith('.'):
                entries.append(entry.name)
    except PermissionError:
        pass

    import platform
    if platform.system() == "Windows":
        # On native Windows, return Windows paths directly
        win_current = wsl_path
        parent = os.path.dirname(wsl_path)
        win_parent = parent if parent != wsl_path else None
    else:
        # On WSL, convert back to Windows display paths
        win_current = _wsl_to_win(wsl_path)
        wsl_parent = os.path.dirname(wsl_path)
        if wsl_parent and wsl_parent != wsl_path and len(wsl_path) > 6:
            win_parent = _wsl_to_win(wsl_parent)
        else:
            win_parent = None

    return {
        "current": win_current,
        "parent": win_parent,
        "folders": entries,
    }


@app.get("/api/agreement-types")
def get_agreement_types():
    """List all available agreement types."""
    return list_types()


def _run_single_file_pipeline(
    job_id: str,
    job_dir: str,
    input_path: str,
    filename: str,
    preparer: str,
    purpose: str,
    agreement_type: str,
):
    """
    Runs the full single-file pipeline (ingest -> PII -> Call 1 -> verify ->
    Call 2 -> completeness/retry -> Call 4 -> generate output). Writes live
    progress to job_dir/meta.json throughout, so callers can poll job status
    via GET /api/status/{job_id} instead of blocking on the HTTP request.
    This function is meant to run in a background thread.
    """
    job_meta = _load_meta(job_dir) or {
        "job_id": job_id,
        "filename": filename,
        "input_path": input_path,
        "preparer": preparer,
        "purpose": purpose,
        "agreement_type_requested": agreement_type,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "phases": {},
    }

    # Run the pipeline
    try:
        # Phase 1: Ingest
        job_meta["phases"]["ingest"] = "running"
        _save_meta(job_dir, job_meta)
        raw_text = ingest_document(input_path)
        job_meta["phases"]["ingest"] = f"done ({len(raw_text):,} chars)"

        # Resolve agreement type
        if agreement_type == "auto":
            detected = detect_agreement_type(raw_text, filename)
            if detected:
                agr = get_type(detected)
            else:
                agr = get_type("lease")  # Default fallback
        else:
            agr = get_type(agreement_type)
            if not agr:
                raise ProcessingError(f"Unknown agreement type: {agreement_type}", kind="general")

        job_meta["agreement_type"] = agr.type_id
        job_meta["agreement_name"] = agr.name

        # Detect sub-type
        sub_type = agr.detect_sub_type(raw_text, filename)
        job_meta["sub_type"] = sub_type
        _save_meta(job_dir, job_meta)

        # Phase 2: PII scan
        job_meta["phases"]["pii"] = "running"
        _save_meta(job_dir, job_meta)
        text_for_ai, pii_findings = redact_and_capture_pii(raw_text)

        pii_summary = {}
        for item in pii_findings:
            pii_summary.setdefault(item["type"], []).append(item["value"])
        job_meta["phases"]["pii"] = f"done ({len(pii_findings)} items)"
        job_meta["pii_summary"] = {k: len(v) for k, v in pii_summary.items()}
        _save_meta(job_dir, job_meta)

        # Phase 3: AI raw extraction (Call 1)
        job_meta["phases"]["ai"] = "running"
        _save_meta(job_dir, job_meta)
        field_data, ai_anchors, normalized_dates, field_sections = analyze_with_ai(
            agr, text_for_ai, sub_type=sub_type
        )

        # Apply user overrides
        if preparer:
            for key in agr.fields:
                if "preparer" in key.lower():
                    field_data[key] = preparer
                    break
        if purpose:
            for key in agr.fields:
                if "purpose" in key.lower():
                    field_data[key] = purpose
                    break
        for key in agr.fields:
            if "summary_date" in key.lower() and not field_data.get(key):
                field_data[key] = datetime.now().strftime("%B %d, %Y")
                break

        filled_count = sum(1 for v in field_data.values() if v)
        job_meta["phases"]["ai"] = f"done ({filled_count}/{len(agr.fields)} fields)"
        job_meta["field_data"] = field_data
        job_meta["normalized_dates"] = normalized_dates
        _save_meta(job_dir, job_meta)

        # Phase 3B: Source verification (also resolves per-field source positions)
        job_meta["phases"]["verify"] = "running"
        _save_meta(job_dir, job_meta)
        field_data, verify_report, flagged, positions = verify_and_expand(agr, field_data, raw_text, ai_anchors)
        job_meta["phases"]["verify"] = (
            f"done (anchor: {verify_report.get('anchor_verified', 0)}, "
            f"exact: {verify_report['exact']}, "
            f"expanded: {verify_report['expanded']}, "
            f"unverified: {verify_report['not_found']})"
        )
        job_meta["field_data"] = field_data
        job_meta["verify_report"] = verify_report
        _save_meta(job_dir, job_meta)

        # Phase 3B2: Human verification pause. Any field whose source region
        # contains a hand-written date/number - whether the AI resolved it
        # confidently or not - is surfaced here for the user to confirm or
        # correct, before spending an AI call interpreting it and before the
        # report is generated. Confident-looking AI guesses can still be
        # wrong, so this isn't limited to outright "NEEDS VERIFICATION"
        # failures.
        touched_fields = _detect_handwriting_touched_fields(raw_text, positions, field_data)
        if touched_fields:
            source_lookup = {fname: input_path for fname in touched_fields}
            # Use the ACTUAL source text at this field's known position as
            # the screenshot search anchor, not the AI's "verbatim" value -
            # the AI occasionally paraphrases slightly even when instructed
            # not to (e.g. returning "this Amendment is made and dated..."
            # when the document literally says "(Amendment) is made and
            # dated..."), which makes page.search_for() either find nothing
            # or match an unrelated occurrence of a short, generic fragment
            # elsewhere on the page. Slicing directly from raw_text at the
            # already-computed position is guaranteed to be a literal
            # substring of the document.
            search_snippets = {
                fname: raw_text[positions[fname][0]:positions[fname][1]]
                for fname in touched_fields if fname in positions
            }
            verification_items = _build_verification_items(
                job_id, job_dir, touched_fields, agr.get_display_labels(), source_lookup,
                search_snippets=search_snippets,
            )
            job_meta["phases"]["verify_human"] = f"waiting ({len(verification_items)} field(s))"
            job_meta["verification_items"] = verification_items
            job_meta["status"] = "needs_verification"
            _save_meta(job_dir, job_meta)

            corrections = _wait_for_corrections(job_id, job_dir)

            job_meta = _load_meta(job_dir) or job_meta
            for fname, corrected_value in corrections.items():
                if fname in field_data and corrected_value and corrected_value.strip():
                    field_data[fname] = corrected_value.strip()

            still_flagged = sum(1 for v in field_data.values() if needs_verification(v))
            job_meta["phases"]["verify_human"] = (
                f"done ({len(corrections)} corrected, {still_flagged} left as NEEDS VERIFICATION)"
            )
            job_meta["field_data"] = field_data
            job_meta["status"] = "processing"
            _save_meta(job_dir, job_meta)

        # Phase 3C: AI interpretation (Call 2) - batched + parallel, using small
        # ±500-char snippets around each field's verified source position rather
        # than the full document. Fields still flagged NEEDS VERIFICATION
        # (uncorrected, or the review pause timed out) are excluded - there's
        # no point spending an AI call interpreting unresolved/garbled text;
        # build_field_variants() already renders "NEEDS VERIFICATION" for
        # these regardless.
        interpret_input = {
            fname: val for fname, val in field_data.items() if not needs_verification(val)
        }
        job_meta["phases"]["interpret"] = "running"
        _save_meta(job_dir, job_meta)
        snippets = build_snippets(raw_text, positions, window=500)

        def _on_interpret_progress(done, total):
            job_meta["phases"]["interpret"] = f"running (batch {done}/{total})"
            _save_meta(job_dir, job_meta)

        interpretations = interpret_fields(agr, interpret_input, snippets, on_progress=_on_interpret_progress)
        job_meta["phases"]["interpret"] = f"done ({len(interpretations)}/{filled_count} fields)"
        job_meta["interpretations"] = interpretations
        job_meta["sections"] = field_sections
        _save_meta(job_dir, job_meta)

        # Phase 3D: Completeness check (code, no AI) + targeted retry for any gaps
        completeness = check_completeness(agr, field_data, interpretations, flagged)
        job_meta["completeness"] = completeness
        if completeness["needs_retry"]:
            job_meta["phases"]["retry"] = "running"
            _save_meta(job_dir, job_meta)
            field_data, retry_count = ai_retry_fields(agr, field_data, raw_text, completeness["needs_retry"])
            job_meta["phases"]["retry"] = f"done (recovered {retry_count})"
            if retry_count > 0:
                job_meta["field_data"] = field_data
                # Fields recovered by retry have no interpretation yet - interpret them too.
                retried_fields = {f: v for f, v in field_data.items() if f in completeness["needs_retry"] and v}
                if retried_fields:
                    retry_positions = {f: p for f, p in positions.items() if f in retried_fields}
                    retry_snippets = build_snippets(raw_text, retry_positions, window=500)
                    extra_interp = interpret_fields(agr, retried_fields, retry_snippets)
                    interpretations.update(extra_interp)
                    job_meta["interpretations"] = interpretations
            _save_meta(job_dir, job_meta)

        # Phase 3D2: Second human verification pause. ai_retry_fields() reads
        # raw source text directly and has no handwriting-resolution
        # guidance of its own, so a field recovered by retry can reintroduce
        # a hand-written/garbled value that slipped past the first
        # verification pause (which only ran on the Call 1 result). Catch
        # any such fields here, before QA/report generation.
        retry_touched = _detect_handwriting_touched_fields(raw_text, positions, field_data)
        if retry_touched:
            source_lookup = {fname: input_path for fname in retry_touched}
            search_snippets = {
                fname: raw_text[positions[fname][0]:positions[fname][1]]
                for fname in retry_touched if fname in positions
            }
            verification_items = _build_verification_items(
                job_id, job_dir, retry_touched, agr.get_display_labels(), source_lookup,
                search_snippets=search_snippets,
            )
            job_meta["phases"]["verify_human"] = f"waiting ({len(verification_items)} field(s), post-retry)"
            job_meta["verification_items"] = verification_items
            job_meta["status"] = "needs_verification"
            _save_meta(job_dir, job_meta)

            corrections = _wait_for_corrections(job_id, job_dir)

            job_meta = _load_meta(job_dir) or job_meta
            for fname, corrected_value in corrections.items():
                if fname in field_data and corrected_value and corrected_value.strip():
                    field_data[fname] = corrected_value.strip()
                    interpretations[fname] = corrected_value.strip()

            still_flagged = sum(1 for v in field_data.values() if needs_verification(v))
            job_meta["phases"]["verify_human"] = (
                f"done ({len(corrections)} corrected/confirmed, {still_flagged} left as NEEDS VERIFICATION)"
            )
            job_meta["field_data"] = field_data
            job_meta["interpretations"] = interpretations
            job_meta["status"] = "processing"
            _save_meta(job_dir, job_meta)

        # Phase 3E: AI QA/feedback pass (Call 4) - suggestions only, saved as a
        # job artifact for improving the config/prompts later. Never applied
        # to this job's output.
        job_meta["phases"]["qa"] = "running"
        _save_meta(job_dir, job_meta)
        try:
            qa_feedback = suggest_improvements(agr, raw_text, field_data, interpretations, field_sections)
            qa_path = os.path.join(job_dir, "qa_feedback.json")
            with open(qa_path, "w", encoding="utf-8") as qf:
                json.dump(qa_feedback, qf, indent=2)
            job_meta["phases"]["qa"] = f"done ({len(qa_feedback.get('suggestions', []))} suggestion(s))"
            job_meta["qa_feedback_path"] = qa_path
        except Exception as e:
            # QA pass is advisory only - never fail the job because of it.
            log_error(f"QA feedback pass failed (non-fatal)", job_id=job_id, exc=e)
            job_meta["phases"]["qa"] = "failed (non-fatal)"
        _save_meta(job_dir, job_meta)

        # Build the 3-variant field set: FieldName / FieldName_Int / FieldName_Raw
        from field_variants import build_field_variants, doc_type_label
        doc_label = doc_type_label(sub_type, fallback=sub_type)
        full_field_data = build_field_variants(
            agr.fields.keys(), field_data,
            interpretations=interpretations, sections=field_sections,
            doc_label=doc_label, short_fields=agr.short_fields,
        )
        job_meta["field_data"] = full_field_data
        job_meta["interpretations"] = interpretations
        job_meta["sections"] = field_sections
        _save_meta(job_dir, job_meta)

        # Phase 4: Generate DOCX
        job_meta["phases"]["generate"] = "running"
        _save_meta(job_dir, job_meta)
        output_path = os.path.join(job_dir, _make_output_name(filename))
        populate_template(agr, full_field_data, output_path)
        job_meta["phases"]["generate"] = "done"
        job_meta["output_path"] = output_path
        job_meta["output_filename"] = os.path.basename(output_path)

        # Generate XML - GlobalFormVars schema for the lease type, the
        # agreement's own field list for every other type (so a non-lease
        # type's real fields appear instead of being dropped for not
        # matching the lease's fixed schema).
        normalized_dates = job_meta.get("normalized_dates", {})
        type_xml_fields = XML_FIELDS if agr.type_id == "lease" else list(agr.fields.keys())
        xml_content = field_data_to_xml_pretty(full_field_data, normalized_dates, xml_fields=type_xml_fields)
        xml_filename = Path(filename).stem + "_GlobalFormVars.xml"
        xml_path = os.path.join(job_dir, xml_filename)
        with open(xml_path, "w", encoding="utf-8") as xf:
            xf.write(xml_content)
        job_meta["xml_path"] = xml_path
        job_meta["xml_filename"] = xml_filename

        # Auto-save to user's output folder
        settings = _load_settings()
        output_folder = settings.get("output_folder", "")
        saved_files = []
        if output_folder:
            wsl_output_folder = _win_to_wsl(output_folder)
            os.makedirs(wsl_output_folder, exist_ok=True)

            def _safe_copy(src, dest_dir, filename):
                """Copy file, handling permission errors by appending a suffix."""
                dest = os.path.join(dest_dir, filename)
                try:
                    # Remove existing file first if it exists (handles read-only)
                    if os.path.exists(dest):
                        try:
                            os.chmod(dest, 0o666)
                        except OSError:
                            pass
                        try:
                            os.remove(dest)
                        except OSError:
                            # File is locked (e.g., open in Word) — use alternate name
                            base, ext = os.path.splitext(filename)
                            timestamp = datetime.now().strftime("%H%M%S")
                            filename = f"{base}_{timestamp}{ext}"
                            dest = os.path.join(dest_dir, filename)
                    shutil.copy2(src, dest)
                    return filename
                except PermissionError:
                    # Last resort: alternate name
                    base, ext = os.path.splitext(filename)
                    timestamp = datetime.now().strftime("%H%M%S")
                    alt_filename = f"{base}_{timestamp}{ext}"
                    alt_dest = os.path.join(dest_dir, alt_filename)
                    shutil.copy2(src, alt_dest)
                    return alt_filename

            # Copy DOCX
            saved_name = _safe_copy(output_path, wsl_output_folder, job_meta["output_filename"])
            saved_files.append(saved_name)
            # Copy XML
            saved_name = _safe_copy(xml_path, wsl_output_folder, xml_filename)
            saved_files.append(saved_name)
            # Save JSON data
            json_filename = Path(filename).stem + "_data.json"
            json_dest_path = os.path.join(wsl_output_folder, json_filename)
            try:
                if os.path.exists(json_dest_path):
                    try:
                        os.chmod(json_dest_path, 0o666)
                    except OSError:
                        pass
                with open(json_dest_path, "w", encoding="utf-8") as jf:
                    json.dump({
                        "source_file": filename,
                        "generated_at": datetime.now().isoformat(),
                        "agreement_type": agr.type_id,
                        "pii_count": len(pii_findings),
                        "fields_extracted": sum(1 for v in field_data.values() if v),
                        "fields_total": len(agr.fields),
                        # field_data includes all 3 variable types per field:
                        # FieldName (base), FieldName_Int (interpretation),
                        # FieldName_Raw (raw copy/paste, with section refs).
                        "field_data": full_field_data,
                        "section_references": field_sections,
                    }, jf, indent=2)
                saved_files.append(json_filename)
            except PermissionError:
                timestamp = datetime.now().strftime("%H%M%S")
                alt_json = Path(filename).stem + f"_data_{timestamp}.json"
                alt_path = os.path.join(wsl_output_folder, alt_json)
                with open(alt_path, "w", encoding="utf-8") as jf:
                    json.dump({
                        "source_file": filename,
                        "generated_at": datetime.now().isoformat(),
                        "agreement_type": agr.type_id,
                        "pii_count": len(pii_findings),
                        "fields_extracted": sum(1 for v in field_data.values() if v),
                        "fields_total": len(agr.fields),
                        "field_data": full_field_data,
                        "section_references": field_sections,
                    }, jf, indent=2)
                saved_files.append(alt_json)

        job_meta["saved_to_folder"] = output_folder  # Windows path for display
        job_meta["saved_files"] = saved_files
        job_meta["fields_extracted"] = filled_count
        job_meta["fields_total"] = len(agr.fields)
        job_meta["pii_count"] = len(pii_findings)
        job_meta["xml_filename"] = xml_filename
        job_meta["status"] = "complete"
        _save_meta(job_dir, job_meta)
        log_code("I101", extra=f"{filename} | {filled_count}/{len(agr.fields)} fields", job_id=job_id)
        return

    except (ProcessingError, DocumentIngestError) as e:
        # Known, user-friendly error
        friendly = _friendly_error(e)
        kind = getattr(e, "kind", "general")
        code = _resolve_error_code(e, kind)
        # Mark which phase was running when this happened - job_meta["phases"]
        # already has that phase set to "running" from before the failing call.
        running_phase = next((p for p, v in job_meta["phases"].items() if v == "running"), None)
        if running_phase:
            job_meta["phases"][running_phase] = f"failed ({kind or 'error'})"
        log_code(code, extra=f"{filename} | {getattr(e, 'detail', '') or friendly}", job_id=job_id)
        job_meta["status"] = "error"
        job_meta["error"] = friendly
        job_meta["error_code"] = code
        job_meta["error_kind"] = kind
        _save_meta(job_dir, job_meta)
        return
    except Exception as e:
        # Unexpected error — log full trace, keep a clean message in meta.json
        import traceback
        traceback.print_exc()
        friendly = _friendly_error(e)
        running_phase = next((p for p, v in job_meta["phases"].items() if v == "running"), None)
        if running_phase:
            job_meta["phases"][running_phase] = "failed"
        log_error(f"Unexpected error processing {filename}", job_id=job_id, exc=e)
        get_logger().error(traceback.format_exc())
        job_meta["status"] = "error"
        job_meta["error"] = friendly
        job_meta["error_code"] = "E999"
        _save_meta(job_dir, job_meta)
        return


@app.post("/api/upload")
async def upload_agreement(
    file: UploadFile = File(...),
    preparer: str = Form(""),
    purpose: str = Form(""),
    agreement_type: str = Form("auto"),
):
    """
    Upload an agreement file and kick off processing in the background.
    agreement_type: type ID or "auto" for auto-detection.
    Returns immediately with a job_id - poll GET /api/status/{job_id} for progress.
    """
    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".docx", ".doc", ".txt"):
        raise HTTPException(400, f"Unsupported file type: {ext}. Use PDF, DOCX, or TXT.")

    # Create job directory
    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(WORK_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    log_code("I100", extra=f"single-file: {file.filename}", job_id=job_id)

    # Save uploaded file
    input_path = os.path.join(job_dir, file.filename)
    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Save initial job metadata, then hand off to a background thread so this
    # request returns immediately instead of blocking for the full pipeline.
    job_meta = {
        "job_id": job_id,
        "filename": file.filename,
        "input_path": input_path,
        "preparer": preparer,
        "purpose": purpose,
        "agreement_type_requested": agreement_type,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "phases": {},
    }
    _save_meta(job_dir, job_meta)

    thread = threading.Thread(
        target=_run_single_file_pipeline,
        args=(job_id, job_dir, input_path, file.filename, preparer, purpose, agreement_type),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "processing"}


def _run_multi_file_pipeline(
    job_id: str,
    job_dir: str,
    folder_path: str,
    wsl_folder: str,
    files: list,
    preparer: str,
    purpose: str,
    agreement_type: str,
):
    """
    Runs the full multi-file pipeline (ingest all -> PII -> per-doc Call 1 +
    Call 2 -> sort/merge -> Call 4 on merged summary -> generate output).
    Writes live progress to job_dir/meta.json throughout. Meant to run in a
    background thread.
    """
    job_meta = _load_meta(job_dir) or {
        "job_id": job_id,
        "mode": "multi_file",
        "folder_path": folder_path,
        "file_count": len(files),
        "preparer": preparer,
        "purpose": purpose,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "phases": {},
        "documents": [],
    }

    try:
        # Resolve agreement type. "auto" can't run real detection until at
        # least one document has been ingested (detect_agreement_type()
        # needs text) - start with the lease type as a placeholder purely
        # so classify_document() below has something to call with, then
        # re-resolve for real against the first successfully-ingested
        # document's text before anything past ingest happens. "lease"
        # remains the final fallback if detection can't determine a type,
        # matching the single-file pipeline's existing "auto" behavior.
        explicit_agreement_type = agreement_type != "auto"
        if explicit_agreement_type:
            agr = get_type(agreement_type)
            if not agr:
                raise ProcessingError(f"Unknown agreement type: {agreement_type}", kind="general")
        else:
            agr = get_type("lease")

        job_meta["agreement_type"] = agr.type_id
        job_meta["agreement_name"] = agr.name

        # Phase 1: Ingest all documents
        job_meta["phases"]["ingest"] = "running"
        _save_meta(job_dir, job_meta)

        doc_infos: List[DocumentInfo] = []
        skipped_files = []  # Track files that failed, so we continue with the rest
        for filepath in files:
            filename = os.path.basename(filepath)
            print(f"\n  Ingesting: {filename}")
            try:
                raw_text = ingest_document(filepath)
            except (DocumentIngestError, ProcessingError) as e:
                # Skip this file but continue with the rest
                reason = _friendly_error(e)
                kind = getattr(e, "kind", "general")
                code = INGEST_KIND_TO_CODE.get(kind, "E100") if isinstance(e, DocumentIngestError) else "E100"
                log_code("W100", extra=f"{filename} [{code}]: {reason}", job_id=job_id)
                print(f"    SKIPPED: {reason}")
                skipped_files.append({"filename": filename, "reason": reason, "code": code})
                continue
            except Exception as e:
                import traceback
                traceback.print_exc()
                log_error(f"Unexpected error ingesting {filename} (skipped)", job_id=job_id, exc=e)
                print(f"    SKIPPED (unexpected): {e}")
                skipped_files.append({"filename": filename, "reason": _friendly_error(e), "code": "E999"})
                continue

            # For "auto" mode, do the real type detection against the
            # first successfully-ingested document, then re-resolve `agr`
            # for every document that follows (including this one).
            if not explicit_agreement_type:
                detected = detect_agreement_type(raw_text, filename)
                if detected:
                    agr = get_type(detected) or agr
                explicit_agreement_type = True  # only detect once, from the first doc
                job_meta["agreement_type"] = agr.type_id
                job_meta["agreement_name"] = agr.name

            doc_type, amend_num = classify_document(filename, raw_text, agreement=agr)
            doc_info = DocumentInfo(
                filepath=filepath,
                filename=filename,
                doc_type=doc_type,
                amendment_number=amend_num,
                text=raw_text,
                char_count=len(raw_text),
            )
            doc_infos.append(doc_info)
            print(f"    Type: {doc_type}, Amendment #: {amend_num}, Chars: {len(raw_text):,}")

        if not doc_infos:
            # Every file failed
            reasons = "; ".join(f"{s['filename']}: {s['reason']}" for s in skipped_files[:5])
            raise ProcessingError(
                f"None of the {len(files)} files could be processed. {reasons}"
            )

        # Phase 1B: Signature gate - a document with no signature block near
        # its end is not an executed/finalized agreement and cannot be
        # trusted for any field (a draft's "Effective Date" line may be
        # blank, wrong, or superseded). Exclude such documents from the
        # pipeline entirely rather than merely flagging them, per explicit
        # instruction. has_signature() only looks at the last
        # SIGNATURE_SEARCH_WINDOW_CHARS characters of the document, which
        # both keeps this cheap and matches how these documents are
        # actually laid out (signature block on the last page, or
        # second-to-last if the last page is blank).
        unsigned_docs = [d for d in doc_infos if not has_signature(d.text)]
        if unsigned_docs:
            doc_infos = [d for d in doc_infos if has_signature(d.text)]
            for d in unsigned_docs:
                log_code("W100", extra=f"{d.filename}: no signature block found - excluded as unfinalized", job_id=job_id)
                print(f"    EXCLUDED (no signature found): {d.filename}")
                skipped_files.append({
                    "filename": d.filename,
                    "reason": "No signature block found in the last part of the document - treated as an unsigned/unfinalized draft and excluded.",
                    "code": "W100",
                })

        if not doc_infos:
            reasons = "; ".join(f"{s['filename']}: {s['reason']}" for s in skipped_files[:5])
            raise ProcessingError(
                f"None of the {len(files)} files have a detectable signature block. {reasons}"
            )

        job_meta["phases"]["ingest"] = f"done ({len(doc_infos)} files, {len(skipped_files)} skipped)"
        job_meta["skipped_files"] = skipped_files
        _save_meta(job_dir, job_meta)

        # Phase 2: PII scan (aggregate)
        job_meta["phases"]["pii"] = "running"
        _save_meta(job_dir, job_meta)
        total_pii = 0
        for doc_info in doc_infos:
            try:
                _, pii_findings = redact_and_capture_pii(doc_info.text)
                total_pii += len(pii_findings)
            except Exception:
                pass  # PII scan is non-critical
        job_meta["phases"]["pii"] = f"done ({total_pii} items across all docs)"
        _save_meta(job_dir, job_meta)

        # Phase 2B: Classify documents by TYPE ONLY (filename/header keyword
        # matching - classify_document(), already reliable and zero AI
        # cost). Deliberately NO pre-AI ordering/"latest" guessing here -
        # that used to require reading filenames before any document was
        # actually read, which produced unreliable chronological guesses
        # (e.g. misordering an Omnibus Agreement as "oldest" when it was one
        # of the newest documents). Every document is now read on its own,
        # in one flat batch, and the three date facts that actually matter
        # (commencement/effective/termination) are derived AFTER extraction
        # from each document's own real, validated date - never guessed
        # from filenames beforehand. See parse_strict_date()/is_confident_date()
        # in multi_file.py for the single source of truth on what counts as
        # a trustworthy date.
        job_meta["phases"]["classify"] = "running"
        _save_meta(job_dir, job_meta)

        # date_roles (from the agreement type's own config.json) drives
        # which doc_type(s) count as the "origin" document (the original
        # lease, the original PSA, etc.), which count as a termination
        # notice, and which count as amendment-like documents competing
        # for "the effective date" - see Phase 3C below. Falls back to the
        # lease's own historical hardcoded values if a type has no
        # date_roles configured, so this is safe for any type added later
        # without one.
        date_roles = agr.date_roles or {
            "origin_types": ["lease"], "origin_date_field": "Date_Lease",
            "origin_date_fallback_field": "Date_Commencment",
            "termination_types": ["termination"], "termination_date_field": "Date_Termination",
            "effective_types": ["amendment", "covid_amendment", "omnibus_agreement"],
            "effective_date_field": "Amendment_Effective_Date",
        }
        origin_types = set(date_roles.get("origin_types", []))
        termination_types = set(date_roles.get("termination_types", []))
        effective_types = set(date_roles.get("effective_types", []))
        origin_date_field = date_roles.get("origin_date_field", "")
        origin_date_fallback_field = date_roles.get("origin_date_fallback_field", "")
        termination_date_field = date_roles.get("termination_date_field", "")
        effective_date_field = date_roles.get("effective_date_field", "")

        lease_doc = next((d for d in doc_infos if d.doc_type in origin_types), None)
        termination_doc = next((d for d in doc_infos if d.doc_type in termination_types), None)

        job_meta["phases"]["classify"] = (
            f"done (origin: {lease_doc.filename if lease_doc else 'none'}, "
            f"termination: {termination_doc.filename if termination_doc else 'none'}, "
            f"{len(doc_infos)} document(s) total)"
        )
        _save_meta(job_dir, job_meta)

        # Phase 3: AI raw extraction - every document read independently, in
        # one flat parallel batch. The lease gets the FULL field list
        # (require_all=True); every other document type is scoped down to
        # only the fields it can plausibly address (guaranty fields for a
        # guaranty doc, everything except lease-only fields for amendments/
        # addenda/omnibus/etc.) and allowed to omit fields it doesn't touch.
        job_meta["phases"]["ai_extract"] = "running"
        _save_meta(job_dir, job_meta)

        lease_only_fields = agr.get_full_lease_only_fields()
        amendment_field_scope = {k: v for k, v in agr.fields.items() if k not in lease_only_fields}
        guaranty_field_scope = {k: v for k, v in agr.fields.items() if k in GUARANTY_FIELDS}

        doc_jobs = []
        for d in doc_infos:
            if d.doc_type in origin_types:
                scope, require_all = dict(agr.fields), True
            elif d.doc_type == "guaranty":
                scope, require_all = guaranty_field_scope, False
            else:
                scope, require_all = amendment_field_scope, False
            doc_jobs.append({
                "key": d.filename, "text": d.text, "sub_type": d.doc_type,
                "only_fields": scope, "require_all": require_all,
            })

        doc_anchors: Dict[str, dict] = {}

        def _on_batch_progress(done, total):
            job_meta["phases"]["ai_extract"] = f"running ({done}/{total} documents)"
            _save_meta(job_dir, job_meta)

        batch_results = analyze_documents_parallel(agr, doc_jobs, on_progress=_on_batch_progress)

        _see_original_default = "See Original Lease." if agr.type_id == "lease" else "See Original Agreement."
        for d in doc_infos:
            field_data, anchors, dates, sections = batch_results.get(d.filename, ({}, {}, {}, {}))
            for fname in agr.fields:
                field_data.setdefault(fname, _see_original_default if d is not lease_doc else "None.")
            d.field_data = field_data
            d.normalized_dates = dates
            d.sections = sections
            doc_anchors[d.filename] = anchors

        job_meta["phases"]["ai_extract"] = f"done ({len(doc_infos)} document(s))"
        _save_meta(job_dir, job_meta)

        # Phase 3B: Source verification (pure code, no AI) - run for every
        # document, resolving each field's source position so Call 3 can
        # build accurate snippets from wherever that field actually came from.
        job_meta["phases"]["verify"] = "running"
        _save_meta(job_dir, job_meta)

        doc_texts: Dict[str, str] = {}
        doc_positions: Dict[str, dict] = {}
        combined_flagged: List[str] = []

        for d in doc_infos:
            verified, _report, flagged, positions = verify_and_expand(
                agr, d.field_data, d.text, doc_anchors.get(d.filename, {})
            )
            d.field_data = verified
            doc_texts[d.filename] = d.text
            doc_positions[d.filename] = positions
            combined_flagged.extend(flagged)

        job_meta["phases"]["verify"] = f"done ({len(doc_infos)} document(s))"
        _save_meta(job_dir, job_meta)

        # Phase 3C: Determine the three date facts that actually matter, by
        # SIMPLE RULE from each document's own real, VALIDATED date - never
        # by AI-guessed filename ordering, and never by a fragile
        # single-format date-string sort. Each fact is pinned to a specific
        # document identity, matching merge_fields()'s pinning:
        #   - Commencement date: the LEASE document's Date_Lease (fallback
        #     Date_Commencment).
        #   - Termination date: the TERMINATION document's Date_Termination,
        #     if a termination notice exists.
        #   - Effective date: among amendment/covid_amendment/omnibus_agreement
        #     documents, whichever has the LATEST validated
        #     Amendment_Effective_Date. A document whose date doesn't parse
        #     as a real date (garbled OCR, blank template, etc.) is simply
        #     not eligible to win this comparison - it becomes a
        #     verification item below instead of silently winning by being
        #     last in some list.
        job_meta["phases"]["dates"] = "running"
        _save_meta(job_dir, job_meta)

        for d in doc_infos:
            if d.doc_type in origin_types:
                raw = d.field_data.get(origin_date_field, "") or (
                    d.field_data.get(origin_date_fallback_field, "") if origin_date_fallback_field else ""
                )
            elif d.doc_type in termination_types:
                raw = d.field_data.get(termination_date_field, "")
            elif d.doc_type in effective_types:
                raw = d.field_data.get(effective_date_field, "")
            else:
                raw = ""
            d.execution_date_raw = raw
            parsed = parse_strict_date(raw)
            d.execution_date = parsed.strftime("%m/%d/%Y") if parsed else None

        effective_date_source = None
        best_date = None
        for d in doc_infos:
            if d.doc_type not in effective_types:
                continue
            parsed = parse_strict_date(d.execution_date_raw)
            if parsed and (best_date is None or parsed > best_date):
                best_date = parsed
                effective_date_source = d

        job_meta["phases"]["dates"] = (
            f"done (origin: {lease_doc.filename if lease_doc else 'none'}, "
            f"effective: {effective_date_source.filename if effective_date_source else 'none'}, "
            f"termination: {termination_doc.filename if termination_doc else 'none'})"
        )
        _save_meta(job_dir, job_meta)

        # Phase 4: Merge - Date_Lease/Date_Commencment pinned to the lease
        # doc, Date_Termination pinned to the termination doc,
        # Amendment_Effective_Date pinned to effective_date_source (all
        # identity-based, not sort-order-based - see merge_fields()).
        # Every other field still uses ordinary latest-wins merge, sorted
        # for history-display purposes only (sort_documents() no longer
        # decides anything about the three pinned date facts above).
        job_meta["phases"]["merge"] = "running"
        _save_meta(job_dir, job_meta)

        sorted_docs = sort_documents(doc_infos, origin_types=origin_types or None)
        origin_only_fields = set(date_roles.get("origin_only_fields", [])) or None
        termination_only_fields = set(date_roles.get("termination_only_fields", [])) or None
        merged_fields = merge_fields(
            sorted_docs,
            effective_date_source=effective_date_source,
            effective_date_field=effective_date_field or "Amendment_Effective_Date",
            origin_only_fields=origin_only_fields,
            origin_types=origin_types or None,
            termination_only_fields=termination_only_fields,
            termination_types=termination_types or None,
        )
        job_meta["phases"]["merge"] = f"done ({len(merged_fields)} fields merged)"
        _save_meta(job_dir, job_meta)

        # Phase 4B: Human verification - ONE combined pass presenting EVERY
        # flagged item at once (not a sequence of separate pauses). Two
        # kinds of items get flagged, combined into a single list:
        #   1. The three priority date facts above, if the document that
        #      should hold that fact has no validated date at all (e.g. the
        #      effective-date search above found zero eligible documents
        #      with a real parsed date - every amendment's date was
        #      garbled/blank) - the user is asked to supply it directly.
        #   2. Any other field whose value came from a source region
        #      containing hand-written text (see
        #      _detect_handwriting_touched_fields) - confident-looking AI
        #      guesses can still be wrong, so this isn't limited to outright
        #      "NEEDS VERIFICATION" failures.
        job_meta["phases"]["verify_human"] = "running"
        _save_meta(job_dir, job_meta)

        touched_for_verification: Dict[str, str] = {}
        touched_search_snippets: Dict[str, str] = {}
        touched_source_docs: Dict[str, "DocumentInfo"] = {}

        def _flag_field(fname: str, value: str, source_doc: "DocumentInfo"):
            touched_for_verification[fname] = value
            touched_source_docs[fname] = source_doc

        # 1. Priority date facts with no eligible/validated document.
        if lease_doc and origin_date_field and not parse_strict_date(lease_doc.execution_date_raw):
            _flag_field(origin_date_field, lease_doc.execution_date_raw or "None.", lease_doc)
        if termination_doc and termination_date_field and not parse_strict_date(termination_doc.execution_date_raw):
            _flag_field(termination_date_field, termination_doc.execution_date_raw or "None.", termination_doc)
        if effective_date_source is None and effective_date_field:
            # No amendment-like document had a validated date at all - ask
            # about whichever such document exists and looks most likely
            # to be the latest one (by amendment number, since no date can
            # be trusted yet); if multiple exist the user can correct any
            # of them and the job will re-resolve the actual latest date
            # from what they enter.
            candidates = [d for d in doc_infos if d.doc_type in effective_types]
            candidates.sort(key=lambda d: d.amendment_number or 0, reverse=True)
            for d in candidates:
                raw = d.field_data.get(effective_date_field, "")
                if raw and raw.strip().lower() not in ("none.", "none", "see original lease.", "see original agreement.", ""):
                    _flag_field(effective_date_field, raw, d)
                    break

        # 2. Any other field whose value touches hand-written source text.
        for fname, hist in merged_fields.items():
            if fname in touched_for_verification:
                continue
            source_text = doc_texts.get(hist.current_source, "")
            source_positions = doc_positions.get(hist.current_source, {})
            hit = _detect_handwriting_touched_fields(
                source_text, source_positions, {fname: hist.current_value},
            )
            if hit:
                source_doc = next((d for d in doc_infos if d.filename == hist.current_source), None)
                _flag_field(fname, hit[fname], source_doc)

        for fname, source_doc in touched_source_docs.items():
            if not source_doc:
                continue
            pos = doc_positions.get(source_doc.filename, {}).get(fname)
            if pos and source_doc.text:
                touched_search_snippets[fname] = source_doc.text[pos[0]:pos[1]]

        if touched_for_verification:
            source_lookup = {
                fname: (touched_source_docs[fname].filepath if touched_source_docs.get(fname) else "")
                for fname in touched_for_verification
            }
            verification_items = _build_verification_items(
                job_id, job_dir, touched_for_verification, agr.get_display_labels(), source_lookup,
                search_snippets=touched_search_snippets,
            )
            job_meta["phases"]["verify_human"] = f"waiting ({len(verification_items)} item(s))"
            job_meta["verification_items"] = verification_items
            job_meta["status"] = "needs_verification"
            _save_meta(job_dir, job_meta)

            corrections = _wait_for_corrections(job_id, job_dir)

            job_meta = _load_meta(job_dir) or job_meta
            human_corrected_fields: set = set()
            for fname, corrected_value in corrections.items():
                if not corrected_value or not corrected_value.strip():
                    continue
                corrected_value = corrected_value.strip()
                source_doc = touched_source_docs.get(fname)
                if fname in merged_fields:
                    merged_fields[fname].current_value = corrected_value
                    merged_fields[fname].current_interpretation = corrected_value
                    merged_fields[fname].current_source = f"{merged_fields[fname].current_source} (human-verified)"
                human_corrected_fields.add(fname)
                # If this correction was one of the three priority date
                # facts, also update the underlying document + the
                # effective_date_source/termination/lease bookkeeping so
                # downstream normalized-date badges/history stay consistent.
                if source_doc is not None:
                    source_doc.field_data[fname] = corrected_value
                    if fname in (origin_date_field, termination_date_field, effective_date_field):
                        source_doc.execution_date_raw = corrected_value
                        parsed = parse_strict_date(corrected_value)
                        source_doc.execution_date = parsed.strftime("%m/%d/%Y") if parsed else None
                        source_doc.normalized_dates[fname] = source_doc.execution_date or ""
                        if fname == effective_date_field and effective_date_source is None:
                            effective_date_source = source_doc

            # A field the human just confirmed/corrected must never be
            # silently overwritten by the completeness-driven AI retry pass
            # below (Phase 4C) - that pass re-reads raw source text and
            # would otherwise reintroduce the exact same garbled/uncertain
            # value the human was just asked to fix. Drop these fields from
            # the flagged list that feeds check_completeness()'s
            # needs_retry so they're treated as already resolved.
            combined_flagged = [f for f in combined_flagged if f not in human_corrected_fields]

            still_flagged = sum(
                1 for fname in touched_for_verification
                if needs_verification(merged_fields.get(fname).current_value if fname in merged_fields else "")
            )
            job_meta["phases"]["verify_human"] = (
                f"done ({len(corrections)} corrected/confirmed, {still_flagged} left as NEEDS VERIFICATION)"
            )
            job_meta["status"] = "processing"
            _save_meta(job_dir, job_meta)
        else:
            job_meta["phases"]["verify_human"] = "done (nothing flagged)"
            _save_meta(job_dir, job_meta)

        # Phase 4B: AI interpretation (Call 3) - ONE call for the whole job,
        # not one per document. Only the CURRENT value of each field ever
        # needs an interpretation (history entries only show raw tagged text),
        # so this interprets each field exactly once, using a snippet from
        # whichever document that field's current value actually came from.
        job_meta["phases"]["interpret"] = "running"
        _save_meta(job_dir, job_meta)

        _none_values = ('none', 'none.', 'n/a', '', 'not applicable', 'see original lease',
                         'see original lease.', 'not found', 'not found.')
        current_values: Dict[str, str] = {}
        field_sources: Dict[str, str] = {}
        for fname, hist in merged_fields.items():
            val = (hist.current_value or "").strip()
            if val.lower() in _none_values:
                continue
            # Fields still flagged NEEDS VERIFICATION after the human-review
            # pause (uncorrected, or the pause timed out) are skipped here -
            # format_field_interpretation() already renders "NEEDS
            # VERIFICATION" for these regardless, so there's no point
            # spending an AI call interpreting garbled/unresolved text.
            if needs_verification(val):
                continue
            current_values[fname] = hist.current_value
            field_sources[fname] = hist.current_source

        snippets = build_snippets_multi_source(field_sources, doc_texts, doc_positions, window=500)

        def _on_interpret_progress(done, total):
            job_meta["phases"]["interpret"] = f"running (batch {done}/{total})"
            _save_meta(job_dir, job_meta)

        call3_interpretations = interpret_fields(agr, current_values, snippets, on_progress=_on_interpret_progress)

        # Patch the merged FieldHistory objects with the real interpretation -
        # merge_fields() only had raw text as a placeholder until now (no
        # per-document interpretation happens anymore in this pipeline).
        for fname, interp in call3_interpretations.items():
            if fname in merged_fields:
                merged_fields[fname].current_interpretation = interp

        job_meta["phases"]["interpret"] = f"done ({len(call3_interpretations)}/{len(current_values)} fields)"
        _save_meta(job_dir, job_meta)

        # Phase 4C: Completeness check (Call 4, pure code, no AI) + targeted
        # retry for any gaps. Simplification: retry reads against the lease
        # text (or the first available document if there's no lease) - fields
        # flagged for retry are almost always core lease-level provisions.
        completeness = check_completeness(agr, current_values, call3_interpretations, combined_flagged)
        job_meta["completeness"] = completeness

        if completeness["needs_retry"]:
            job_meta["phases"]["retry"] = "running"
            _save_meta(job_dir, job_meta)
            retry_source_doc = lease_doc or (sorted_docs[0] if sorted_docs else None)
            if retry_source_doc:
                recovered_field_data, retry_count = ai_retry_fields(
                    agr, dict(current_values), retry_source_doc.text, completeness["needs_retry"]
                )
                job_meta["phases"]["retry"] = f"done (recovered {retry_count})"
                if retry_count > 0:
                    retried_fields = {
                        f: v for f, v in recovered_field_data.items()
                        if f in completeness["needs_retry"] and v
                    }
                    for fname, val in retried_fields.items():
                        if fname in merged_fields:
                            merged_fields[fname].current_value = val
                            merged_fields[fname].current_source = retry_source_doc.filename
                        current_values[fname] = val
                    if retried_fields:
                        # No fresh source positions for newly-recovered fields -
                        # interpret_fields() falls back gracefully to raw text
                        # alone when no snippet is available for a field.
                        # Note: any hand-written/garbled text reintroduced by
                        # ai_retry_fields() here (which reads raw source text
                        # directly, with no handwriting-resolution guidance
                        # of its own) is caught downstream by
                        # format_field_interpretation()'s needs_verification
                        # check and rendered as "NEEDS VERIFICATION" in the
                        # final report - it does not get a second live
                        # verification pause (the single combined pause
                        # earlier in the pipeline is the only one).
                        extra_interp = interpret_fields(agr, retried_fields, {})
                        for fname, interp in extra_interp.items():
                            if fname in merged_fields:
                                merged_fields[fname].current_interpretation = interp
                        call3_interpretations.update(extra_interp)
            else:
                job_meta["phases"]["retry"] = "skipped (no document available)"
            _save_meta(job_dir, job_meta)

        # Build the normalized-date badges shown in the preview UI - derived
        # from the SAME winning document per field that merge_fields()
        # already determined (via merged_fields), computed here (after the
        # verification pause/retry may have changed current_source to
        # "(human-verified)") so it can never disagree with the field's
        # actual displayed value/source.
        merged_dates = merge_normalized_dates(sorted_docs, merged_fields)

        # Build final field_data with the 3 variants per field:
        #   FieldName      -- base value (latest/current, kept for
        #                      backward compatibility)
        #   FieldName_Int  -- Interpretation: latest/superseding value only,
        #                      precise, always tagged with its section ref
        #   FieldName_Raw  -- Raw Data: every historical version, each
        #                      tagged with its source document + section
        from field_variants import clean_value
        final_field_data = {}
        fields_with_history = 0
        for field_name, history in merged_fields.items():
            is_short_field = field_name in agr.short_fields
            final_field_data[field_name] = clean_value(history.current_value)
            final_field_data[f"{field_name}_Int"] = format_field_interpretation(
                history, suppress_section=is_short_field,
            )
            final_field_data[f"{field_name}_Raw"] = format_field_raw(history)
            if history.history:
                fields_with_history += 1

        # Fields never seen in any document at all still need to show "None"
        # for every one of the 3 variables (never a bare/blank placeholder).
        for field_name in agr.fields:
            if field_name not in final_field_data:
                final_field_data[field_name] = "None"
                final_field_data[f"{field_name}_Int"] = "None"
                final_field_data[f"{field_name}_Raw"] = "None"

        # Apply user overrides
        if preparer:
            for key in agr.fields:
                if "preparer" in key.lower():
                    final_field_data[key] = preparer
                    break
        if purpose:
            for key in agr.fields:
                if "purpose" in key.lower():
                    final_field_data[key] = purpose
                    break
        for key in agr.fields:
            if "summary_date" in key.lower():
                final_field_data[key] = datetime.now().strftime("%B %d, %Y")
                break

        filled_count = sum(1 for k in agr.fields if final_field_data.get(k, "None") not in ("", "None"))
        job_meta["phases"]["merge"] = (
            f"done ({filled_count} fields, {fields_with_history} with history)"
        )
        job_meta["field_data"] = final_field_data
        job_meta["normalized_dates"] = merged_dates

        # Store document list for reference
        job_meta["documents"] = [
            {
                "filename": d.filename,
                "doc_type": d.doc_type,
                "amendment_number": d.amendment_number,
                "execution_date": d.execution_date,
                "fields_extracted": sum(1 for v in d.field_data.values() if v),
            }
            for d in sorted_docs
        ]
        _save_meta(job_dir, job_meta)

        # Phase 4B: AI QA/feedback pass (Call 4) on the MERGED summary - one
        # call for the whole multi-file job, not one per document. Suggestions
        # only, saved as a job artifact, never applied to this job's output.
        job_meta["phases"]["qa"] = "running"
        _save_meta(job_dir, job_meta)
        try:
            combined_text = "\n\n=== DOCUMENT BREAK ===\n\n".join(
                f"[{d.filename}]\n{d.text}" for d in sorted_docs
            )
            merged_interpretations = {
                f: hist.current_interpretation for f, hist in merged_fields.items()
            }
            merged_sections = {
                f: hist.current_section for f, hist in merged_fields.items()
            }
            qa_feedback = suggest_improvements(
                agr, combined_text, final_field_data, merged_interpretations, merged_sections
            )
            qa_path = os.path.join(job_dir, "qa_feedback.json")
            with open(qa_path, "w", encoding="utf-8") as qf:
                json.dump(qa_feedback, qf, indent=2)
            job_meta["phases"]["qa"] = f"done ({len(qa_feedback.get('suggestions', []))} suggestion(s))"
            job_meta["qa_feedback_path"] = qa_path
        except Exception as e:
            log_error(f"QA feedback pass failed (non-fatal)", job_id=job_id, exc=e)
            job_meta["phases"]["qa"] = "failed (non-fatal)"
        _save_meta(job_dir, job_meta)

        # Phase 5: Generate output
        job_meta["phases"]["generate"] = "running"
        _save_meta(job_dir, job_meta)

        # Use folder name for output filename
        folder_name = Path(folder_path).name
        date_str = datetime.now().strftime("%m-%d-%y")
        output_filename = f"{folder_name}_multi_summary_{date_str}.docx"
        output_path = os.path.join(job_dir, output_filename)

        populate_template(agr, final_field_data, output_path)
        job_meta["output_path"] = output_path
        job_meta["output_filename"] = output_filename

        # Generate XML - GlobalFormVars schema for the lease type, the
        # agreement's own field list for every other type.
        xml_filename = f"{folder_name}_multi_GlobalFormVars.xml"
        xml_path = os.path.join(job_dir, xml_filename)
        type_xml_fields = XML_FIELDS if agr.type_id == "lease" else list(agr.fields.keys())
        xml_content = field_data_to_xml_pretty(final_field_data, merged_dates, xml_fields=type_xml_fields)
        with open(xml_path, "w", encoding="utf-8") as xf:
            xf.write(xml_content)
        job_meta["xml_filename"] = xml_filename

        # Auto-save to output folder
        settings = _load_settings()
        output_folder = settings.get("output_folder", "")
        saved_files = []
        if output_folder:
            wsl_output_folder = _win_to_wsl(output_folder)
            os.makedirs(wsl_output_folder, exist_ok=True)

            def _safe_copy_mf(src, dest_dir, filename):
                dest = os.path.join(dest_dir, filename)
                try:
                    if os.path.exists(dest):
                        try:
                            os.chmod(dest, 0o666)
                            os.remove(dest)
                        except OSError:
                            base, ext = os.path.splitext(filename)
                            timestamp = datetime.now().strftime("%H%M%S")
                            filename = f"{base}_{timestamp}{ext}"
                            dest = os.path.join(dest_dir, filename)
                    shutil.copy2(src, dest)
                    return filename
                except PermissionError:
                    base, ext = os.path.splitext(filename)
                    timestamp = datetime.now().strftime("%H%M%S")
                    alt = f"{base}_{timestamp}{ext}"
                    shutil.copy2(src, os.path.join(dest_dir, alt))
                    return alt

            saved_files.append(_safe_copy_mf(output_path, wsl_output_folder, output_filename))
            saved_files.append(_safe_copy_mf(xml_path, wsl_output_folder, xml_filename))

            # JSON data
            json_filename = f"{folder_name}_multi_data.json"
            json_dest = os.path.join(wsl_output_folder, json_filename)
            with open(json_dest, "w", encoding="utf-8") as jf:
                json.dump({
                    "source_folder": folder_path,
                    "generated_at": datetime.now().isoformat(),
                    "documents": job_meta["documents"],
                    "fields_with_history": fields_with_history,
                    "field_data": final_field_data,
                    "normalized_dates": merged_dates,
                }, jf, indent=2)
            saved_files.append(json_filename)

        job_meta["phases"]["generate"] = "done"
        job_meta["saved_to_folder"] = output_folder
        job_meta["saved_files"] = saved_files
        job_meta["output_filename"] = output_filename
        job_meta["file_count"] = len(doc_infos)
        job_meta["fields_extracted"] = filled_count
        job_meta["fields_total"] = len(agr.fields)
        job_meta["fields_with_history"] = fields_with_history
        job_meta["pii_count"] = total_pii
        job_meta["status"] = "complete"
        _save_meta(job_dir, job_meta)
        log_code("I101", extra=f"multi-file {folder_name} | {len(doc_infos)} docs, "
                 f"{len(skipped_files)} skipped, {fields_with_history} fields w/ history", job_id=job_id)
        return

    except Exception as e:
        import traceback
        traceback.print_exc()
        friendly = _friendly_error(e)
        kind = getattr(e, "kind", "")
        code = _resolve_error_code(e, kind) if isinstance(e, ProcessingError) else "E999"
        running_phase = next((p for p, v in job_meta["phases"].items() if v == "running"), None)
        if running_phase:
            job_meta["phases"][running_phase] = f"failed ({kind or 'error'})" if kind else "failed"
        log_error(f"Multi-file job failed: {friendly}", job_id=job_id, exc=e)
        get_logger().error(traceback.format_exc())
        job_meta["status"] = "error"
        job_meta["error"] = friendly
        job_meta["error_code"] = code
        job_meta["error_kind"] = kind
        _save_meta(job_dir, job_meta)
        return


@app.post("/api/upload-folder")
async def upload_folder(
    folder_path: str = Form(...),
    preparer: str = Form(""),
    purpose: str = Form(""),
    agreement_type: str = Form("auto"),
):
    """
    Multi-file summary: kick off processing of all documents in a folder in
    the background. Merges fields across documents with historical change
    tracking. Returns immediately with a job_id - poll GET /api/status/{job_id}.
    """
    # Convert Windows path to WSL if needed
    wsl_folder = _win_to_wsl(folder_path)

    if not os.path.isdir(wsl_folder):
        raise HTTPException(400, f"Folder not found: {folder_path}")

    # Find all documents
    files = scan_folder(wsl_folder)
    if not files:
        raise HTTPException(400, f"No supported files found in: {folder_path}")

    # Create job
    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(WORK_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    job_meta = {
        "job_id": job_id,
        "mode": "multi_file",
        "folder_path": folder_path,
        "file_count": len(files),
        "preparer": preparer,
        "purpose": purpose,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "phases": {},
        "documents": [],
    }
    _save_meta(job_dir, job_meta)

    log_code("I103", extra=f"{folder_path} ({len(files)} files)", job_id=job_id)

    thread = threading.Thread(
        target=_run_multi_file_pipeline,
        args=(job_id, job_dir, folder_path, wsl_folder, files, preparer, purpose, agreement_type),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "processing"}


@app.get("/api/status/{job_id}")
def get_job_status(job_id: str):
    """
    Poll live progress for a running (or finished) job. Returns the job's
    meta.json contents directly - includes `phases` (per-phase status
    strings, updated live as the pipeline runs), `status`
    (processing/complete/error), and `error`/`error_kind` when failed.
    """
    job_dir = os.path.join(WORK_DIR, job_id)
    meta = _load_meta(job_dir)
    if not meta:
        raise HTTPException(404, "Job not found")
    return meta


@app.get("/api/verify-screenshot/{job_id}/{field_name}")
def get_verify_screenshot(job_id: str, field_name: str):
    """
    Serve the cropped source-document screenshot generated for a field
    flagged NEEDS VERIFICATION, so the human-review UI can show the user
    exactly what the source document says next to their correction input.
    """
    job_dir = os.path.join(WORK_DIR, job_id)
    safe_name = _safe_field_filename(field_name)
    path = os.path.join(job_dir, "verify_screenshots", f"{safe_name}.png")
    if not os.path.exists(path):
        raise HTTPException(404, "No screenshot available for this field")
    return FileResponse(path, media_type="image/png")


@app.post("/api/verify/{job_id}")
async def submit_verification(job_id: str, corrections: dict):
    """
    Submit human corrections for fields flagged NEEDS VERIFICATION, and
    resume the paused background pipeline. Body: {"corrections": {field_name:
    corrected_value, ...}}. Fields omitted from `corrections` (or submitted
    with an empty value) are left as-is - they'll remain flagged "NEEDS
    VERIFICATION" in the final output. Returns immediately; poll
    GET /api/status/{job_id} as usual to see the pipeline resume and finish.
    """
    job_dir = os.path.join(WORK_DIR, job_id)
    meta = _load_meta(job_dir)
    if not meta:
        raise HTTPException(404, "Job not found")
    if meta.get("status") != "needs_verification":
        raise HTTPException(400, "This job is not currently waiting on verification")

    corrections_dict = corrections.get("corrections", corrections) if isinstance(corrections, dict) else {}
    if not isinstance(corrections_dict, dict):
        raise HTTPException(400, "corrections must be an object mapping field name to corrected value")

    meta["_pending_corrections"] = corrections_dict
    _save_meta(job_dir, meta)

    with _VERIFICATION_LOCK:
        event = _VERIFICATION_EVENTS.get(job_id)
    if event is None:
        # The pipeline thread isn't (or is no longer) waiting - most likely
        # the wait already timed out. The corrections are saved to meta.json
        # regardless, but nothing will consume them.
        raise HTTPException(409, "This job is no longer waiting on verification (it may have timed out)")
    event.set()

    return {"job_id": job_id, "status": "resuming", "corrections_received": len(corrections_dict)}


@app.get("/api/preview/{job_id}")
def preview_summary(job_id: str):
    """Return the extracted field data as a structured preview."""
    job_dir = os.path.join(WORK_DIR, job_id)
    meta = _load_meta(job_dir)
    if not meta:
        raise HTTPException(404, "Job not found")
    if meta["status"] != "complete":
        raise HTTPException(400, f"Job status: {meta['status']}")

    field_data = meta.get("field_data", {})
    agreement_type_id = meta.get("agreement_type", "lease")
    agr = get_type(agreement_type_id)

    if not agr:
        raise HTTPException(500, f"Agreement type '{agreement_type_id}' not found")

    # Build sections from agreement type config
    preview = []
    for section in agr.sections:
        items = []
        for field_entry in section.get("fields", []):
            # Each entry is [field_key, label]
            if isinstance(field_entry, (list, tuple)) and len(field_entry) >= 2:
                field_key, label = field_entry[0], field_entry[1]
            else:
                continue
            items.append({
                "key": field_key,
                "label": label,
                "value": field_data.get(field_key, ""),
                "interpretation": field_data.get(f"{field_key}_Int", ""),
                "raw": field_data.get(f"{field_key}_Raw", ""),
            })
        preview.append({"title": section["title"], "items": items})

    return {
        "job_id": job_id,
        "filename": meta.get("filename", meta.get("folder_path", "")),
        "agreement_type": agreement_type_id,
        "agreement_name": agr.name,
        "mode": meta.get("mode", "single"),
        "documents": meta.get("documents", []),
        "output_filename": meta.get("output_filename", ""),
        "pii_summary": meta.get("pii_summary", {}),
        "normalized_dates": meta.get("normalized_dates", {}),
        "sections": preview,
        "all_fields": field_data,
    }


@app.get("/api/download/{job_id}")
def download_summary(job_id: str):
    """Download the generated DOCX file."""
    job_dir = os.path.join(WORK_DIR, job_id)
    meta = _load_meta(job_dir)
    if not meta:
        raise HTTPException(404, "Job not found")
    if meta["status"] != "complete":
        raise HTTPException(400, f"Job not complete: {meta['status']}")

    output_path = meta.get("output_path")
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(404, "Output file not found")

    return FileResponse(
        path=output_path,
        filename=meta["output_filename"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/download-xml/{job_id}")
def download_xml(job_id: str, pretty: bool = False):
    """Download the extracted data as GlobalFormVars XML."""
    job_dir = os.path.join(WORK_DIR, job_id)
    meta = _load_meta(job_dir)
    if not meta:
        raise HTTPException(404, "Job not found")
    if meta["status"] != "complete":
        raise HTTPException(400, f"Job not complete: {meta['status']}")

    field_data = meta.get("field_data", {})
    if not field_data:
        raise HTTPException(404, "No field data available")

    normalized_dates = meta.get("normalized_dates", {})

    # GlobalFormVars schema for the lease type, the agreement's own field
    # list for every other type (so a non-lease type's real fields appear
    # instead of being dropped for not matching the lease's fixed schema).
    type_id = meta.get("agreement_type", "lease")
    agr_for_xml = get_type(type_id)
    type_xml_fields = XML_FIELDS if (not agr_for_xml or type_id == "lease") else list(agr_for_xml.fields.keys())

    if pretty:
        xml_content = field_data_to_xml_pretty(field_data, normalized_dates, xml_fields=type_xml_fields)
    else:
        xml_content = field_data_to_xml(field_data, normalized_dates, xml_fields=type_xml_fields)

    # Generate filename from source
    base = Path(meta["filename"]).stem
    xml_filename = f"{base}_GlobalFormVars.xml"

    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{xml_filename}"'},
    )


# =============================================================================
# HELPERS
# =============================================================================

def _save_meta(job_dir: str, meta: dict):
    """
    Write job_dir/meta.json ATOMICALLY. The background pipeline thread calls
    this dozens of times per job (once per phase update) while the frontend
    polls GET /api/status/{job_id} every ~1.5s on a separate request thread.
    A plain open(path, "w") truncates the file before writing its new
    content, leaving a window where a concurrent read sees a
    truncated/empty file and fails to parse it as JSON ("Lost track of this
    job"). Writing to a temp file in the same directory and renaming it into
    place (os.replace) avoids that window - the rename is atomic on both
    POSIX and Windows, so a reader always sees either the old or the new
    complete content, never a partial write.
    """
    meta_path = os.path.join(job_dir, "meta.json")
    tmp_path = meta_path + f".tmp{os.getpid()}"
    with open(tmp_path, "w") as f:
        json.dump(meta, f, indent=2)
    os.replace(tmp_path, meta_path)


def _load_meta(job_dir: str) -> dict:
    meta_path = os.path.join(job_dir, "meta.json")
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Extremely narrow residual race (e.g. reading mid os.replace on a
        # filesystem without full atomic-rename guarantees) - treat as
        # "try again" rather than a hard failure. Callers that need the
        # freshest data will simply poll again shortly.
        return None


# =============================================================================
# HUMAN VERIFICATION PAUSE/RESUME
# =============================================================================
# When a field's value still carries an unresolved handwriting/uncertainty
# marker (see field_variants.needs_verification) after AI extraction, the
# pipeline pauses here rather than silently shipping a guessed or garbled
# value in the final report. The background thread blocks on a
# threading.Event until a human submits corrections via
# POST /api/verify/{job_id} (or the wait times out), then resumes with
# whatever corrections were provided.

_VERIFICATION_EVENTS: Dict[str, threading.Event] = {}
_VERIFICATION_LOCK = threading.Lock()
_VERIFICATION_TIMEOUT_SEC = 60 * 60  # 1 hour - generous, this is a human-paced step


def _safe_field_filename(field_name: str) -> str:
    """Sanitize a field name for use as a screenshot filename on disk."""
    return re.sub(r"[^A-Za-z0-9_]", "_", field_name)


_HANDWRITTEN_MARKER_RE = re.compile(r'\[handwritten[^\]]*\]', re.IGNORECASE)


def _detect_handwriting_touched_fields(
    raw_text: str,
    positions: Dict[str, tuple],
    field_data: Dict[str, str],
    window: int = 3,
) -> Dict[str, str]:
    """
    Find every field whose resolved value either (a) still carries an
    unresolved handwriting/uncertainty marker (needs_verification), or (b)
    was extracted from a source span that directly OVERLAPS (or is
    immediately adjacent to, within `window` chars) a "[handwritten...]"
    marker, even though the AI DID manage to resolve it into a clean-
    looking value. Both cases get surfaced for human confirmation - the
    goal is catching every field whose OWN value came from hand-written
    source text, not just ones the AI failed on, since a confident-looking
    guess can still be wrong.

    `window` is deliberately tiny (a couple characters, not a phrase or
    sentence) - fields merely appearing in the same sentence as a
    hand-filled blank (e.g. "a Delaware corporation" a few words before
    "The date of this Lease is ___") must NOT be flagged just for being
    nearby. Only a field whose actual extracted span touches the
    handwritten marker's span should be flagged.

    Returns {field_name: ai_resolved_value}.
    """
    handwritten_spans = [m.span() for m in _HANDWRITTEN_MARKER_RE.finditer(raw_text or "")]
    touched = {}
    for fname, val in field_data.items():
        if needs_verification(val):
            touched[fname] = val
            continue
        if not handwritten_spans:
            continue
        pos = positions.get(fname)
        if not pos:
            continue
        start, end = pos
        for hs, he in handwritten_spans:
            if hs - window <= end and he + window >= start:
                touched[fname] = val
                break
    return touched


def _is_date_field(field_name: str) -> bool:
    """Heuristic: does this field name represent a date value? Used to give
    the user a format hint (e.g. 'Enter as Month Day, Year') on the
    verification screen, since date fields are by far the most common
    thing flagged for hand-written-text review."""
    return "date" in field_name.lower()


def _build_verification_instruction(field_label: str, source_file: str, is_date: bool, ai_confident: bool) -> str:
    """
    Build a short, plain-language instruction telling the user exactly what
    they're being asked to do for one flagged field - which value to look
    for in the highlighted source image, and what format to type it in if
    they need to correct it. Shown directly on the verification card so the
    user isn't left guessing what a bare field name/AI value means.
    """
    doc_ref = f' in "{source_file}"' if source_file else " in the source document"
    what = f"the {field_label.lower()}" if field_label else "this value"
    format_hint = " Enter it as Month Day, Year (e.g. November 22, 2019)." if is_date else ""

    if ai_confident:
        return (
            f"We need you to confirm {what}{doc_ref}. The AI's reading is shown below - "
            f"check it against the highlighted image and either confirm it's correct, "
            f"or type the correct value yourself.{format_hint}"
        )
    return (
        f"We need you to read {what}{doc_ref} - the handwriting was too unclear for the "
        f"AI to confidently read it. Look at the highlighted image below and type the "
        f"correct value.{format_hint}"
    )


def _build_verification_items(
    job_id: str,
    job_dir: str,
    touched: Dict[str, str],
    field_labels: Dict[str, str],
    source_lookup: Dict[str, str],
    search_snippets: Dict[str, str] = None,
) -> List[dict]:
    """
    Build the list of verification items shown to the user, and generate a
    cropped screenshot on disk for each field where a source PDF is
    available. touched: {field_name: ai_resolved_value} - the value the AI
    ultimately derived, shown to the user as a pre-filled/confirmable
    answer rather than something they must retype from scratch.
    search_snippets: {field_name: text_to_search_for_in_pdf} - optionally a
    different (usually more literal/source-verbatim) string to locate the
    screenshot with, since the AI's resolved value (e.g. "July 30, 2007")
    may not appear verbatim in the source PDF's own text layer the way the
    original garbled sentence around it does.
    source_lookup: {field_name: source_file_path} - a field with no
    resolvable path (e.g. a DOCX source) simply gets no screenshot.
    """
    search_snippets = search_snippets or {}
    screenshots_dir = os.path.join(job_dir, "verify_screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    items = []
    for fname, ai_value in touched.items():
        source_path = source_lookup.get(fname, "")
        search_text = search_snippets.get(fname) or ai_value
        has_screenshot = False
        if source_path and os.path.exists(source_path) and source_path.lower().endswith(".pdf"):
            try:
                png_bytes = find_snippet_screenshot(source_path, search_text)
            except Exception:
                png_bytes = None
            if png_bytes:
                safe_name = _safe_field_filename(fname)
                with open(os.path.join(screenshots_dir, f"{safe_name}.png"), "wb") as f:
                    f.write(png_bytes)
                has_screenshot = True

        label = field_labels.get(fname, fname)
        is_date = _is_date_field(fname)
        # False when the AI outright gave up (needs_verification marker
        # still present) - the UI shows no confirm checkbox in that case
        # since there's nothing confident to confirm, just a required
        # text box.
        ai_confident = not needs_verification(ai_value)
        source_file = os.path.basename(source_path) if source_path else ""

        items.append({
            "field": fname,
            "label": label,
            "ai_value": ai_value,
            "ai_confident": ai_confident,
            "is_date": is_date,
            "instruction": _build_verification_instruction(label, source_file, is_date, ai_confident),
            "source_file": source_file,
            "screenshot_url": f"/api/verify-screenshot/{job_id}/{fname}" if has_screenshot else None,
        })
    return items


def _wait_for_corrections(job_id: str, job_dir: str) -> Dict[str, str]:
    """
    Block the calling (background pipeline) thread until corrections are
    submitted via POST /api/verify/{job_id}, or _VERIFICATION_TIMEOUT_SEC
    elapses. Returns whatever corrections dict was submitted (possibly
    partial, possibly empty on timeout) - any field left uncorrected simply
    stays flagged "NEEDS VERIFICATION" in the final output rather than
    blocking the job forever.
    """
    with _VERIFICATION_LOCK:
        event = _VERIFICATION_EVENTS.setdefault(job_id, threading.Event())
        event.clear()

    event.wait(timeout=_VERIFICATION_TIMEOUT_SEC)

    with _VERIFICATION_LOCK:
        _VERIFICATION_EVENTS.pop(job_id, None)

    meta = _load_meta(job_dir) or {}
    return meta.get("_pending_corrections", {}) or {}


def _make_output_name(input_filename: str) -> str:
    import re
    base = Path(input_filename).stem
    clean = re.sub(r"(?i)[\s_-]*(fully[\s_-]*executed|execution|final|signed|copy)", "", base)
    clean = re.sub(r"[\s_-]+$", "", clean)
    clean = re.sub(r"\s+", "_", clean)
    date_str = datetime.now().strftime("%m-%d-%y")
    return f"{clean}_summary_{date_str}.docx"


# Serve static frontend
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
