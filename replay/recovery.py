"""Measure restart-to-reconciliation including the remaining short lab lease."""

import subprocess
import sys
import time
from pathlib import Path

from replay.orders import OrderSystem
from replay.scenario import synthetic_action
from replay.store import Store


def measure_recovery(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    intake, orders = directory / "recovery-intake.sqlite", directory / "recovery-orders.sqlite"
    store = Store(intake)
    store.accept(synthetic_action())
    command = [sys.executable, "-m", "replay.worker", str(intake), str(orders),
               "--lease-seconds", "0.05"]
    crashed = subprocess.run(command + ["--crash-after-send"], capture_output=True, timeout=10)
    if crashed.returncode != 75:
        raise RuntimeError(f"fault worker did not reach crash boundary: {crashed.stderr!r}")
    before = store.actions()[0]
    started = time.perf_counter()
    time.sleep(max(0, before["lease_until"] - time.time()) + 0.005)
    restarted = subprocess.run(command, capture_output=True, text=True, timeout=10)
    elapsed = (time.perf_counter() - started) * 1000
    if restarted.returncode != 0 or restarted.stdout.strip() != "done":
        raise RuntimeError(f"recovery failed: {restarted.stdout!r} {restarted.stderr!r}")
    after = store.actions()[0]
    count = len(OrderSystem(orders).ledger())
    if before["state"] != "leased" or after["state"] != "done" or count != 1:
        raise RuntimeError("crash/recovery violated its exactly-one-side-effect invariant")
    return {"crash_exit": crashed.returncode, "before": before["state"],
            "after": after["state"], "orders": count, "recovery_ms": round(elapsed, 2),
            "lease_ms": 50, "includes": "remaining lease wait + fresh interpreter + reconciliation"}
