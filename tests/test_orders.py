from concurrent.futures import ThreadPoolExecutor

import pytest

from replay.orders import AckTimeout, OrderSystem
from replay.store import Conflict
from test_model import event


def test_commit_happens_before_lost_acknowledgement(tmp_path):
    path = tmp_path / "orders.sqlite"
    orders = OrderSystem(path)
    with pytest.raises(AckTimeout):
        orders.execute(event().key, event().payload, lose_ack=True)
    assert len(OrderSystem(path).ledger()) == 1
    order_id = OrderSystem(path).execute(event().key, event().payload)
    assert order_id == orders.ledger()[0]["id"]
    assert len(orders.ledger()) == 1


def test_downstream_refuses_changed_payload(tmp_path):
    orders = OrderSystem(tmp_path / "orders.sqlite")
    orders.execute(event().key, event().payload)
    with pytest.raises(Conflict):
        orders.execute(event().key, event(quantity=2).payload)
    assert len(orders.ledger()) == 1


def test_parallel_downstream_requests_reuse_one_result(tmp_path):
    orders = OrderSystem(tmp_path / "orders.sqlite")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: orders.execute(event().key, event().payload), range(20)))
    assert len(set(results)) == 1
    assert len(orders.ledger()) == 1


def test_naive_orders_do_not_gain_accidental_deduplication(tmp_path):
    orders = OrderSystem(tmp_path / "orders.sqlite")
    for _ in range(3):
        orders.execute(None, event().payload)
    assert len(orders.ledger()) == 3
