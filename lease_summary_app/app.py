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
import sys
import uuid
import json
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the generic engine
from engine import (
    process_document,
    analyze_with_ai,
    verify_and_expand,
    ai_retry_fields,
    populate_template,
    _generate_output_filename,
)
from agreement_types import get_type, list_types, detect_agreement_type, discover_types

# Also keep backward-compat imports for the pipeline pieces
from lease_summary_tool import ingest_document, redact_and_capture_pii

# XML export
from xml_export import field_data_to_xml, field_data_to_xml_pretty

# Multi-file processing
from multi_file import (
    scan_folder, classify_document, sort_documents, merge_fields,
    merge_normalized_dates, format_field_with_history, build_multi_file_prompt_prefix,
    DocumentInfo, FieldHistory,
)

app = FastAPI(title="SeedJura Agreement Summary")

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
    """Convert Windows path (C:\\foo\\bar) to WSL path (/mnt/c/foo/bar)."""
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
    """Convert WSL path (/mnt/c/foo/bar) to Windows path (C:\\foo\\bar)."""
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
    # Convert to WSL path for filesystem access
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

    # Convert current and parent back to Windows paths
    win_current = _wsl_to_win(wsl_path)
    wsl_parent = os.path.dirname(wsl_path)
    # Don't go above drive root
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


