from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    ensure_schema(connection)
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS outbound_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method TEXT NOT NULL DEFAULT 'POST',
            path TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_outbound_requests_created_at ON outbound_requests(created_at, id)"
    )
    connection.commit()


def enqueue_post(db_path: Path, path: str, payload: dict[str, Any]) -> int:
    with closing(connect(db_path)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO outbound_requests (method, path, payload_json)
            VALUES ('POST', ?, ?)
            """,
            (path, json.dumps(payload, separators=(",", ":"), ensure_ascii=False)),
        )
        connection.commit()
        return int(cursor.lastrowid)


def read_outbound_batch(db_path: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    with closing(connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, method, path, payload_json, attempts
            FROM outbound_requests
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    batch: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(str(row["payload_json"]))
        except Exception:
            payload = {}
        batch.append(
            {
                "id": int(row["id"]),
                "method": str(row["method"]),
                "path": str(row["path"]),
                "payload": payload,
                "attempts": int(row["attempts"]),
            }
        )
    return batch


def mark_sent(db_path: Path, request_id: int) -> None:
    with closing(connect(db_path)) as connection:
        connection.execute("DELETE FROM outbound_requests WHERE id = ?", (request_id,))
        connection.commit()


def record_failure(db_path: Path, request_id: int, error: str) -> None:
    with closing(connect(db_path)) as connection:
        connection.execute(
            """
            UPDATE outbound_requests
            SET attempts = attempts + 1,
                last_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (error[:500], request_id),
        )
        connection.commit()


def clear_outbound_requests(db_path: Path) -> None:
    with closing(connect(db_path)) as connection:
        connection.execute("DELETE FROM outbound_requests")
        connection.commit()


def pending_count(db_path: Path) -> int:
    with closing(connect(db_path)) as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM outbound_requests").fetchone()
    return int(row["total"] if row else 0)
