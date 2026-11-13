"""Optional Replaylab SDK integration. No Replaylab implementation is vendored."""

from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from replay.model import TicketAction
from replay.orders import OrderSystem
from replay.scenario import synthetic_action
from replay.store import Store
from replay.worker import Worker


def run_extension(directory: Path) -> dict:
    # Explicit optional dependency: normal demo/tests do not import this SDK.
    from replaylab import Engine, Store as TraceStore, current_session, step

    trace = TraceStore(str(directory / "trace.sqlite"))
    intake = Store(directory / "intake.sqlite")
    orders = OrderSystem(directory / "orders.sqlite")

    @step(name="freshdesk.replacement.delivery", version="1")
    def deliver(envelope: dict, lose_ack: bool) -> dict:
        decision = intake.accept(TicketAction.from_dict(envelope))
        result = Worker(intake, orders, lease_seconds=1).run_once(lose_ack=lose_ack)
        current_session().state["last_decision"] = decision
        return {"decision": decision, "worker": result, "orders": len(orders.ledger())}

    def workflow(data: dict) -> dict:
        first = deliver(data["action"], True)
        replay = deliver(data["action"], False)
        update = deliver(data["distinct_update"], False)
        return {"first": first, "redelivery": replay, "distinct": update}

    action = synthetic_action()
    data = {"action": asdict(action),
            "distinct_update": asdict(replace(action, revision="synthetic-update-2"))}
    engine = Engine(trace)
    recorded = engine.run(workflow, data, name="freshdesk-exactly-one")
    before = intake.actions()
    replayed = engine.run(workflow, data, source=recorded, mode="replay",
                          name="freshdesk-exactly-one")
    original, replay = trace.get_run(recorded), trace.get_run(replayed)
    if original["status"] != "completed" or replay["status"] != "completed":
        raise RuntimeError(f"Replaylab extension failed: {original!r} {replay!r}")
    steps = trace.steps(replayed)
    if len(steps) != 3 or any(row["origin"] != "replayed" for row in steps):
        raise RuntimeError("Replaylab did not replay all three delivery boundaries")
    if before != intake.actions() or len(orders.ledger()) != 2:
        raise RuntimeError("Trace replay unexpectedly executed a side-effect boundary")
    return {"recorded_steps": 3, "replayed_steps": len(steps),
            "additional_side_effects_during_trace_replay": 0,
            "downstream_orders": 2, "statuses": [original["status"], replay["status"]]}


def main():
    import json

    with TemporaryDirectory(prefix="freshdesk-replaylab-") as directory:
        print(json.dumps(run_extension(Path(directory)), indent=2))


if __name__ == "__main__":
    main()
