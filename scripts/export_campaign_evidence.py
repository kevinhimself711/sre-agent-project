"""Export compact, redacted campaign evidence for repository review."""

import argparse
import ast
import csv
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean

SECRET_NAME = re.compile(r"(API_KEY|PASSWORD|AUTH_TOKEN|SECRET|PRIVATE_KEY)", re.I)
SECRET_VALUE = re.compile(r"(?:sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._~+/=-]{8,})")
RUN_NUMBER = re.compile(r"run_(\d+)$")


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_value(value, default=None):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value


def known_secrets():
    return [
        value for name, value in os.environ.items() if SECRET_NAME.search(name) and len(value) >= 8
    ]


def redact(value, secrets):
    if isinstance(value, dict):
        return {str(key): redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if not isinstance(value, str):
        return value
    result = value
    for secret in secrets:
        result = result.replace(secret, "[REDACTED]")
    return SECRET_VALUE.sub("[REDACTED]", result)


def read_events(run):
    path = run / "holmes.events.jsonl"
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"event": "model_capture_incomplete", "reason": "invalid_jsonl"})
    return events


def run_sort_key(path):
    match = RUN_NUMBER.search(path.name)
    return (int(match.group(1)) if match else -1, path.as_posix())


def run_directories(attempt, record):
    return sorted(
        attempt.glob(f"holmes/{record['case']}/run_*"),
        key=run_sort_key,
    )


def result_path(attempt, record):
    relative = record.get("result_file")
    if relative:
        candidate = attempt / relative
        if candidate.is_file():
            return candidate
    candidates = []
    for run in run_directories(attempt, record):
        candidates.extend(sorted(run.glob("*_results.csv")))
    return candidates[-1] if candidates else None


def first_run(attempt, record, result=None):
    if result is not None:
        return result.parent
    runs = run_directories(attempt, record)
    return runs[-1] if runs else attempt / "holmes" / record["case"] / "run_1"


def result_row(path):
    if path is None:
        return {}, "missing"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        return {}, f"row_count_{len(rows)}"
    return rows[0], "ok"


def response_tool_ids(event):
    ids = []
    response = event.get("response") or {}
    for choice in response.get("choices") or []:
        message = choice.get("message") or {}
        for tool_call in message.get("tool_calls") or []:
            if tool_call.get("id"):
                ids.append(tool_call["id"])
    return ids


def request_text(event):
    request = event.get("request") or {}
    return json.dumps(request.get("messages", []), ensure_ascii=False, sort_keys=True)


def common_prefix_length(left, right):
    length = 0
    for first, second in zip(left, right, strict=False):
        if first != second:
            break
        length += 1
    return length


def request_summaries(events):
    responses = {
        event.get("request_id"): event
        for event in events
        if event.get("event") == "model_response" and event.get("request_id")
    }
    output = []
    previous_investigation = None
    for event in events:
        if event.get("event") != "model_request":
            continue
        request_id = event.get("request_id")
        response_event = responses.get(request_id, {})
        response = response_event.get("response") or {}
        usage = response.get("usage") or {}
        prompt_details = usage.get("prompt_tokens_details") or {}
        purpose = event.get("purpose")
        current_text = request_text(event)
        prefix = (
            common_prefix_length(previous_investigation, current_text)
            if purpose == "investigation" and previous_investigation is not None
            else None
        )
        if purpose == "investigation":
            previous_investigation = current_text
        output.append(
            {
                "request_id": request_id,
                "purpose": purpose,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "cached_tokens": prompt_details.get("cached_tokens"),
                "elapsed_seconds": response_event.get("elapsed_seconds"),
                "tool_call_ids": response_tool_ids(response_event),
                "previous_investigation_common_prefix_chars": prefix,
                "response_captured": bool(response_event),
            }
        )
    return output


def tool_summaries(events, secrets):
    starts = {}
    issued_by = {}
    for event in events:
        if event.get("event") == "tool_start":
            tool_call = event.get("tool_call") or {}
            if tool_call.get("id"):
                starts[tool_call["id"]] = event.get("timestamp")
        elif event.get("event") == "model_response":
            for tool_call_id in response_tool_ids(event):
                issued_by[tool_call_id] = event.get("request_id")
    output = []
    for event in events:
        if event.get("event") != "tool_end":
            continue
        result = event.get("result") or {}
        payload = result.get("result") or {}
        data = payload.get("data", "") if isinstance(payload, dict) else payload
        data_text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        redacted_text = redact(data_text, secrets)
        call_id = result.get("tool_call_id")
        output.append(
            {
                "tool_call_id": call_id,
                "tool_name": result.get("tool_name"),
                "toolset_name": result.get("toolset_name"),
                "params": redact(
                    payload.get("params") if isinstance(payload, dict) else None,
                    secrets,
                ),
                "status": payload.get("status") if isinstance(payload, dict) else None,
                "error": redact(
                    payload.get("error") if isinstance(payload, dict) else None,
                    secrets,
                ),
                "result_length": len(data_text),
                "result_head": redacted_text[:300],
                "result_tail": redacted_text[-300:],
                "truncated": "[truncated]" in data_text[-40:],
                "elapsed_seconds": event.get("elapsed_seconds"),
                "started_at": starts.get(call_id),
                "ended_at": event.get("timestamp"),
                "issued_by_request_id": issued_by.get(call_id),
            }
        )
    return output


