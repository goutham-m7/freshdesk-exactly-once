import subprocess
import sys
import time

from replay.orders import OrderSystem
from replay.store import Store
from replay.worker import Worker
from test_model import event


def test_timeout_retries_same_downstream_key(tmp_path):
    store = Store(tmp_path / "intake.sqlite")
    orders = OrderSystem(tmp_path / "orders.sqlite")
    store.accept(event())
    worker = Worker(store, orders, lease_seconds=1)
    assert worker.run_once(lose_ack=True) == "retry"
    assert len(orders.ledger()) == 1
    assert store.actions()[0]["state"] == "pending"
    assert worker.run_once() == "done"
    assert store.actions()[0]["attempts"] == 2
    assert len(orders.ledger()) == 1
    assert worker.run_once() == "idle"


def test_real_process_death_after_remote_commit_recovers(tmp_path):
    intake = tmp_path / "intake.sqlite"
    downstream = tmp_path / "orders.sqlite"
    Store(intake).accept(event())
    command = [sys.executable, "-m", "replay.worker", str(intake), str(downstream),
               "--lease-seconds", "0.05"]
    crash = subprocess.run(command + ["--crash-after-send"], capture_output=True, timeout=10)
    assert crash.returncode == 75, crash.stderr.decode()
    assert len(OrderSystem(downstream).ledger()) == 1
    assert Store(intake).actions()[0]["state"] == "leased"
    time.sleep(0.06)
    restart = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert restart.returncode == 0, restart.stderr
    assert restart.stdout.strip() == "done"
    assert Store(intake).actions()[0]["state"] == "done"
    assert len(OrderSystem(downstream).ledger()) == 1
