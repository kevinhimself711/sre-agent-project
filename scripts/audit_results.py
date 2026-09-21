"""Summarize official scores and validate real Holmes exports without re-running cases."""

import argparse
import ast
import csv
import hashlib
import json
from collections import Counter

from llm_backend.usage_log import summarize_usage
from project_paths import project_root
from sregym.traces import store
from sregym.traces.holmes_export import export_run
from sregym.traces.postprocess import write_trajectory

ROOT = project_root()


def decode(value):
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    results = ROOT / "repos/sregym/results"
    rows, sessions = [], []
    for csv_path in sorted(results.glob("*/*/*/run_*/*_results.csv")):
        run = csv_path.parent
        with csv_path.open() as handle:
            records = list(csv.DictReader(handle))
        if len(records) != 1:
            raise RuntimeError(f"Unexpected official row count: {csv_path}")
        row = records[0]
        item = {
            "path": str(run.relative_to(results)),
            "agent": run.parent.parent.name,
            "case": run.parent.name,
            "run_status": row.get("run_status"),
            "success": decode(row.get("Diagnosis.success", "None")),
            "composite_score": decode(row.get("Diagnosis.composite_score", "None")),
            "cleanup_failed": decode(row.get("cleanup_failed", "False")),
            "ttl_seconds": decode(row.get("TTL", "None")),
            "phases": {k: decode(v) for k, v in row.items() if k.startswith("phase.")},
            "cost_usd": None,
            "cost_status": "billing unavailable",
        }
        trajectory_path = write_trajectory(run)
        if trajectory_path:
            trajectory = json.loads(trajectory_path.read_text())
            item["metrics"] = trajectory.get("final_metrics")
        if item["agent"] == "stratus":
            item["all_agent_usage"] = summarize_usage(run / "stratus_usage.jsonl")
        if item["agent"] == "holmes":
            acceptance = export_run(run)
            first = (run / "sft-format-samples.jsonl").read_bytes()
            export_run(run)
            assert first == (run / "sft-format-samples.jsonl").read_bytes(), (
                "Export changed on repetition"
            )
            item["data_acceptance"] = acceptance
            events = [
                json.loads(line) for line in (run / "holmes.events.jsonl").read_text().splitlines()
            ]
            session_id = next(e["session_id"] for e in events if e["event"] == "episode_start")
            sessions.append(session_id)
            item["session_id"] = session_id
            item["model_calls"] = sum(e["event"] == "model_request" for e in events)
            item["tool_calls"] = sum(e["event"] == "tool_start" for e in events)
            item["model_seconds"] = sum(
                e.get("elapsed_seconds", 0) for e in events if e["event"] == "model_response"
            )
            item["tool_seconds"] = sum(
                e.get("elapsed_seconds", 0) for e in events if e["event"] == "tool_end"
            )
            effective_inputs = json.dumps(
                [e["request"]["messages"] for e in events if e["event"] == "model_request"]
            )
            assert not any(
                case_id in effective_inputs
                for case_id in (
                    "network_policy_block",
                    "wrong_service_selector_social_network",
                )
            ), "Case ID present in a model-visible request"
            item["case_id_leak_check"] = "passed"
            item["sft_sha256"] = hashlib.sha256(first).hexdigest()
        rows.append(item)
    assert len(sessions) == len(set(sessions)), "Session reused across attempts"
    if args.final:
        assert Counter((r["agent"], r["case"]) for r in rows) == {
            ("stratus", "network_policy_block"): 1,
            ("holmes", "network_policy_block"): 2,
            ("holmes", "wrong_service_selector_social_network"): 1,
        }, "Campaign differs from the approved finite case count"
        assert all(r["run_status"] == "complete" and not r["cleanup_failed"] for r in rows)
        assert all(not r["data_acceptance"]["issues"] for r in rows if r["agent"] == "holmes")
    db = results / "traces.db"
    store.ingest_tree(results, db)
    with store.connect(db) as conn:
        before = conn.execute("SELECT count(*) FROM trajectories").fetchone()[0]
    store.ingest_tree(results, db)
    with store.connect(db) as conn:
        after = conn.execute("SELECT count(*) FROM trajectories").fetchone()[0]
    assert before == after, "Repeated ingestion created duplicates"
    summary = {
        "schema_version": 1,
        "runs": rows,
        "sqlite_rows": after,
        "idempotent_ingestion": True,
        "unique_holmes_sessions": len(sessions),
    }
    (ROOT / "artifacts/results-audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
