# ai-generated: 90% - Claude Code drafted, reviewed by the student
"""SQLite persistence: one row per ticket, the ticket itself stored as JSON."""
import json
import os
import sqlite3
import threading

DB_PATH = os.environ.get("SVCDESK_DB", "/data/svcdesk.db")


class Store:
    def __init__(self, path: str = DB_PATH):
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self._db.commit()

    def put(self, ticket: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO tickets (id, body) VALUES (?, ?)",
                (ticket["id"], json.dumps(ticket)),
            )
            self._db.commit()

    def get(self, ticket_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT body FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT body FROM tickets").fetchall()
        return [json.loads(row[0]) for row in rows]
