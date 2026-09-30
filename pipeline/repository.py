"""
pipeline/repository.py
───────────────────────
SQLite repository layer for pipeline persistence across runs.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from schemas.lead_schema import LeadRecord

logger = logging.getLogger(__name__)


class LeadRepository:
    """SQLite storage repository for auditable pipeline runs."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT,
                completed_at TEXT,
                metadata_json TEXT
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                company TEXT,
                website TEXT,
                industry TEXT,
                opportunity_score INTEGER,
                priority TEXT,
                qualification_status TEXT,
                lead_record_json TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            """)
            conn.commit()

    def save_run(self, run_id: str, metadata: Dict[str, Any], records: List[LeadRecord]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO runs (run_id, started_at, completed_at, metadata_json) VALUES (?, ?, ?, ?)",
                (
                    run_id,
                    metadata.get("run_timestamp"),
                    metadata.get("completed_at"),
                    json.dumps(metadata, default=str),
                ),
            )

            for rec in records:
                cursor.execute(
                    "INSERT INTO leads (run_id, company, website, industry, opportunity_score, priority, qualification_status, lead_record_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        rec.company,
                        rec.website,
                        rec.industry,
                        rec.opportunity_score,
                        rec.priority.value,
                        rec.qualification_status.value,
                        json.dumps(rec.model_dump(), default=str),
                    ),
                )
            conn.commit()
            logger.info("Repository: Saved run %s (%d leads) to SQLite", run_id, len(records))
