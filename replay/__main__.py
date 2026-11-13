"""Run the offline experiment without installing runtime dependencies."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from replay.recovery import measure_recovery
from replay.scenario import run_scenario


def demo() -> dict:
    with TemporaryDirectory(prefix="freshdesk-replay-") as directory:
        root = Path(directory)
        report = run_scenario(root / "comparison", redeliveries=100)
        report["recovery"] = measure_recovery(root / "restart")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    demo_parser = commands.add_parser("demo", help="100 redeliveries and a real worker restart")
    demo_parser.add_argument("--json", action="store_true", help="include complete durable ledgers")
    args = parser.parse_args()
    report = demo()
    if args.json:
        print(json.dumps(report, indent=2))
        return
    print("Freshdesk Exactly-One Action Replay")
    print("Synthetic only; no Freshdesk account, real orders, refunds, or replies.")
    print("Fault: order committed, acknowledgement timed out (synthetic 504).")
    print(f"Injected redeliveries: {report['redeliveries']}")
    print(f"Duplicate downstream effects: naive={report['naive_duplicates']} safe={report['safe_duplicates']}")
    print(f"Replay orders: naive={report['naive_replayed_orders']} safe={report['safe_replayed_orders']}")
    print(f"Distinct updates processed: {report['legitimate_updates']}/2")
    print(f"Safe total orders: {report['safe_total_orders']} (1 replayed action + 2 distinct updates)")
    print(f"Restart recovery: {report['recovery']['recovery_ms']:.2f} ms; "
          "leased -> done; downstream orders=1")
    print("Recovery includes remaining 50 ms lease + new process + reconciliation; not an SLA.")
    for item in report["timeline"]:
        print(f"  [{item['at']}] {item['event']}")
    print("Guarantee requires downstream atomic idempotency; the outbox alone is insufficient.")


if __name__ == "__main__":
    main()
