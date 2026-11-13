from concurrent.futures import ThreadPoolExecutor

import pytest

from replay.store import Conflict, Store
from test_model import event


def test_acceptance_is_durable_and_duplicates_are_explained(tmp_path):
    path = tmp_path / "intake.sqlite"
    assert Store(path).accept(event()) == "accepted"
    assert Store(path).accept(event()) == "duplicate"
    rows = Store(path).actions()
    assert len(rows) == 1
    assert rows[0]["state"] == "pending"
    assert [r["decision"] for r in Store(path).receipts()] == ["accepted", "duplicate"]


def test_changed_payload_rolls_back_receipt_and_outbox(tmp_path):
    store = Store(tmp_path / "intake.sqlite")
    store.accept(event())
    with pytest.raises(Conflict):
        store.accept(event(quantity=2))
    assert len(store.receipts()) == 1
    assert len(store.actions()) == 1


def test_distinct_updates_survive_ticket_dedupe(tmp_path):
    store = Store(tmp_path / "intake.sqlite")
    for rev in ("a", "b", "c"):
        assert store.accept(event(revision=rev)) == "accepted"
    assert len(store.actions()) == 3


def test_parallel_deliveries_create_one_outbox_row(tmp_path):
    store = Store(tmp_path / "intake.sqlite")
    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(pool.map(lambda _: store.accept(event()), range(30)))
    assert decisions.count("accepted") == 1
    assert decisions.count("duplicate") == 29
    assert len(store.receipts()) == 30
    assert len(store.actions()) == 1
