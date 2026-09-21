"""Bounded sequential experiments using the upstream runner and official results."""

import argparse
import csv
import hashlib
import json
import os
import random
import signal
import subprocess
import sys
from pathlib import Path

from cluster_guard import cluster_lock, health_snapshot
from project_paths import project_root

VARIANTS = ("baseline", "review", "recovery", "combined")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_manifest(path):
    spec = json.loads(path.read_text(encoding="utf-8"))
    if (
        spec["variants"] != list(VARIANTS)
        or spec["profile"] != "full"
        or spec["stage"] != "diagnosis"
    ):
        raise ValueError("Unsupported experiment configuration")
    if spec["repetitions"] != 3 or spec["max_replacements"] != 4 or spec["enable_thinking"]:
        raise ValueError("Experiment differs from the approved finite budget")
    expected = {
        "agent_model": "openai/qwen3.8-max",
        "judge_model": "openai/qwen3.8-max",
        "max_steps": 30,
        "max_output_tokens": 8192,
        "agent_timeout": 1800,
    }
    if any(spec.get(key) != value for key, value in expected.items()):
        raise ValueError("Model or budget differs from the frozen runtime configuration")
    families = [c["family"] for cases in spec["cases"].values() for c in cases]
    if len(set(families)) != len(families):
        raise ValueError("Fault families must not cross development and validation")
    return spec


def schedule(spec, phase, candidate=None):
    variants = list(VARIANTS) if phase == "dev" else ["baseline", candidate]
    if phase == "validation" and candidate not in VARIANTS[1:]:
        raise ValueError("Validation requires a frozen non-baseline candidate")
    jobs = [
        {
            "case": case["id"],
            "family": case["family"],
            "variant": variant,
            "repeat": repeat,
            "phase": phase,
        }
        for repeat in range(1, spec["repetitions"] + 1)
        for case in spec["cases"][phase]
        for variant in variants
    ]
    random.Random(spec["seed"] + (1 if phase == "validation" else 0)).shuffle(jobs)
    for job in jobs:
        job["key"] = f"{phase}/{job['variant']}/{job['case']}/{job['repeat']}"
    return jobs


def completed(record):
    return (
        record.get("execution") in {"complete", "agent_failure"}
        and record.get("cleanup_ok") is True
        and (
            record.get("judge") == "complete"
            or (record.get("execution") == "agent_failure" and record.get("judge") == "not_run")
        )
    )


def selected_records(state, phase):
    by_key = {}
    for record in state["attempts"]:
        if record["phase"] == phase:
            by_key[record["key"]] = record
    return list(by_key.values())


def choose_candidate(records):
    summaries = {}
    for variant in VARIANTS:
        rows = [r for r in records if r["variant"] == variant and completed(r)]
        if len(rows) != 6:
            raise RuntimeError(
                f"Cannot freeze candidate with incomplete development data: {variant}"
            )
        summaries[variant] = {
            "successes": sum(r["success"] is True for r in rows),
            "score": sum(r.get("score") or 0 for r in rows) / len(rows),
            "agent_tokens": (
                sum(r["tokens"]["input"] + r["tokens"]["output"] for r in rows)
                if all(
                    isinstance(r["tokens"].get(key), int)
                    for r in rows
                    for key in ("input", "output")
                )
                else None
            ),
        }

    def rank(variant):
        row = summaries[variant]
        return (
            -row["successes"],
            -row["score"],
            row["agent_tokens"] if row["agent_tokens"] is not None else float("inf"),
            2 if variant == "combined" else 1,
            VARIANTS.index(variant),
        )

    chosen = min(VARIANTS[1:], key=rank)
    base, candidate = summaries["baseline"], summaries[chosen]
    quality = (candidate["successes"], candidate["score"])
    base_quality = (base["successes"], base["score"])
    improved = quality > base_quality or (
        quality == base_quality
        and candidate["agent_tokens"] is not None
        and base["agent_tokens"] is not None
        and candidate["agent_tokens"] < base["agent_tokens"]
    )
    if not improved:
        chosen = "recovery"
    return {"candidate": chosen, "observed_dev_improvement": improved, "summaries": summaries}


