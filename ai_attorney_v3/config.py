"""
Configuration for AI Attorney v3 — Clause Validation Cascade Engine.
All settings loaded from environment variables with sensible defaults.
"""

import os

# Database configuration (SQL Server primary)
DB_SERVER = os.environ.get("DB_SERVER", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "1433"))
DB_USER = os.environ.get("DB_USER", "sa")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "SeedJuraTech")

# SQLite fallback path
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "provisions.db")

# OpenAI
OPENAI_API_KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openai_api_key.txt")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
OPENAI_TEMPERATURE = 0.0

# SeedJura API (for clause fetching if running alongside portal)
SEEDJURA_API_URL = os.environ.get("SEEDJURA_API_URL", "http://localhost:8082/api")

# Processing
MAX_RERUN_PASSES = 3
CLAUSE_BATCH_SIZE = 25
FUZZY_MATCH_THRESHOLD = 0.90
FULL_CLAUSE_LOCATION_THRESHOLD = 0.85
CONTEXT_WORD_COUNT = 150

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
JOBS_DIR = os.path.join(BASE_DIR, "jobs")
STATIC_DIR = os.path.join(BASE_DIR, "static")
BLACKLIST_DIR = os.path.join(BASE_DIR, "blacklists")
WHITELIST_PATH = os.path.join(BASE_DIR, "redaction_whitelist.txt")

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)


def get_openai_api_key() -> str:
    """Load OpenAI API key from file."""
    if os.path.exists(OPENAI_API_KEY_PATH):
        with open(OPENAI_API_KEY_PATH, "r") as f:
            return f.read().strip()
    # Fall back to environment variable
    return os.environ.get("OPENAI_API_KEY", "")
