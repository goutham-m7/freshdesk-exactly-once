"""Transactional receipt ledger and one-action-per-event outbox."""

from pathlib import Path

from replay.db import connection
from replay.model import TicketAction


class Conflict(ValueError):
    """The same authorization identity carried a different action payload."""


class Store:
    def __init__(self, path: Path):
        self.path = path
        with connection(path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS actions (
                    key TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('pending','leased','done')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    token TEXT, lease_until REAL, result TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY, key TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK(decision IN ('accepted','duplicate'))
                );
            """)

    def accept(self, action: TicketAction) -> str:
        with connection(self.path, write=True) as db:
            row = db.execute("SELECT payload FROM actions WHERE key=?", (action.key,)).fetchone()
            if row and row["payload"] != action.payload:
                raise Conflict("same action identity, different payload; nothing accepted")
            decision = "duplicate" if row else "accepted"
            if not row:
                db.execute("INSERT INTO actions(key,payload,state) VALUES (?,?,'pending')",
                           (action.key, action.payload))
            db.execute("INSERT INTO receipts(key,decision) VALUES (?,?)", (action.key, decision))
            return decision

    def actions(self) -> list[dict]:
        with connection(self.path) as db:
            return [dict(row) for row in db.execute("SELECT * FROM actions ORDER BY rowid")]

    def receipts(self) -> list[dict]:
        with connection(self.path) as db:
            return [dict(row) for row in db.execute("SELECT * FROM receipts ORDER BY id")]