def prompt_snapshots(records, campaign_dir, secrets):
    snapshots = {}
    for record in sorted(records, key=lambda row: row.get("attempt_number", 0)):
        variant = record["variant"]
        if variant in snapshots:
            continue
        attempt = campaign_dir / "attempts" / Path(record["artifact_directory"]).name
        result = result_path(attempt, record)
        events = read_events(first_run(attempt, record, result))
        request_event = next((e for e in events if e.get("event") == "model_request"), None)
        if not request_event:
            continue
        request = request_event.get("request") or {}
        system_messages = [
            message.get("content")
            for message in request.get("messages", [])
            if message.get("role") == "system"
        ]
        first_user = next(
            (
                message.get("content")
                for message in request.get("messages", [])
                if message.get("role") == "user"
            ),
            None,
        )
        tools = request.get("tools", [])
        snapshots[variant] = {
            "variant": variant,
            "attempt_key": record["key"],
            "request_id": request_event.get("request_id"),
            "system_messages_sha256": sha256_text(json.dumps(system_messages, ensure_ascii=False)),
            "first_user_message_sha256": sha256_text(first_user or ""),
            "tool_schema_sha256": sha256_text(json.dumps(tools, sort_keys=True)),
            "system_messages": redact(system_messages, secrets),
            "first_user_message": redact(first_user, secrets),
            "tools": redact(tools, secrets),
        }
    return snapshots


def full_attempt(record, campaign_dir, secrets):
    attempt = campaign_dir / "attempts" / Path(record["artifact_directory"]).name
    result = result_path(attempt, record)
    row, status = result_row(result)
    events = read_events(first_run(attempt, record, result))
    finals = [event for event in events if event.get("event") == "agent_final"]
    ends = [event for event in events if event.get("event") == "episode_end"]
    reviews = [event for event in events if event.get("event") == "diagnosis_review"]
    return redact(
        {
            "schema_version": 1,
            "key": record.get("key"),
            "phase": record.get("phase"),
            "case": record.get("case"),
            "family": record.get("family"),
            "variant": record.get("variant"),
            "repeat": record.get("repeat"),
            "attempt_number": record.get("attempt_number"),
            "execution": record.get("execution"),
            "judge": record.get("judge"),
            "cleanup_ok": record.get("cleanup_ok"),
            "result_status": status,
            "diagnosis": {
                "success": parse_value(row.get("Diagnosis.success"), record.get("success")),
                "composite_score": parse_value(
                    row.get("Diagnosis.composite_score"), record.get("score")
                ),
                "dimensions": parse_value(row.get("Diagnosis.dimensions"), {}),
                "checklist": parse_value(row.get("Diagnosis.checklist"), []),
                "judgment": parse_value(row.get("Diagnosis.judgment")),
                "reasoning": parse_value(row.get("Diagnosis.reasoning")),
            },
            "final_submission": parse_value(row.get("Diagnosis.submission")),
            "review_drafts": [
                {
                    "timestamp": event.get("timestamp"),
                    "state": event.get("state"),
                    "reason": event.get("reason"),
                    "draft_request_id": event.get("draft_request_id"),
                    "iteration": event.get("iteration"),
                    "remaining_steps": event.get("remaining_steps"),
                    "draft": event.get("draft"),
                }
                for event in reviews
            ],
            "tokens": record.get("tokens", {}),
            "stop_reason": {
                "agent_final_finish_reason": finals[-1].get("finish_reason") if finals else None,
                "episode_end_state": ends[-1].get("state") if ends else None,
                "submission_state": ends[-1].get("submission_state") if ends else None,
                "returncode": record.get("returncode"),
            },
            "requests": request_summaries(events),
            "model_error_count": sum(e.get("event") == "model_error" for e in events),
            "model_capture_incomplete_count": sum(
                e.get("event") == "model_capture_incomplete" for e in events
            ),
            "tool_calls": tool_summaries(events, secrets),
            "artifacts": record.get("artifacts", {}),
        },
        secrets,
    )


