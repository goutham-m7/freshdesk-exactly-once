import pytest

from replay.scenario import run_scenario


@pytest.mark.parametrize("redeliveries", [1, 2, 100])
def test_comparison_counts_and_legitimate_updates(tmp_path, redeliveries):
    report = run_scenario(tmp_path, redeliveries=redeliveries)
    assert report["naive_duplicates"] == redeliveries
    assert report["safe_duplicates"] == 0
    assert report["naive_replayed_orders"] == redeliveries + 1
    assert report["safe_replayed_orders"] == 1
    assert report["legitimate_updates"] == 2
    assert report["safe_total_orders"] == 3
    assert len(report["actions"]) == 3
    assert all(a["state"] == "done" for a in report["actions"])
    assert report["actions"][0]["attempts"] == 2
    assert len(report["receipts"]) == redeliveries + 3
    assert any("504" in item["event"] for item in report["timeline"])


@pytest.mark.parametrize("count", [0, -1, 1001, True, 1.5])
def test_unbounded_runs_rejected(tmp_path, count):
    with pytest.raises(ValueError):
        run_scenario(tmp_path, redeliveries=count)


def test_existing_run_not_silently_reused(tmp_path):
    run_scenario(tmp_path, redeliveries=1)
    with pytest.raises(FileExistsError):
        run_scenario(tmp_path, redeliveries=1)