@app.post("/api/upload")
async def upload_agreement(
    file: UploadFile = File(...),
    preparer: str = Form(""),
    purpose: str = Form(""),
    agreement_type: str = Form("auto"),
):
    """
    Upload an agreement file and process it.
    agreement_type: type ID or "auto" for auto-detection.
    """
    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".docx", ".doc", ".txt"):
        raise HTTPException(400, f"Unsupported file type: {ext}. Use PDF, DOCX, or TXT.")

    # Create job directory
    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(WORK_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    # Save uploaded file
    input_path = os.path.join(job_dir, file.filename)
    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Save job metadata
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

    # Run the pipeline
    try:
        # Phase 1: Ingest
        job_meta["phases"]["ingest"] = "running"
        _save_meta(job_dir, job_meta)
        raw_text = ingest_document(input_path)
        job_meta["phases"]["ingest"] = f"done ({len(raw_text):,} chars)"

        # Resolve agreement type
        if agreement_type == "auto":
            detected = detect_agreement_type(raw_text, file.filename)
            if detected:
                agr = get_type(detected)
            else:
                agr = get_type("lease")  # Default fallback
        else:
            agr = get_type(agreement_type)
            if not agr:
                raise HTTPException(400, f"Unknown agreement type: {agreement_type}")

        job_meta["agreement_type"] = agr.type_id
        job_meta["agreement_name"] = agr.name

        # Detect sub-type
        sub_type = agr.detect_sub_type(raw_text, file.filename)
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

        # Phase 3: AI analysis
        job_meta["phases"]["ai"] = "running"
        _save_meta(job_dir, job_meta)
        field_data, ai_anchors, normalized_dates = analyze_with_ai(agr, text_for_ai, sub_type=sub_type)

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

        # Phase 3B: Source verification
        job_meta["phases"]["verify"] = "running"
        _save_meta(job_dir, job_meta)
        field_data, verify_report, flagged = verify_and_expand(agr, field_data, raw_text, ai_anchors)
        job_meta["phases"]["verify"] = (
            f"done (anchor: {verify_report.get('anchor_verified', 0)}, "
            f"exact: {verify_report['exact']}, "
            f"expanded: {verify_report['expanded']}, "
            f"unverified: {verify_report['not_found']})"
        )
        job_meta["field_data"] = field_data
        job_meta["verify_report"] = verify_report
        _save_meta(job_dir, job_meta)

        # Phase 3C: AI retry for flagged fields
        if flagged or any(
            field_data.get(f, "").strip().lower() in ('none', 'none.', '')
            for f in agr.expected_fields
        ):
            field_data, retry_count = ai_retry_fields(agr, field_data, raw_text, flagged)
            if retry_count > 0:
                job_meta["field_data"] = field_data
                job_meta["phases"]["retry"] = f"done (recovered {retry_count})"
                _save_meta(job_dir, job_meta)

        # Phase 4: Generate DOCX
        job_meta["phases"]["generate"] = "running"
        _save_meta(job_dir, job_meta)
        output_path = os.path.join(job_dir, _make_output_name(file.filename))
        populate_template(agr, field_data, output_path)
        job_meta["phases"]["generate"] = "done"
        job_meta["output_path"] = output_path
        job_meta["output_filename"] = os.path.basename(output_path)

        # Generate XML
        normalized_dates = job_meta.get("normalized_dates", {})
        xml_content = field_data_to_xml_pretty(field_data, normalized_dates)
        xml_filename = Path(file.filename).stem + "_GlobalFormVars.xml"
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
            json_filename = Path(file.filename).stem + "_data.json"
            json_dest_path = os.path.join(wsl_output_folder, json_filename)
            try:
                if os.path.exists(json_dest_path):
                    try:
                        os.chmod(json_dest_path, 0o666)
                    except OSError:
                        pass
                with open(json_dest_path, "w", encoding="utf-8") as jf:
                    json.dump({
                        "source_file": file.filename,
                        "generated_at": datetime.now().isoformat(),
                        "agreement_type": agr.type_id,
                        "pii_count": len(pii_findings),
                        "fields_extracted": sum(1 for v in field_data.values() if v),
                        "fields_total": len(agr.fields),
                        "field_data": field_data,
                    }, jf, indent=2)
                saved_files.append(json_filename)
            except PermissionError:
                timestamp = datetime.now().strftime("%H%M%S")
                alt_json = Path(file.filename).stem + f"_data_{timestamp}.json"
                alt_path = os.path.join(wsl_output_folder, alt_json)
                with open(alt_path, "w", encoding="utf-8") as jf:
                    json.dump({
                        "source_file": file.filename,
                        "generated_at": datetime.now().isoformat(),
                        "agreement_type": agr.type_id,
                        "pii_count": len(pii_findings),
                        "fields_extracted": sum(1 for v in field_data.values() if v),
                        "fields_total": len(agr.fields),
                        "field_data": field_data,
                    }, jf, indent=2)
                saved_files.append(alt_json)

        job_meta["saved_to_folder"] = output_folder  # Windows path for display
        job_meta["saved_files"] = saved_files
        job_meta["status"] = "complete"
        _save_meta(job_dir, job_meta)

    except Exception as e:
        job_meta["status"] = "error"
        job_meta["error"] = str(e)
        _save_meta(job_dir, job_meta)
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "error", "error": str(e)},
        )

    return {
        "job_id": job_id,
        "status": "complete",
        "agreement_type": agr.type_id,
        "agreement_name": agr.name,
        "output_filename": job_meta["output_filename"],
        "xml_filename": xml_filename,
        "fields_extracted": filled_count,
        "fields_total": len(agr.fields),
        "pii_count": len(pii_findings),
        "saved_to_folder": output_folder,
        "saved_files": saved_files,
    }


