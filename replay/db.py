"""Short-lived, real SQLite transactions; no network work under these locks."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connection(path: Path, *, write: bool = False):
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        if write:
            db.execute("BEGIN IMMEDIATE")
        with db:
            yield db
    finally:
        db.close()
