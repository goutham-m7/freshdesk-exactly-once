import sqlite3

import pytest

from replay.db import connection
from replay.orders import OrderSystem
from replay.store import Conflict, Store
from replay.worker import Worker
from test_model import event


def test_receipt_write_failure_rolls_back_outbox(tmp_path):
    store = Store(tmp_path / "intake.sqlite")
    with connection(store.path) as db:
        db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON receipts "
                   "BEGIN SELECT RAISE(ABORT, 'synthetic disk write failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="synthetic disk write failure"):
        store.accept(event())
    assert store.actions() == []
    assert store.receipts() == []


def test_downstream_conflict_is_not_marked_successful_or_blindly_retried(tmp_path):
    store = Store(tmp_path / "intake.sqlite")
    orders = OrderSystem(tmp_path / "orders.sqlite")
    orders.execute(event().key, event(quantity=2).payload)
    store.accept(event())
    with pytest.raises(Conflict):
        Worker(store, orders, lease_seconds=30).run_once()
    assert store.actions()[0]["state"] == "leased"
    assert store.actions()[0]["result"] is None
    assert len(orders.ledger()) == 1


def test_quoted_source_identity_is_data_not_sql(tmp_path):
    store = Store(tmp_path / "intake.sqlite")
    store.accept(event(revision="'; DROP TABLE actions; --"))
    store.accept(event())
    assert len(store.actions()) == 2
