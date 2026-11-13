"""Transactional receipt ledger and one-action-per-event outbox."""

import math
import uuid
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

    def claim(self, *, now: float, lease_seconds: float) -> dict | None:
        if not math.isfinite(now) or not math.isfinite(lease_seconds) or lease_seconds <= 0:
            raise ValueError("clock and positive lease must be finite")
        with connection(self.path, write=True) as db:
            row = db.execute(
                "SELECT * FROM actions WHERE state='pending' OR "
                "(state='leased' AND lease_until<=?) ORDER BY rowid LIMIT 1", (now,)
            ).fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            db.execute(
                "UPDATE actions SET state='leased',token=?,lease_until=?,attempts=attempts+1 "
                "WHERE key=?", (token, now + lease_seconds, row["key"])
            )
            return dict(db.execute("SELECT * FROM actions WHERE key=?", (row["key"],)).fetchone())

    def finish(self, claim: dict, *, result: str) -> bool:
        with connection(self.path, write=True) as db:
            return db.execute(
                "UPDATE actions SET state='done',result=?,error=NULL,token=NULL,lease_until=NULL "
                "WHERE key=? AND token=? AND state='leased'",
                (result, claim["key"], claim["token"])
            ).rowcount == 1

    def retry(self, claim: dict, *, error: str) -> bool:
        with connection(self.path, write=True) as db:
            return db.execute(
                "UPDATE actions SET state='pending',error=?,token=NULL,lease_until=NULL "
                "WHERE key=? AND token=? AND state='leased'",
                (error, claim["key"], claim["token"])
            ).rowcount == 1