def collect_result(directory, job, returncode):
    files = list(directory.glob(f"holmes/{job['case']}/run_*/*_results.csv"))
    item = {
        **job,
        "returncode": returncode,
        "execution": "environment_failure",
        "judge": "missing",
        "data": "missing",
        "success": None,
        "score": None,
        "tokens": {},
        "cost": None,
    }
    if not files:
        return item
    with files[-1].open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        item["execution"] = "result_format_error"
        return item
    row = rows[0]

    def decoded(key, default=None):
        value = row.get(key, "")
        if value in {"True", "true"}:
            return True
        if value in {"False", "false"}:
            return False
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value or default

    item.update(
        {
            "official_run_status": row.get("run_status"),
            "official_cleanup_failed": decoded("cleanup_failed", False),
            "success": decoded("Diagnosis.success"),
            "score": decoded("Diagnosis.composite_score"),
            "phases": {k: decoded(k) for k in row if k.startswith("phase.")},
            "result_file": str(files[-1].relative_to(directory)),
        }
    )
    if isinstance(item["success"], bool):
        item["judge"] = "complete"
        item["execution"] = "complete" if row.get("run_status") == "complete" else "agent_failure"
    elif decoded("incomplete_reason") in {
        "agent_timeout",
        "agent_exited_before_all_stages_completed",
    }:
        item.update(execution="agent_failure", judge="not_run", success=False, score=0.0)
    else:
        item["execution"] = (
            "judge_failure" if row.get("run_status") == "complete" else "environment_failure"
        )
    run = files[-1].parent
    acceptance = run / "data-acceptance.json"
    if acceptance.exists():
        result = json.loads(acceptance.read_text())
        item["data"] = "complete" if not result["issues"] else "incomplete"
        item["data_issues"] = result["issues"]
    trace = run / "holmes.events.jsonl"
    if trace.exists():
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        usage = [e["response"].get("usage", {}) for e in events if e["event"] == "model_response"]
        item["tokens"] = {
            "input": sum(u.get("prompt_tokens", 0) or 0 for u in usage),
            "output": sum(u.get("completion_tokens", 0) or 0 for u in usage),
            "cached": sum(
                (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0 for u in usage
            ),
        }
        if not usage or any(
            u.get("prompt_tokens") is None or u.get("completion_tokens") is None for u in usage
        ):
            item["tokens"] = {"input": None, "output": None, "cached": None}
        item["model_calls"] = len(usage)
        tools = [e["result"] for e in events if e["event"] == "tool_end"]
        item["tool_calls"] = len(tools)
        item["rejections"] = sum(
            str(t["result"].get("data", "")).lstrip().startswith("Command Rejected") for t in tools
        )
        invocations = [
            json.dumps([t["tool_name"], t["result"].get("params")], sort_keys=True) for t in tools
        ]
        item["repeated_tool_calls"] = len(invocations) - len(set(invocations))
        item["review_events"] = [
            {k: e[k] for k in ("state", "iteration", "remaining_steps") if k in e}
            for e in events
            if e["event"] == "diagnosis_review"
        ]
    item["artifacts"] = {
        path.name: {"sha256": digest(path), "bytes": path.stat().st_size}
        for path in (files[-1], trace, acceptance, run / "sft-format-samples.jsonl")
        if path.is_file()
    }
    return item


def run_one(root, spec, job, directory):
    env = {
        **os.environ,
        "SRE_PROJECT_ROOT": str(root),
        "SRE_CLUSTER_LOCK_HELD": "1",
        "HOLMES_HARNESS": job["variant"],
        "HOLMES_MAX_STEPS": str(spec["max_steps"]),
        "SREGYM_RESULTS_DIR": str(directory),
    }
    log = directory / "runner.log"
    directory.mkdir(parents=True, exist_ok=False)
    helpers = []
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            ["bash", str(root / "scripts/run_benchmark.sh"), "holmes", job["case"], "1"],
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        # Network helpers only affect environment initialization, never the agent's permissions.
        helpers.append(
            subprocess.Popen(
                [sys.executable, str(root / "scripts/environment_helpers.py")],
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        )
        try:
            returncode = process.wait(timeout=5400)
        except BaseException:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
        finally:
            for helper in helpers:
                if helper.poll() is None:
                    os.killpg(helper.pid, signal.SIGTERM)
                    try:
                        helper.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(helper.pid, signal.SIGKILL)
                        helper.wait()
    for run in directory.glob(f"holmes/{job['case']}/run_*"):
        if (run / "holmes.events.jsonl").exists():
            subprocess.run(
                [
                    str(root / "repos/sregym/.venv/bin/python"),
                    "-m",
                    "sregym.traces.holmes_export",
                    str(run),
                ],
                cwd=root / "repos/sregym",
                env=env,
                stdout=subprocess.DEVNULL,
            )
    return collect_result(directory, job, returncode)


def run_campaign(spec, phase, destination, runner, health, provenance, resume=False):
    state_path = destination / "state.json"
    if state_path.exists():
        if not resume:
            raise RuntimeError("Campaign already exists; use --resume after inspecting state")
        state = json.loads(state_path.read_text())
        if state["provenance"] != provenance:
            raise RuntimeError("Frozen experiment provenance changed")
    else:
        state = {
            "schema_version": 1,
            "provenance": provenance,
            "attempts": [],
            "replacement_count": 0,
        }
    health()
    for unfinished in state["attempts"]:
        if unfinished.get("execution") == "running":
            # No submission is retried. The old result is reconciled at episode level.
            prior = collect_result(Path(unfinished["artifact_directory"]), unfinished, -1)
            prior["cleanup_ok"] = not prior.get("official_cleanup_failed", False)
            unfinished.update(prior)
            if not completed(unfinished):
                unfinished["execution"] = "interrupted"
    if phase == "validation" and not state.get("selection"):
        state["selection"] = choose_candidate(selected_records(state, "dev"))
    jobs = schedule(spec, phase, (state.get("selection") or {}).get("candidate"))
    atomic_json(state_path, state)
    for job in jobs:
        history = [r for r in state["attempts"] if r["key"] == job["key"]]
        if any(completed(r) for r in history):
            continue
        while True:
            if history:
                if state["replacement_count"] >= spec["max_replacements"]:
                    break
                state["replacement_count"] += 1
            health()
            number = len(state["attempts"]) + 1
            directory = destination / "attempts" / f"{number:03d}-{job['variant']}-{job['case']}"
            record = {
                **job,
                "attempt_number": number,
                "execution": "running",
                "cleanup_ok": False,
                "artifact_directory": str(directory),
            }
            state["attempts"].append(record)
            atomic_json(state_path, state)
            print(f"Starting {number}: {job['key']}", flush=True)
            result = runner(job, directory)
            record.update(result)
            try:
                record["reset_snapshot"] = health()
                record["cleanup_ok"] = not record.get("official_cleanup_failed", False)
            finally:
                atomic_json(state_path, state)
                atomic_json(destination / "summary.json", public_summary(state))
            if not record["cleanup_ok"]:
                raise RuntimeError("Cleanup failed; cluster cannot be reused")
            print(
                f"Finished {number}: execution={record['execution']} diagnosis={record.get('success')} data={record.get('data')}",
                flush=True,
            )
            if completed(record):
                break
            history.append(record)
    if (
        phase == "dev"
        and all(completed(r) for r in selected_records(state, phase))
        and len(selected_records(state, phase)) == len(jobs)
    ):
        state["selection"] = choose_candidate(selected_records(state, "dev"))
    atomic_json(state_path, state)
    return state


def public_summary(state):
    fields = {
        "key",
        "case",
        "family",
        "variant",
        "repeat",
        "phase",
        "attempt_number",
        "execution",
        "judge",
        "data",
        "success",
        "score",
        "tokens",
        "cost",
        "cleanup_ok",
        "phases",
        "model_calls",
        "tool_calls",
        "rejections",
        "repeated_tool_calls",
        "review_events",
        "artifacts",
    }
    return {
        "schema_version": 1,
        "provenance": state["provenance"],
        "selection": state.get("selection"),
        "replacement_count": state["replacement_count"],
        "attempts": [{k: v for k, v in row.items() if k in fields} for row in state["attempts"]],
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--phase", choices=("dev", "validation"), required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = project_root()
    spec = load_manifest(args.manifest)
    destination = root / "artifacts/campaigns" / spec["campaign_id"]
    if args.dry_run:
        print(json.dumps(schedule(spec, args.phase, "recovery"), indent=2))
        return
    if (
        os.environ.get("AGENT_MODEL_ID") != spec["agent_model"]
        or os.environ.get("JUDGE_MODEL_ID") != spec["judge_model"]
    ):
        raise RuntimeError("Source baseline.env first; runtime models must match the manifest")
    provenance = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "manifest_sha256": digest(args.manifest),
        "patches": json.loads((root / "patches/manifest.json").read_text()),
        "baseline_config_sha256": digest(root / "configs/baseline.env"),
        "review_prompt_sha256": digest(root / "repos/holmesgpt/holmes/core/diagnosis_review.py"),
        "agent_model": spec["agent_model"],
        "judge_model": spec["judge_model"],
        "image_id": subprocess.check_output(
            [
                "docker",
                "image",
                "inspect",
                os.environ.get("SRE_AGENT_IMAGE", "sre-holmes-agent:baseline"),
                "--format",
                "{{.Id}}",
            ],
            text=True,
        ).strip(),
    }
    with cluster_lock():
        try:
            state = run_campaign(
                spec,
                args.phase,
                destination,
                lambda job, directory: run_one(root, spec, job, directory),
                health_snapshot,
                provenance,
                args.resume,
            )
        finally:
            state_path = destination / "state.json"
            if state_path.exists():
                summary = public_summary(json.loads(state_path.read_text()))
                serialized = json.dumps(summary)
                for name, value in os.environ.items():
                    if len(value) >= 8 and any(
                        term in name for term in ("API_KEY", "PASSWORD", "AUTH_TOKEN")
                    ):
                        serialized = serialized.replace(value, "[REDACTED]")
                atomic_json(
                    root / "artifacts/publish/campaign-summary.json", json.loads(serialized)
                )
        if any(not completed(r) for r in selected_records(state, args.phase)):
            raise SystemExit("Campaign ended with missing measurements; see state.json")


if __name__ == "__main__":
    main()
