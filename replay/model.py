"""Synthetic action envelope, not an asserted Freshdesk webhook schema."""

import hashlib
import json
from dataclasses import asdict, dataclass, fields


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class TicketAction:
    tenant: str
    ticket_id: int
    conversation_id: int
    revision: str
    action: str
    order_id: str
    quantity: int

    def __post_init__(self):
        for name in ("tenant", "revision", "order_id", "action"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{name} must be a nonempty string, at most 256 chars")
        for name in ("ticket_id", "conversation_id", "quantity"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.action not in ("replacement", "refund"):
            raise ValueError("action must be replacement or refund")

    @classmethod
    def from_dict(cls, value: dict) -> "TicketAction":
        if not isinstance(value, dict) or set(value) != {f.name for f in fields(cls)}:
            raise ValueError("action fields must match the documented synthetic envelope")
        return cls(**value)

    @property
    def key(self) -> str:
        identity = ["v1", self.tenant, self.ticket_id, self.conversation_id,
                    self.revision, self.action]
        return hashlib.sha256(canonical(identity).encode()).hexdigest()

    @property
    def payload(self) -> str:
        return canonical(asdict(self))
