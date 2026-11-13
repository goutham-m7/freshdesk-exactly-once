"""Optional real-SDK tests: run explicitly with Replaylab installed or on PYTHONPATH."""

from extensions.replaylab_freshdesk import run_extension


def test_real_sdk_replays_three_boundaries_without_more_orders(tmp_path):
    result = run_extension(tmp_path)
    assert result == {
        "recorded_steps": 3,
        "replayed_steps": 3,
        "additional_side_effects_during_trace_replay": 0,
        "downstream_orders": 2,
        "statuses": ["completed", "completed"],
    }
