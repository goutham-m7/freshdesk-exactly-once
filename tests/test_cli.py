import json
import subprocess
import sys

from replay.recovery import measure_recovery


def test_recovery_metric_observes_a_new_process(tmp_path):
    result = measure_recovery(tmp_path)
    assert result["crash_exit"] == 75
    assert result["before"] == "leased"
    assert result["after"] == "done"
    assert result["orders"] == 1
    assert result["recovery_ms"] > 0


def test_demo_json_exposes_measured_metrics_and_ledger():
    run = subprocess.run([sys.executable, "-m", "replay", "demo", "--json"],
                         capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, run.stderr
    data = json.loads(run.stdout)
    assert data["safe_duplicates"] == 0
    assert data["naive_duplicates"] == 100
    assert data["recovery"]["orders"] == 1
    assert len(data["actions"]) == 3


def test_default_demo_is_human_readable():
    run = subprocess.run([sys.executable, "-m", "replay", "demo"],
                         capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, run.stderr
    assert "naive=100 safe=0" in run.stdout
    assert "Distinct updates processed: 2/2" in run.stdout
    assert "Synthetic only" in run.stdout
