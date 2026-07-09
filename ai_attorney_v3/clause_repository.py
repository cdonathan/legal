"""
Clause database access layer with SQL Server primary and SQLite fallback.
Retrieves attorney-approved clauses filtered by document type.
"""

import os
import re
import sqlite3
import logging
from typing import Optional

from models import ClauseRecord
from text_utils import clean_clause_html
import config

logger = logging.getLogger(__name__)


class ClauseRepository:
    """Unified interface to clause database with automatic failover."""

    def __init__(self, sql_config: Optional[dict] = None, sqlite_path: Optional[str] = None):
        self.sql_config = sql_config or {
            "server": config.DB_SERVER,
            "port": config.DB_PORT,
            "user": config.DB_USER,
            "password": config.DB_PASSWORD,
            "database": config.DB_NAME,
        }
        self.sqlite_path = sqlite_path or config.SQLITE_PATH
        self._connection_mode = "sql_server"
        self._sql_available = True

    def get_clauses_by_form_type(self, form_type: str) -> list[ClauseRecord]:
        """
        Retrieve all clauses for a document type.
        Tries SQL Server first, falls back to SQLite on failure.
        """
        form_type_upper = form_type.strip().upper()

        # Try SQL Server first
        if self._sql_available:
            try:
                clauses = self._fetch_from_sql_server(form_type_upper)
                self._connection_mode = "sql_server"
                logger.info(f"Fetched {len(clauses)} clauses from SQL Server for {form_type_upper}")
                return clauses
            except Exception as e:
                logger.warning(f"SQL Server failed, falling back to SQLite: {e}")
                self._sql_available = False

        # SQLite fallback
        clauses = self._fetch_from_sqlite(form_type_upper)
        self._connection_mode = "sqlite"
        logger.info(f"Fetched {len(clauses)} clauses from SQLite for {form_type_upper}")
        return clauses

    def get_clause_by_id(self, clause_id: int, form_type: str, clauses: Optional[list[ClauseRecord]] = None) -> Optional[ClauseRecord]:
        """
        Retrieve a single clause by its position index (1-based) within the form_type set.
        If clauses list is provided, uses that directly (avoids extra DB call).
        """
        if clauses:
            if 1 <= clause_id <= len(clauses):
                return clauses[clause_id - 1]
            return None

        all_clauses = self.get_clauses_by_form_type(form_type)
        if 1 <= clause_id <= len(all_clauses):
            return all_clauses[clause_id - 1]
        return None

    def get_clause_text(self, clause: ClauseRecord) -> str:
        """Get clean text from a clause record. Uses cached clean_text if available."""
        if clause.clean_text:
            return clause.clean_text
        clause.clean_text = clean_clause_html(clause.html_data_text)
        return clause.clean_text

    def get_connection_mode(self) -> str:
        """Return current connection mode for status reporting."""
        return self._connection_mode

    def _fetch_from_sql_server(self, form_type: str) -> list[ClauseRecord]:
        """Query SQL Server for clauses by form_type."""
        import pymssql

        conn = pymssql.connect(**self.sql_config)
        cur = conn.cursor(as_dict=True)
        cur.execute(
            "SELECT * FROM provisions WHERE form_type = %s ORDER BY category_id, risk_level DESC",
            (form_type,)
        )
        rows = cur.fetchall()
        conn.close()

        return [self._row_to_clause(row, idx) for idx, row in enumerate(rows, 1)]

    def _fetch_from_sqlite(self, form_type: str) -> list[ClauseRecord]:
        """Query SQLite fallback for clauses by form_type."""
        if not os.path.exists(self.sqlite_path):
            logger.error(f"SQLite database not found: {self.sqlite_path}")
            return []

        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM provisions WHERE form_type = ? ORDER BY category_id, risk_level DESC",
            (form_type,)
        ).fetchall()
        conn.close()

        return [self._row_to_clause(dict(row), idx) for idx, row in enumerate(rows, 1)]

    def _row_to_clause(self, row: dict, position_id: int) -> ClauseRecord:
        """Convert a database row to a ClauseRecord, handling column name variations."""
        # Handle various column name casings from different DB drivers
        html = (
            row.get("HTML_DATA_TEXT") or row.get("htmL_DATA_TEXT") or
            row.get("html_data_text") or row.get("HTML_DATA") or
            row.get("htmL_DATA") or row.get("html_data") or ""
        )
        desc = (
            row.get("PROV_DESC") or row.get("proV_DESC") or
            row.get("prov_desc") or ""
        )
        risk = (
            row.get("RISK_LEVEL") or row.get("risK_LEVEL") or
            row.get("risk_level") or ""
        )
        form_type = (
            row.get("form_type") or row.get("FORM_TYPE") or
            row.get("forM_TYPE") or ""
        )
        category_id = (
            row.get("category_id") or row.get("CATEGORY_ID") or
            row.get("categorY_ID") or 0
        )

        clean_text = clean_clause_html(html)

        return ClauseRecord(
            id=position_id,
            form_type=form_type,
            category_id=int(category_id) if category_id else 0,
            prov_desc=desc,
            html_data_text=html,
            clean_text=clean_text,
            risk_level=risk
        )

    def get_rules(self, form_type: str) -> dict:
        """Retrieve rules JSON for a form_type (if available in DB)."""
        form_type_upper = form_type.strip().upper()

        # Try SQLite (rules table)
        if os.path.exists(self.sqlite_path):
            try:
                import json
                conn = sqlite3.connect(self.sqlite_path)
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT rules_json FROM rules WHERE form_type = ?",
                    (form_type_upper,)
                ).fetchone()
                conn.close()
                if row:
                    return json.loads(row["rules_json"])
            except Exception as e:
                logger.debug(f"No rules table or parse error: {e}")

        return {"patterns": []}