def sealed_summary(records):
    groups = defaultdict(list)
    for record in records:
        groups[(record.get("phase"), record.get("case"), record.get("variant"))].append(record)
    output = []
    for (phase, case, variant), rows in sorted(groups.items()):
        successes = [row.get("success") for row in rows if isinstance(row.get("success"), bool)]
        scores = [row.get("score") for row in rows if isinstance(row.get("score"), (int, float))]
        tokens = {
            key: [
                row.get("tokens", {}).get(key)
                for row in rows
                if isinstance(row.get("tokens", {}).get(key), int)
            ]
            for key in ("input", "output", "cached")
        }
        output.append(
            {
                "phase": phase,
                "case": case,
                "variant": variant,
                "attempts": len(rows),
                "judged_attempts": len(successes),
                "successes": sum(successes),
                "success_rate": sum(successes) / len(successes) if successes else None,
                "composite_mean": mean(scores) if scores else None,
                "tokens": {
                    key: {
                        "sum": sum(values) if values else None,
                        "mean": mean(values) if values else None,
                    }
                    for key, values in tokens.items()
                },
            }
        )
    return output


def file_metadata(output_dir, names):
    return {
        name: {
            "bytes": (output_dir / name).stat().st_size,
            "sha256": hashlib.sha256((output_dir / name).read_bytes()).hexdigest(),
        }
        for name in names
    }


def export(campaign_dir, output_dir, sealed=False):
    state = json.loads((campaign_dir / "state.json").read_text(encoding="utf-8"))
    secrets = known_secrets()
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in ("attempts.jsonl", "prompt.txt", "summary.json", "manifest.json"):
        path = output_dir / stale
        if path.exists():
            path.unlink()
    written = []
    prompt_variants = []
    if sealed:
        name = "summary.json"
        (output_dir / name).write_text(
            json.dumps(
                {"schema_version": 1, "groups": sealed_summary(state["attempts"])},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        written.append(name)
    else:
        name = "attempts.jsonl"
        with (output_dir / name).open("w", encoding="utf-8") as handle:
            for record in state["attempts"]:
                handle.write(
                    json.dumps(full_attempt(record, campaign_dir, secrets), ensure_ascii=False)
                    + "\n"
                )
        written.append(name)
        snapshots = prompt_snapshots(state["attempts"], campaign_dir, secrets)
        prompt_variants = sorted(snapshots)
        name = "prompt.txt"
        with (output_dir / name).open("w", encoding="utf-8") as handle:
            handle.write(f"campaign_id: {campaign_dir.name}\n")
            handle.write("First rendered model request observed for each harness variant.\n\n")
            for variant, snapshot in snapshots.items():
                handle.write(f"===== VARIANT: {variant} =====\n")
                for key in (
                    "attempt_key",
                    "request_id",
                    "system_messages_sha256",
                    "first_user_message_sha256",
                    "tool_schema_sha256",
                ):
                    handle.write(f"{key}: {snapshot[key]}\n")
                handle.write("\n--- SYSTEM MESSAGES (JSON) ---\n")
                handle.write(json.dumps(snapshot["system_messages"], ensure_ascii=False, indent=2))
                handle.write("\n\n--- FIRST USER MESSAGE ---\n")
                handle.write(snapshot["first_user_message"] or "")
                handle.write("\n\n--- TOOL SCHEMA (JSON) ---\n")
                handle.write(json.dumps(snapshot["tools"], ensure_ascii=False, indent=2))
                handle.write("\n\n")
        prompt_path = output_dir / name
        prompt_path.write_text(
            prompt_path.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8"
        )
        written.append(name)
    manifest = {
        "schema_version": 1,
        "mode": "sealed" if sealed else "full",
        "campaign_id": campaign_dir.name,
        "source_provenance": state.get("provenance", {}),
        "attempt_count": len(state.get("attempts", [])),
        "prompt_variants": prompt_variants,
        "files": file_metadata(output_dir, written),
        "safety": {
            "raw_traces_excluded": True,
            "request_bodies_excluded_from_attempts": True,
            "full_tool_result_bodies_excluded": True,
            "package_is_not_agent_input": True,
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(redact(manifest, secrets), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sealed", action="store_true")
    args = parser.parse_args()
    manifest = export(args.campaign_dir, args.output, sealed=args.sealed)
    print(
        json.dumps(
            {
                "campaign_id": manifest["campaign_id"],
                "attempts": manifest["attempt_count"],
                "mode": manifest["mode"],
            }
        )
    )


if __name__ == "__main__":
    main()
