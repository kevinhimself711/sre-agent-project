import copy
import json
from pathlib import Path

import pytest
from campaign import (
    choose_candidate,
    collect_result,
    completed,
    load_manifest,
    run_campaign,
    schedule,
)
from cluster_guard import cluster_lock
from filelock import Timeout

SPEC = load_manifest(Path(__file__).resolve().parents[1] / "configs/campaign-20260921.json")


def success(job, directory):
    return {
        **job,
        "execution": "complete",
        "judge": "complete",
        "data": "complete",
        "success": True,
        "score": 1.0,
        "tokens": {"input": 10, "output": 2},
    }


def test_deterministic_bounded_matrix():
    assert schedule(SPEC, "dev") == schedule(SPEC, "dev")
    assert len(schedule(SPEC, "dev")) == 24
    assert len(schedule(SPEC, "validation", "recovery")) == 12
    assert len({j["key"] for j in schedule(SPEC, "dev")}) == 24


def test_completed_attempts_are_not_repeated(tmp_path):
    state = run_campaign(SPEC, "dev", tmp_path, success, lambda: {}, {"commit": "a"})
    assert len(state["attempts"]) == 24

    def must_not_run(*args):
        raise AssertionError("Completed job repeated")

    again = run_campaign(
        SPEC, "dev", tmp_path, must_not_run, lambda: {}, {"commit": "a"}, resume=True
    )
    assert len(again["attempts"]) == 24
    assert again["selection"]["candidate"] == "recovery"


def test_cleanup_failure_stops_the_next_case(tmp_path):
    calls = []

    def dirty(job, directory):
        calls.append(job)
        return {**success(job, directory), "official_cleanup_failed": True}

    with pytest.raises(RuntimeError, match="Cleanup failed"):
        run_campaign(SPEC, "dev", tmp_path, dirty, lambda: {}, {})
    assert len(calls) == 1
    assert not json.loads((tmp_path / "state.json").read_text())["attempts"][0]["cleanup_ok"]


def test_interruption_is_durable_and_resume_checks_health(tmp_path):
    def interrupt(*args):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_campaign(SPEC, "dev", tmp_path, interrupt, lambda: {}, {})
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["attempts"][0]["execution"] == "running"

    def unhealthy():
        raise RuntimeError("dirty cluster")

    with pytest.raises(RuntimeError, match="dirty cluster"):
        run_campaign(SPEC, "dev", tmp_path, success, unhealthy, {}, resume=True)
    state = run_campaign(SPEC, "dev", tmp_path, success, lambda: {}, {}, resume=True)
    assert len(state["attempts"]) == 25
    assert state["replacement_count"] == 1


def test_replacements_have_one_campaign_wide_limit(tmp_path):
    def failure(job, directory):
        return {**job, "execution": "environment_failure", "judge": "missing"}

    state = run_campaign(SPEC, "dev", tmp_path, failure, lambda: {}, {})
    assert state["replacement_count"] == 4
    assert len(state["attempts"]) == 28
    assert not state.get("selection")


def test_agent_failure_counts_as_an_observation():
    assert completed({"execution": "agent_failure", "judge": "complete", "cleanup_ok": True})
    assert completed({"execution": "agent_failure", "judge": "not_run", "cleanup_ok": True})


def test_official_timeout_counts_as_failure_without_inventing_judge(tmp_path):
    job = schedule(SPEC, "dev")[0]
    run = tmp_path / "holmes" / job["case"] / "run_1"
    run.mkdir(parents=True)
    (run / f"{job['case']}_results.csv").write_text(
        "run_status,incomplete_reason,timed_out\nincomplete,agent_timeout,True\n"
    )
    result = collect_result(tmp_path, job, 1)
    assert result["success"] is False
    assert result["judge"] == "not_run"
    assert result["execution"] == "agent_failure"


def test_frozen_configuration_cannot_drift(tmp_path):
    run_campaign(SPEC, "dev", tmp_path, success, lambda: {}, {"commit": "a"})
    with pytest.raises(RuntimeError, match="provenance changed"):
        run_campaign(SPEC, "dev", tmp_path, success, lambda: {}, {"commit": "b"}, resume=True)


def test_missing_usage_is_not_zero_cost_improvement():
    records = []
    for job in schedule(SPEC, "dev"):
        row = {**success(job, None), "cleanup_ok": True}
        if job["variant"] == "review":
            row["tokens"] = {}
        records.append(row)
    result = choose_candidate(records)
    assert result["summaries"]["review"]["agent_tokens"] is None
    assert result["candidate"] == "recovery"
    assert result["observed_dev_improvement"] is False


def test_cli_and_workflow_share_exclusive_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("SRE_CLUSTER_LOCK", str(tmp_path / "cluster.lock"))
    with cluster_lock():
        with pytest.raises(Timeout):
            with cluster_lock():
                pass


def test_fault_families_cannot_cross_splits(tmp_path):
    spec = copy.deepcopy(SPEC)
    spec["cases"]["validation"][0]["family"] = spec["cases"]["dev"][0]["family"]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="families"):
        load_manifest(path)
