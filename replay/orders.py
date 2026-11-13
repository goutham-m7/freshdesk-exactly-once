"""Synthetic downstream service with its own atomic idempotency contract."""

from pathlib import Path

from replay.db import connection
from replay.store import Conflict


class AckTimeout(TimeoutError):
    """The downstream commit succeeded but the caller did not receive its result."""


class OrderSystem:
    def __init__(self, path: Path):
        self.path = path
        with connection(path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS orders ("
                       "id INTEGER PRIMARY KEY, key TEXT UNIQUE, payload TEXT NOT NULL)")

    def execute(self, key: str | None, payload: str, *, lose_ack: bool = False) -> str:
        # SQLite permits many NULL keys: the naive path deliberately has no identity.
        with connection(self.path, write=True) as db:
            row = db.execute("SELECT * FROM orders WHERE key=?", (key,)).fetchone()
            if row:
                if row["payload"] != payload:
                    raise Conflict("downstream key already committed a different payload")
                order_id = row["id"]
            else:
                order_id = db.execute("INSERT INTO orders(key,payload) VALUES (?,?)",
                                      (key, payload)).lastrowid
        # Must happen AFTER commit, never inside the transaction.
        if lose_ack:
            raise AckTimeout("order committed; acknowledgement timed out (synthetic 504)")
        return f"order-{order_id:04d}"

    def ledger(self) -> list[dict]:
        with connection(self.path) as db:
            return [{"id": f"order-{row['id']:04d}", "key": row["key"],
                     "payload": row["payload"]}
                    for row in db.execute("SELECT * FROM orders ORDER BY id")]
