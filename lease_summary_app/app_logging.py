"""
Structured logging for the SeedJura Agreement Summary app.
Writes to a rotating log file with error codes and timestamps.

Error Code Scheme:
  E1xx - Ingestion errors (file reading, format, OCR)
  E2xx - AI / extraction errors
  E3xx - Verification errors
  E4xx - Output / template / save errors
  E5xx - Configuration / environment errors
  W1xx - Warnings (non-fatal, processing continued)
  I1xx - Info events
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime


# =============================================================================
# ERROR / EVENT CODE CATALOG
# =============================================================================

CODES = {
    # Ingestion errors (E1xx)
    "E100": "File not found",
    "E101": "File is empty",
    "E102": "Unsupported file type",
    "E103": "Legacy .doc format not supported",
    "E104": "PDF could not be opened (corrupt)",
    "E105": "PDF is password-protected",
    "E106": "Error reading PDF pages",
    "E107": "DOCX is password-protected",
    "E108": "DOCX corrupt or invalid",
    "E109": "No readable text extracted",
    "E110": "OCR required but pytesseract/Pillow not installed",
    "E111": "OCR required but Tesseract binary not found",
    "E112": "OCR processing failed",
    # AI errors (E2xx)
    "E200": "OpenAI API key not found",
    "E201": "OpenAI authentication failed",
    "E202": "OpenAI quota/billing issue",
    "E203": "OpenAI service unreachable after retries",
    "E204": "AI response was not valid JSON",
    "E205": "AI returned no fields",
    # Verification errors (E3xx)
    "E300": "Source verification error",
    # Output errors (E4xx)
    "E400": "Template not found",
    "E401": "Template population failed",
    "E402": "Output file save failed (permission)",
    "E403": "XML generation failed",
    # Config / environment (E5xx)
    "E500": "Output folder could not be created",
    "E501": "Settings file error",
    # Warnings (W1xx)
    "W100": "File skipped in multi-file batch",
    "W101": "AI extraction failed for one document (multi-file)",
    "W102": "PII scan failed (non-critical)",
    "W103": "AI JSON recovered from malformed response",
    "W104": "OCR retried with preprocessing",
    # Info (I1xx)
    "I100": "Job started",
    "I101": "Job completed",
    "I102": "Document ingested",
    "I103": "Multi-file batch started",
    "I104": "OCR started",
}


# =============================================================================
# LOGGER SETUP
# =============================================================================

def _log_dir() -> str:
    """Determine the log directory (C:\\seedJura\\logs on Windows)."""
    if os.name == "nt" or sys.platform == "win32":
        base = r"C:\seedJura\logs"
    else:
        base = "/mnt/c/seedJura/logs"
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        # Fall back to app directory
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(base, exist_ok=True)
    return base


_logger = None


def get_logger() -> logging.Logger:
    """Get the configured application logger (singleton)."""
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("seedjura")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        # Rotating file handler: 5 MB per file, keep 5 backups
        log_path = os.path.join(_log_dir(), "seedjura.log")
        file_handler = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

        # Also echo to console
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)

    _logger = logger
    return logger


def log_code(code: str, extra: str = "", job_id: str = "", level: str = None):
    """
    Log an event by its code. Looks up the description from CODES.

    Args:
        code: Error/event code (e.g., "E104")
        extra: Additional context (filename, exception detail, etc.)
        job_id: Associated job ID for correlation
        level: Override log level (defaults inferred from code prefix)
    """
    logger = get_logger()
    description = CODES.get(code, "Unknown code")

    # Infer level from code prefix if not given
    if level is None:
        if code.startswith("E"):
            level = "ERROR"
        elif code.startswith("W"):
            level = "WARNING"
        else:
            level = "INFO"

    parts = [f"[{code}]"]
    if job_id:
        parts.append(f"job={job_id}")
    parts.append(description)
    if extra:
        parts.append(f"- {extra}")
    message = " ".join(parts)

    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    else:
        logger.info(message)


def log_info(message: str, job_id: str = ""):
    """Log a free-form info message."""
    logger = get_logger()
    prefix = f"job={job_id} " if job_id else ""
    logger.info(f"{prefix}{message}")


def log_error(message: str, job_id: str = "", exc: Exception = None):
    """Log a free-form error, optionally with exception details."""
    logger = get_logger()
    prefix = f"job={job_id} " if job_id else ""
    if exc:
        logger.error(f"{prefix}{message} | {type(exc).__name__}: {exc}")
    else:
        logger.error(f"{prefix}{message}")


# Map DocumentIngestError.kind → error code
INGEST_KIND_TO_CODE = {
    "corrupt": "E104",
    "encrypted": "E105",
    "unsupported": "E102",
    "empty": "E109",
    "ocr_unavailable": "E111",
    "general": "E100",
}
