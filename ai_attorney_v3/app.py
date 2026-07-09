"""
AI Attorney v3 — Clause Validation Cascade Engine
FastAPI application with routes for document upload, analysis, approval, and download.
"""

import os
import uuid
import json
import time
import threading
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import config
from models import ProposedChange

app = FastAPI(title="AI Attorney v3 — Clause Validation Cascade")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory job store
jobs: dict = {}


# ============================================================
# JOB PROCESSING (runs in background thread)
# ============================================================

def process_job(job_id: str):
    """Full pipeline orchestrator — runs in background thread."""
    from evaluation_module import EvaluationModule
    from cascade_engine import CascadeEngine
    from provenance_verifier import ProvenanceVerifier
    from rules_engine import RulesEngine
    from clause_repository import ClauseRepository
    from document_processor import DocumentProcessor
    from redaction import apply_hex_redaction
    from context_extractor import extract_context
    from audit_logger import AuditLogger
    import openai

    job = jobs[job_id]
    audit = AuditLogger()
    audit.set_metadata(job_id, job.get("form_type", "NDA"), job.get("filename", ""))

    try:
        # Step 1: Extract text
        job["status"] = "extracting_text"
        job["step"] = 1
        processor = DocumentProcessor()
        text = processor.extract_text(job["file_path"])
        job["original_text"] = text
        job["word_count"] = len(text.split())
        logger.info(f"Job {job_id}: Extracted {job['word_count']} words")

        # Step 2: PII Redaction
        job["status"] = "redacting_pii"
        job["step"] = 2
        redacted_text, pii_mapping = apply_hex_redaction(text)
        job["pii_mapping"] = pii_mapping
        job["pii_count"] = len(pii_mapping)
        logger.info(f"Job {job_id}: Redacted {len(pii_mapping)} PII items")

        # Step 3: Fetch clauses
        job["status"] = "fetching_clauses"
        job["step"] = 3
        form_type = job.get("form_type", "NDA")
        repo = ClauseRepository()
        clauses = repo.get_clauses_by_form_type(form_type)
        job["clauses_count"] = len(clauses)
        job["db_mode"] = repo.get_connection_mode()
        logger.info(f"Job {job_id}: Fetched {len(clauses)} clauses ({repo.get_connection_mode()})")

        if not clauses:
            job["status"] = "error"
            job["error"] = f"No clauses found for form_type '{form_type}'"
            return

        # Step 4: Rules engine (deterministic, runs first)
        job["status"] = "applying_rules"
        job["step"] = 4
        rules = RulesEngine()
        rules_changes = rules.apply(redacted_text)
        for rc in rules_changes:
            audit.log_rules_engine(rc.id, rc.clause_desc or "", rc.find, rc.replace)
        logger.info(f"Job {job_id}: Rules engine found {len(rules_changes)} changes")

        # Step 5: AI Evaluation
        job["status"] = "evaluating"
        job["step"] = 5
        api_key = config.get_openai_api_key()
        if not api_key:
            job["status"] = "error"
            job["error"] = "OpenAI API key not found"
            return

        client = openai.OpenAI(api_key=api_key)
        evaluator = EvaluationModule(client)
        findings = evaluator.evaluate(redacted_text, clauses, form_type)
        logger.info(f"Job {job_id}: AI returned {len(findings)} findings")

        # Store raw AI response for audit
        audit.log_ai_response(json.dumps([{
            "id": f.id, "clause_id": f.clause_id,
            "document_section": f.document_section,
            "issue": f.issue, "suggested_portion": f.suggested_portion,
            "priority": f.priority
        } for f in findings], indent=2))

        # Step 6: Validate AI response (boundary enforcement)
        job["status"] = "validating"
        job["step"] = 6
        valid_findings = evaluator.validate_response(findings, redacted_text, clauses)
        rejected_count = len(findings) - len(valid_findings)
        if rejected_count:
            logger.warning(f"Job {job_id}: {rejected_count} findings rejected by boundary enforcement")

        # Log all findings for debugging
        for f in valid_findings:
            clause = clauses[f.clause_id - 1] if 1 <= f.clause_id <= len(clauses) else None
            logger.info(
                f"Job {job_id} | AI Finding {f.id} | clause_id={f.clause_id} ({clause.prov_desc[:30] if clause else '?'}) | "
                f"priority={f.priority} | "
                f"doc_section='{f.document_section[:60]}...' | "
                f"suggested='{f.suggested_portion[:60]}...'"
            )

        # Step 7: Run cascade for each finding
        job["status"] = "resolving_changes"
        job["step"] = 7
        cascade = CascadeEngine(audit=audit)
        cascade_changes: list[ProposedChange] = []
        change_id = 1

        for finding in valid_findings:
            clause = repo.get_clause_by_id(finding.clause_id, form_type, clauses)
            if not clause:
                audit.log_tier_attempt(finding.id, "lookup", "", "fail", f"clause_id {finding.clause_id} not found")
                continue

            result = cascade.resolve(finding, clause, redacted_text)
            audit.log_resolution(finding.id, result.replacement_text, result.clause_id, result.confidence)

            # Log cascade details for debugging
            logger.info(
                f"Job {job_id} | Finding {finding.id} | Clause: {clause.prov_desc[:40]} | "
                f"Tier: {result.confidence} | "
                f"Find: '{finding.document_section[:50]}...' | "
                f"Suggested: '{finding.suggested_portion[:50]}...' | "
                f"Replace: '{(result.replacement_text or 'MANUAL')[:50]}...'"
            )
            if result.audit_trail:
                for entry in result.audit_trail:
                    logger.info(f"  └─ {entry.tier}: {entry.result} — {entry.reason}")

            # Build ProposedChange from CascadeResult
            if result.confidence == "manual":
                # Human review item
                change = ProposedChange(
                    id=change_id,
                    type="replace",
                    find=finding.document_section,
                    replace="",
                    before_context="",
                    after_context="",
                    confidence="manual",
                    source="cascade_engine",
                    clause_id=clause.id,
                    clause_desc=clause.prov_desc,
                    reasoning=finding.issue,
                    priority=finding.priority,
                    document_position=0,
                    full_clause_text=result.full_clause_text,
                )
            else:
                change = ProposedChange(
                    id=change_id,
                    type="replace",
                    find=finding.document_section,
                    replace=result.replacement_text or "",
                    before_context="",
                    after_context="",
                    confidence=result.confidence,
                    source="cascade_engine",
                    clause_id=clause.id,
                    clause_desc=clause.prov_desc,
                    reasoning=finding.issue,
                    priority=finding.priority,
                    document_position=0,
                    similarity_score=result.similarity_score,
                )

            cascade_changes.append(change)
            change_id += 1

        # Step 8: Provenance verification
        job["status"] = "verifying_provenance"
        job["step"] = 8
        verifier = ProvenanceVerifier()
        verified_changes = verifier.verify_all(cascade_changes, clauses)
        for vc in verified_changes:
            audit.log_provenance_check(vc.id, True, vc.confidence, vc.clause_id)

        # Step 9: Extract context and set document positions
        job["status"] = "preparing_presentation"
        job["step"] = 9
        from text_utils import locate_text_in_document

        for change in verified_changes:
            location = locate_text_in_document(redacted_text, change.find)
            if location:
                change.document_position = location.start
                ctx = extract_context(redacted_text, location.start, location.end, config.CONTEXT_WORD_COUNT)
                change.before_context = ctx.before_text
                change.after_context = ctx.after_text

        # Step 10: Combine rules + cascade, deduplicate
        all_changes = list(rules_changes)

        # Remove cascade changes that overlap with rules engine matches
        rules_texts = {rc.find.lower() for rc in rules_changes}
        for cc in verified_changes:
            if cc.find.lower() not in rules_texts:
                cc.id = change_id
                change_id += 1
                all_changes.append(cc)

        # Sort by document position
        all_changes.sort(key=lambda c: c.document_position)

        # Reassign sequential IDs
        for i, change in enumerate(all_changes, 1):
            change.id = i

        job["proposed_changes"] = all_changes
        job["changes_count"] = len(all_changes)
        job["status"] = "awaiting_selection"
        job["step"] = 10
        job["completed_at"] = datetime.now().isoformat()

        # Save audit log
        job_dir = os.path.join(config.JOBS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        audit.save(job_id, job_dir)

        logger.info(f"Job {job_id}: Complete — {len(all_changes)} changes proposed")

    except Exception as e:
        import traceback
        job["status"] = "error"
        job["error"] = str(e)
        job["traceback"] = traceback.format_exc()
        logger.error(f"Job {job_id} failed: {e}")


# ============================================================
# API ROUTES
# ============================================================

@app.post("/api/upload")
async def upload_file(
    file: UploadFile,
    form_type: str = Form(default="NDA"),
    user_id: int = Form(default=1),
):
    """Upload a document for analysis."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".docx", ".pdf", ".txt", ".mhtml", ".mht"):
        raise HTTPException(400, f"Unsupported file type: {ext}")

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(config.JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    file_path = os.path.join(job_dir, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "step": 0,
        "filename": file.filename,
        "file_path": file_path,
        "form_type": form_type,
        "user_id": user_id,
        "created_at": datetime.now().isoformat(),
        "pass_number": 1,
    }

    thread = threading.Thread(target=process_job, args=(job_id,), daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/job/{job_id}")
def get_job_status(job_id: str):
    """Get job status and proposed changes."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]
    response = {
        "id": job["id"],
        "status": job["status"],
        "step": job["step"],
        "filename": job["filename"],
        "form_type": job.get("form_type"),
        "pass_number": job.get("pass_number", 1),
        "word_count": job.get("word_count"),
        "pii_count": job.get("pii_count"),
        "clauses_count": job.get("clauses_count"),
        "changes_count": job.get("changes_count"),
        "db_mode": job.get("db_mode"),
        "error": job.get("error"),
        "created_at": job["created_at"],
        "completed_at": job.get("completed_at"),
    }

    # Include proposed changes when ready
    if job["status"] == "awaiting_selection" and job.get("proposed_changes"):
        response["proposed_changes"] = [
            _change_to_dict(c) for c in job["proposed_changes"]
        ]

    return response


@app.get("/api/job/{job_id}/document")
def get_document_text(job_id: str):
    """Return full document text with change position markers for preview panel."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]
    text = job.get("original_text", "")
    changes = job.get("proposed_changes", [])

    markers = [
        {"id": c.id, "position": c.document_position, "length": len(c.find)}
        for c in changes if c.document_position > 0
    ]

    return {"text": text, "markers": markers}


@app.post("/api/job/{job_id}/apply")
async def apply_selected(job_id: str, request: Request):
    """Apply user-selected changes to the document."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]
    if job["status"] != "awaiting_selection":
        raise HTTPException(400, f"Job not ready. Status: {job['status']}")

    body = await request.json()
    selected_ids = body if isinstance(body, list) else []

    all_changes = job.get("proposed_changes", [])
    selected = [c for c in all_changes if c.id in selected_ids] if selected_ids else all_changes

    # Only apply non-manual changes
    applicable = [c for c in selected if c.confidence != "manual" and c.replace]

    job_dir = os.path.join(config.JOBS_DIR, job_id)
    base = os.path.splitext(job["filename"])[0]
    pass_num = job.get("pass_number", 1)

    from document_processor import DocumentProcessor
    from redaction import reconstruct_pii_in_docx

    processor = DocumentProcessor()

    # Generate redlined version
    redline_path = os.path.join(job_dir, f"{base}_redline_pass{pass_num}.docx")
    processor.apply_changes(job["file_path"], applicable, redline_path, redline=True)

    # Generate clean version
    clean_path = os.path.join(job_dir, f"{base}_clean_pass{pass_num}.docx")
    processor.apply_changes(job["file_path"], applicable, clean_path, redline=False)

    # Reconstruct PII in output files
    pii_mapping = job.get("pii_mapping", {})
    if pii_mapping:
        reconstruct_pii_in_docx(redline_path, pii_mapping)
        reconstruct_pii_in_docx(clean_path, pii_mapping)

    # Generate PDFs (optional)
    redline_pdf = os.path.join(job_dir, f"{base}_redline_pass{pass_num}.pdf")
    clean_pdf = os.path.join(job_dir, f"{base}_clean_pass{pass_num}.pdf")
    processor.create_pdf(clean_path, clean_pdf)
    time.sleep(1)
    processor.create_pdf(redline_path, redline_pdf)

    job["output_files"] = {
        "redline_docx": redline_path if os.path.exists(redline_path) else None,
        "clean_docx": clean_path if os.path.exists(clean_path) else None,
        "redline_pdf": redline_pdf if os.path.exists(redline_pdf) else None,
        "clean_pdf": clean_pdf if os.path.exists(clean_pdf) else None,
    }
    job["status"] = "complete"
    job["applied_count"] = len(applicable)
    job["can_rerun"] = pass_num < config.MAX_RERUN_PASSES

    return {
        "status": "complete",
        "applied_count": len(applicable),
        "pass_number": pass_num,
        "can_rerun": job["can_rerun"],
        "files": {
            k: f"/api/job/{job_id}/download/{k}" if v else None
            for k, v in job["output_files"].items()
        },
    }


@app.get("/api/job/{job_id}/download/{file_type}")
def download_file(job_id: str, file_type: str):
    """Download output files."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]
    outputs = job.get("output_files", {})
    path = outputs.get(file_type)

    if not path or not os.path.exists(path):
        raise HTTPException(404, f"File not available: {file_type}")

    return FileResponse(path, filename=os.path.basename(path))


@app.post("/api/job/{job_id}/rerun")
def rerun_analysis(job_id: str):
    """Re-analyze the clean output for multi-pass processing."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]
    if job["status"] != "complete":
        raise HTTPException(400, "Job must be complete to rerun")
    if not job.get("can_rerun"):
        raise HTTPException(400, f"Max {config.MAX_RERUN_PASSES} passes reached")

    clean_path = job["output_files"].get("clean_docx")
    if not clean_path or not os.path.exists(clean_path):
        raise HTTPException(400, "Clean output not available for rerun")

    job["file_path"] = clean_path
    job["pass_number"] = job.get("pass_number", 1) + 1
    job["status"] = "queued"
    job["step"] = 0
    job["proposed_changes"] = None
    job["changes_count"] = None

    thread = threading.Thread(target=process_job, args=(job_id,), daemon=True)
    thread.start()

    return {"status": "rerunning", "pass_number": job["pass_number"]}


# ============================================================
# HELPERS
# ============================================================

def _change_to_dict(change: ProposedChange) -> dict:
    """Serialize a ProposedChange for the API response."""
    return {
        "id": change.id,
        "type": change.type,
        "find": change.find,
        "replace": change.replace,
        "before_context": change.before_context,
        "after_context": change.after_context,
        "confidence": change.confidence,
        "source": change.source,
        "clause_id": change.clause_id,
        "clause_desc": change.clause_desc,
        "reasoning": change.reasoning,
        "priority": change.priority,
        "document_position": change.document_position,
        "similarity_score": change.similarity_score,
        "full_clause_text": change.full_clause_text,
    }


# Serve static files (the frontend)
app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
