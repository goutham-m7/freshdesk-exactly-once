"""Repeatable naive versus durable replay against independent SQLite ledgers."""

from dataclasses import replace
from pathlib import Path

from replay.model import TicketAction
from replay.orders import AckTimeout, OrderSystem
from replay.store import Store
from replay.worker import Worker


def synthetic_action() -> TicketAction:
    return TicketAction(tenant="demo.freshdesk.com", ticket_id=4201,
                        conversation_id=701, revision="synthetic-update-1",
                        action="replacement", order_id="SYNTHETIC-ORDER-17", quantity=1)


def run_scenario(directory: Path, *, redeliveries: int) -> dict:
    if type(redeliveries) is not int or not 1 <= redeliveries <= 1000:
        raise ValueError("redeliveries must be an integer from 1 through 1000")
    # Never report a fresh experiment while quietly reusing previous side effects.
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / "run-started"
    with marker.open("x"):
        pass
    naive = OrderSystem(directory / "naive.sqlite")
    safe = OrderSystem(directory / "safe-orders.sqlite")
    store = Store(directory / "intake.sqlite")
    worker = Worker(store, safe, lease_seconds=1)
    action = synthetic_action()
    store.accept(action)
    try:
        naive.execute(None, action.payload, lose_ack=True)
    except AckTimeout:
        pass  # Naive receiver cannot tell whether this order committed.
    assert worker.run_once(lose_ack=True) == "retry"
    timeline = [
        {"at": "delivery 1", "event": "replacement committed in both downstream ledgers"},
        {"at": "fault", "event": "504: acknowledgement lost AFTER downstream commit"},
    ]
    for _ in range(redeliveries):
        naive.execute(None, action.payload)
        store.accept(action)
        worker.run_once()
    naive_count, safe_count = len(naive.ledger()), len(safe.ledger())
    timeline.append({"at": f"{redeliveries} redeliveries", "event":
                     f"naive={naive_count} orders; safe={safe_count}; "
                     "same action key, same payload: receipt deduplicated; "
                     "outbox retried original key; downstream returned original order"})
    for revision in ("synthetic-update-2", "synthetic-update-3"):
        store.accept(replace(action, revision=revision))
        assert worker.run_once() == "done"
    timeline.append({"at": "distinct updates", "event":
                     "2 new revisions accepted on the same ticket: 2 new authorizations, 2 orders"})
    return {
        "redeliveries": redeliveries, "naive_duplicates": naive_count - 1,
        "safe_duplicates": safe_count - 1, "naive_replayed_orders": naive_count,
        "safe_replayed_orders": safe_count, "legitimate_updates": 2,
        "safe_total_orders": len(safe.ledger()), "actions": store.actions(),
        "receipts": store.receipts(), "naive_ledger": naive.ledger(),
        "safe_ledger": safe.ledger(), "timeline": timeline,
    }