@app.post("/api/upload-folder")
async def upload_folder(
    folder_path: str = Form(...),
    preparer: str = Form(""),
    purpose: str = Form(""),
    agreement_type: str = Form("auto"),
):
    """
    Multi-file summary: process all documents in a folder.
    Merges fields across documents with historical change tracking.
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

    try:
        # Resolve agreement type
        if agreement_type == "auto":
            agr = get_type("lease")  # Default for multi-file
        else:
            agr = get_type(agreement_type)
            if not agr:
                raise HTTPException(400, f"Unknown agreement type: {agreement_type}")

        job_meta["agreement_type"] = agr.type_id
        job_meta["agreement_name"] = agr.name

        # Phase 1: Ingest all documents
        job_meta["phases"]["ingest"] = "running"
        _save_meta(job_dir, job_meta)

        doc_infos: List[DocumentInfo] = []
        for filepath in files:
            filename = os.path.basename(filepath)
            print(f"\n  Ingesting: {filename}")
            raw_text = ingest_document(filepath)

            doc_type, amend_num = classify_document(filename, raw_text)
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

        job_meta["phases"]["ingest"] = f"done ({len(doc_infos)} files)"
        _save_meta(job_dir, job_meta)

        # Phase 2: PII scan (aggregate)
        job_meta["phases"]["pii"] = "running"
        _save_meta(job_dir, job_meta)
        total_pii = 0
        for doc_info in doc_infos:
            _, pii_findings = redact_and_capture_pii(doc_info.text)
            total_pii += len(pii_findings)
        job_meta["phases"]["pii"] = f"done ({total_pii} items across all docs)"
        _save_meta(job_dir, job_meta)

        # Phase 3: AI extraction per document
        job_meta["phases"]["ai"] = "running"
        _save_meta(job_dir, job_meta)

        for i, doc_info in enumerate(doc_infos):
            print(f"\n  [{i+1}/{len(doc_infos)}] AI analyzing: {doc_info.filename}")
            print(f"    Type: {doc_info.doc_type}")

            # Build document-specific prompt prefix
            prompt_prefix = build_multi_file_prompt_prefix(doc_info)

            # Use the engine's analyze function
            field_data, anchors, dates = analyze_with_ai(
                agr, doc_info.text, sub_type=doc_info.doc_type
            )

            doc_info.field_data = field_data
            doc_info.normalized_dates = dates

            # Try to get execution date from the extracted data
            exec_date = dates.get("Date_Lease", "") or dates.get("Date_Commencment", "")
            if exec_date and exec_date != "TBD":
                doc_info.execution_date = exec_date
            doc_info.execution_date_raw = field_data.get("Date_Lease", "")

            filled = sum(1 for v in field_data.values() if v)
            print(f"    Extracted: {filled} fields, Date: {doc_info.execution_date or 'Unknown'}")

        job_meta["phases"]["ai"] = f"done ({len(doc_infos)} documents analyzed)"
        _save_meta(job_dir, job_meta)

        # Phase 4: Sort and merge
        job_meta["phases"]["merge"] = "running"
        _save_meta(job_dir, job_meta)

        sorted_docs = sort_documents(doc_infos)
        merged_fields = merge_fields(sorted_docs)
        merged_dates = merge_normalized_dates(sorted_docs)

        # Build final field_data with history annotations
        final_field_data = {}
        fields_with_history = 0
        for field_name, history in merged_fields.items():
            final_field_data[field_name] = format_field_with_history(history)
            if history.history:
                fields_with_history += 1

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

        filled_count = sum(1 for v in final_field_data.values() if v)
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

        # Generate XML
        xml_filename = f"{folder_name}_multi_GlobalFormVars.xml"
        xml_path = os.path.join(job_dir, xml_filename)
        xml_content = field_data_to_xml_pretty(final_field_data, merged_dates)
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
        job_meta["status"] = "complete"
        _save_meta(job_dir, job_meta)

    except Exception as e:
        import traceback
        traceback.print_exc()
        job_meta["status"] = "error"
        job_meta["error"] = str(e)
        _save_meta(job_dir, job_meta)
        return JSONResponse(
            status_code=500,
            content={"job_id": job_id, "status": "error", "error": str(e)},
        )

    return {
        "job_id": job_id,
        "status": "complete",
        "mode": "multi_file",
        "agreement_type": agr.type_id,
        "agreement_name": agr.name,
        "file_count": len(doc_infos),
        "output_filename": output_filename,
        "fields_extracted": filled_count,
        "fields_with_history": fields_with_history,
        "fields_total": len(agr.fields),
        "pii_count": total_pii,
        "saved_to_folder": output_folder,
        "saved_files": saved_files,
        "documents": job_meta["documents"],
    }


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

    if pretty:
        xml_content = field_data_to_xml_pretty(field_data, normalized_dates)
    else:
        xml_content = field_data_to_xml(field_data, normalized_dates)

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
    with open(os.path.join(job_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)


def _load_meta(job_dir: str) -> dict:
    meta_path = os.path.join(job_dir, "meta.json")
    if not os.path.exists(meta_path):
        return None
    with open(meta_path) as f:
        return json.load(f)


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
