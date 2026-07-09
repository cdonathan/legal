"""
Structured audit logging for compliance and provenance tracking.
Records every cascade decision, AI response, and user action.
"""

import os
import json
from datetime import datetime
from typing import Optional

from models import AuditEntry


class AuditLogger:
    """Records all system decisions for compliance audit trail."""

    def __init__(self):
        self.entries: list[dict] = []
        self.ai_responses: list[str] = []
        self.metadata: dict = {}

    def set_metadata(self, job_id: str, form_type: str, filename: str):
        """Set document-level metadata for the audit report."""
        self.metadata = {
            "job_id": job_id,
            "form_type": form_type,
            "filename": filename,
            "started_at": datetime.now().isoformat(),
        }

    def log_tier_attempt(
        self,
        finding_id: int,
        tier: str,
        input_text: str,
        result: str,
        reason: str,
        score: Optional[float] = None
    ):
        """Log a single cascade tier attempt."""
        entry = {
            "type": "tier_attempt",
            "timestamp": datetime.now().isoformat(),
            "finding_id": finding_id,
            "tier": tier,
            "input_text": input_text[:200],  # Truncate for log readability
            "result": result,
            "reason": reason,
        }
        if score is not None:
            entry["score"] = round(score, 4)
        self.entries.append(entry)

    def log_resolution(
        self,
        finding_id: int,
        replacement: Optional[str],
        clause_id: int,
        confidence: str,
        accepted: Optional[bool] = None
    ):
        """Log the final resolution for a finding."""
        entry = {
            "type": "resolution",
            "timestamp": datetime.now().isoformat(),
            "finding_id": finding_id,
            "replacement_text": replacement[:200] if replacement else None,
            "clause_id": clause_id,
            "confidence": confidence,
        }
        if accepted is not None:
            entry["user_accepted"] = accepted
        self.entries.append(entry)

    def log_ai_response(self, raw_response: str):
        """Store complete AI response for post-hoc review."""
        self.ai_responses.append(raw_response)

    def log_boundary_violation(self, finding_id: int, violation_type: str, details: str):
        """Log when AI response fails boundary enforcement."""
        self.entries.append({
            "type": "boundary_violation",
            "timestamp": datetime.now().isoformat(),
            "finding_id": finding_id,
            "violation_type": violation_type,
            "details": details[:300],
        })

    def log_rules_engine(self, change_id: int, rule_name: str, find_text: str, replace_text: str):
        """Log a deterministic rules engine application."""
        self.entries.append({
            "type": "rules_engine",
            "timestamp": datetime.now().isoformat(),
            "change_id": change_id,
            "rule_name": rule_name,
            "find_text": find_text[:100],
            "replace_text": replace_text[:100],
        })

    def log_provenance_check(self, change_id: int, verified: bool, method: str, clause_id: Optional[int] = None):
        """Log provenance verification result."""
        self.entries.append({
            "type": "provenance_check",
            "timestamp": datetime.now().isoformat(),
            "change_id": change_id,
            "verified": verified,
            "method": method,
            "clause_id": clause_id,
        })

    def log_user_decision(self, change_id: int, accepted: bool):
        """Log user accept/reject decision."""
        self.entries.append({
            "type": "user_decision",
            "timestamp": datetime.now().isoformat(),
            "change_id": change_id,
            "accepted": accepted,
        })

    def get_stats(self) -> dict:
        """Compute summary statistics for the audit report."""
        tier_attempts = [e for e in self.entries if e["type"] == "tier_attempt"]
        resolutions = [e for e in self.entries if e["type"] == "resolution"]
        violations = [e for e in self.entries if e["type"] == "boundary_violation"]

        tier_distribution = {}
        for r in resolutions:
            conf = r.get("confidence", "unknown")
            tier_distribution[conf] = tier_distribution.get(conf, 0) + 1

        return {
            "total_findings": len(resolutions),
            "tier_distribution": tier_distribution,
            "boundary_violations": len(violations),
            "total_tier_attempts": len(tier_attempts),
        }

    def save(self, job_id: str, output_dir: str):
        """Write JSON audit file for the processed document."""
        self.metadata["completed_at"] = datetime.now().isoformat()
        self.metadata["stats"] = self.get_stats()

        audit_report = {
            "metadata": self.metadata,
            "ai_responses": self.ai_responses,
            "entries": self.entries,
        }

        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"{job_id}_audit.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(audit_report, f, indent=2, ensure_ascii=False)

        return filepath
