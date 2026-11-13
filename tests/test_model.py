import dataclasses

import pytest

from replay.model import TicketAction


def event(**changes):
    return TicketAction(**({"tenant": "demo.freshdesk.com", "ticket_id": 42,
        "conversation_id": 9, "revision": "2026-11-01T12:00:00Z",
        "action": "replacement", "order_id": "SYN-100", "quantity": 1} | changes))


def test_identity_is_stable_across_round_trip():
    original = event()
    assert TicketAction.from_dict(dataclasses.asdict(original)).key == original.key
    assert len(original.key) == 64


@pytest.mark.parametrize("changes", [
    {"tenant": "other.freshdesk.com"}, {"ticket_id": 43},
    {"conversation_id": 10}, {"revision": "revision-2"}, {"action": "refund"},
])
def test_distinct_action_identity(changes):
    assert event(**changes).key != event().key


def test_payload_is_not_identity():
    assert event(quantity=2).key == event().key
    assert event(quantity=2).payload != event().payload


@pytest.mark.parametrize("changes", [
    {"tenant": ""}, {"revision": " "}, {"ticket_id": True}, {"ticket_id": 0},
    {"conversation_id": -1}, {"quantity": 0}, {"quantity": 1.1},
    {"action": "email"}, {"order_id": ""}, {"tenant": "a" * 257},
])
def test_invalid_actions_fail_before_storage(changes):
    with pytest.raises(ValueError):
        event(**changes)


def test_unknown_fields_rejected():
    with pytest.raises(ValueError):
        TicketAction.from_dict(dataclasses.asdict(event()) | {"secret": "no"})
