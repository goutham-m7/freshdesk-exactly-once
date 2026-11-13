"""Single-attempt worker and explicit subprocess fault-injection entry point."""

import argparse
import os
import time
from pathlib import Path
from typing import Protocol

from replay.orders import AckTimeout, OrderSystem
from replay.store import Store


class ActionTarget(Protocol):
    def execute(self, key: str, payload: str, *, lose_ack: bool = False) -> str: ...


class Worker:
    def __init__(self, store: Store, target: ActionTarget, *, lease_seconds: float):
        self.store = store
        self.target = target
        self.lease_seconds = lease_seconds

    def run_once(self, *, lose_ack: bool = False, crash_after_send: bool = False) -> str:
        claim = self.store.claim(now=time.time(), lease_seconds=self.lease_seconds)
        if claim is None:
            return "idle"
        try:
            result = self.target.execute(claim["key"], claim["payload"], lose_ack=lose_ack)
        except AckTimeout as error:
            return "retry" if self.store.retry(claim, error=str(error)) else "stale"
        if crash_after_send:
            os._exit(75)  # Intentional lab-only death: no local acknowledgement or cleanup.
        return "done" if self.store.finish(claim, result=result) else "stale"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("intake", type=Path)
    parser.add_argument("downstream", type=Path)
    parser.add_argument("--lease-seconds", type=float, default=1)
    parser.add_argument("--crash-after-send", action="store_true")
    args = parser.parse_args()
    worker = Worker(Store(args.intake), OrderSystem(args.downstream), lease_seconds=args.lease_seconds)
    print(worker.run_once(crash_after_send=args.crash_after_send))


if __name__ == "__main__":
    main()
