from concurrent.futures import ThreadPoolExecutor

import pytest

from replay.store import Store
from test_model import event


def ready(tmp_path):
    store = Store(tmp_path / "outbox.sqlite")
    store.accept(event())
    return store


def test_only_one_parallel_worker_claims(tmp_path):
    store = ready(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: store.claim(now=100, lease_seconds=10), range(16)))
    assert len([c for c in claims if c]) == 1
    assert store.actions()[0]["attempts"] == 1


def test_expired_claim_recovered_and_old_token_fenced(tmp_path):
    store = ready(tmp_path)
    first = store.claim(now=100, lease_seconds=10)
    assert store.claim(now=109.999, lease_seconds=10) is None
    second = store.claim(now=110, lease_seconds=10)
    assert first["token"] != second["token"]
    assert not store.finish(first, result="late-order")
    assert store.finish(second, result="order-1")
    row = store.actions()[0]
    assert (row["state"], row["attempts"], row["result"]) == ("done", 2, "order-1")
    assert store.claim(now=999, lease_seconds=10) is None


def test_timeout_is_auditable_and_reclaimable(tmp_path):
    store = ready(tmp_path)
    claim = store.claim(now=100, lease_seconds=10)
    assert store.retry(claim, error="acknowledgement lost")
    assert store.actions()[0]["error"] == "acknowledgement lost"
    assert store.claim(now=100, lease_seconds=10)["attempts"] == 2


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf")])
def test_invalid_lease_rejected(tmp_path, seconds):
    with pytest.raises(ValueError):
        ready(tmp_path).claim(now=100, lease_seconds=seconds)
