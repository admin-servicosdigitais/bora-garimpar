from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import DB_PATH


def initialize_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                source_query TEXT NOT NULL,
                similar_term TEXT NOT NULL,
                collected_at_utc TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def load_jobs() -> list[sqlite3.Row]:
    initialize_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """
            SELECT id, url, title, description, source_query, similar_term, collected_at_utc
            FROM jobs
            ORDER BY collected_at_utc DESC, id DESC
            """
        ).fetchall()
    finally:
        conn.close()


def insert_jobs_from_json(json_files: list[str]) -> int:
    initialize_db()
    inserted_rows = 0
    conn = sqlite3.connect(DB_PATH)
    try:
        for file_path in json_files:
            content = json.loads(Path(file_path).read_text(encoding="utf-8"))
            source_query = content.get("query", "")
            similar_term = content.get("similar_term", "")
            created_at = content.get("created_at_utc", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

            for job in content.get("jobs", []):
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs (url, title, description, source_query, similar_term, collected_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.get("url", ""),
                        job.get("title", "Sem título"),
                        job.get("description", ""),
                        source_query,
                        similar_term,
                        created_at,
                    ),
                )
                inserted_rows += cursor.rowcount
        conn.commit()
    finally:
        conn.close()

    return inserted_rows
