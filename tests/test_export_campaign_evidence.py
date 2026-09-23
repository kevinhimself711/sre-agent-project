import csv
import json

from export_campaign_evidence import export


def write_jsonl(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def write_result(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "Diagnosis.success",
        "Diagnosis.composite_score",
        "Diagnosis.dimensions",
        "Diagnosis.checklist",
        "Diagnosis.judgment",
        "Diagnosis.reasoning",
        "Diagnosis.submission",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def make_campaign(tmp_path):
    campaign = tmp_path / "campaigns" / "synthetic"
    attempt = campaign / "attempts" / "001-baseline-case"
    run = attempt / "holmes" / "case" / "run_1"
    events = [
        {
            "event": "model_request",
            "request_id": "req-1",
            "purpose": "investigation",
            "request": {
                "messages": [
                    {"role": "system", "content": "system one"},
                    {"role": "system", "content": "system two"},
                    {"role": "user", "content": "user question"},
                ],
                "tools": [{"type": "function", "function": {"name": "inspect"}}],
            },
        },
        {
            "event": "model_response",
            "request_id": "req-1",
            "elapsed_seconds": 1.25,
            "response": {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "prompt_tokens_details": {"cached_tokens": 5},
                },
                "choices": [{"message": {"tool_calls": [{"id": "call-1"}]}}],
            },
        },
        {
            "event": "tool_start",
            "timestamp": "2026-01-01T00:00:01Z",
            "tool_call": {"id": "call-1"},
        },
        {
            "event": "tool_end",
            "timestamp": "2026-01-01T00:00:02Z",
            "elapsed_seconds": 0.75,
            "result": {
                "tool_call_id": "call-1",
                "tool_name": "inspect",
                "toolset_name": "synthetic",
                "result": {
                    "status": "success",
                    "params": {"q": "x"},
                    "data": "head " + ("middle " * 20) + "tail [truncated]",
                },
            },
        },
        {
            "event": "diagnosis_review",
            "state": "skipped",
            "reason": "disabled",
            "draft_request_id": "draft-1",
        },
        {
            "event": "model_request",
            "request_id": "req-2",
            "purpose": "investigation",
            "request": {"messages": [{"role": "user", "content": "user question plus"}]},
        },
        {
            "event": "model_response",
            "request_id": "req-2",
            "elapsed_seconds": 2.5,
            "response": {
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 4,
                    "prompt_tokens_details": {"cached_tokens": 7},
                },
                "choices": [{"message": {"tool_calls": []}}],
            },
        },
        {"event": "model_error"},
        {"event": "model_capture_incomplete"},
        {"event": "agent_final", "finish_reason": "stop"},
        {"event": "episode_end", "state": "finished", "submission_state": "acknowledged"},
    ]
    write_jsonl(run / "holmes.events.jsonl", events)
    write_result(
        run / "case_results.csv",
        [
            {
                "Diagnosis.success": "True",
                "Diagnosis.composite_score": "0.75",
                "Diagnosis.dimensions": "{'D1': {'score': 0.75}}",
                "Diagnosis.checklist": "[{'id': 'D1-Q1', 'answer': 'Yes', 'evidence': 'seen'}]",
                "Diagnosis.judgment": "True",
                "Diagnosis.reasoning": "reasoning text",
                "Diagnosis.submission": "final diagnosis",
            }
        ],
    )
    bad = campaign / "attempts" / "002-baseline-bad" / "holmes" / "bad" / "run_1"
    write_result(
        bad / "bad_results.csv", [{"Diagnosis.success": "True"}, {"Diagnosis.success": "False"}]
    )
    state = {
        "provenance": {"commit": "abc"},
        "attempts": [
            {
                "key": "dev/baseline/case/1",
                "phase": "dev",
                "case": "case",
                "family": "family",
                "variant": "baseline",
                "repeat": 1,
                "attempt_number": 1,
                "execution": "complete",
                "judge": "complete",
                "cleanup_ok": True,
                "success": True,
                "score": 0.75,
                "tokens": {"input": 30, "output": 7, "cached": 12},
                "artifact_directory": "/remote/attempts/001-baseline-case",
                "result_file": "holmes/case/run_1/case_results.csv",
            },
            {
                "key": "dev/baseline/bad/1",
                "phase": "dev",
                "case": "bad",
                "family": "family",
                "variant": "baseline",
                "repeat": 1,
                "attempt_number": 2,
                "execution": "result_format_error",
                "judge": "missing",
                "cleanup_ok": True,
                "success": None,
                "score": None,
                "tokens": {},
                "artifact_directory": "/remote/attempts/002-baseline-bad",
                "result_file": "holmes/bad/run_1/bad_results.csv",
            },
        ],
    }
    (campaign / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return campaign


def test_full_export_contains_evidence_without_request_bodies(tmp_path):
    campaign = make_campaign(tmp_path)
    output = tmp_path / "evidence"
    manifest = export(campaign, output)

    assert manifest["mode"] == "full"
    rows = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
    first = rows[0]
    assert first["result_status"] == "ok"
    assert first["diagnosis"]["reasoning"] == "reasoning text"
    assert first["review_drafts"][0]["state"] == "skipped"
    assert first["review_drafts"][0]["reason"] == "disabled"
    assert first["review_drafts"][0]["draft_request_id"] == "draft-1"
    assert first["requests"][0]["cached_tokens"] == 5
    assert first["requests"][0]["tool_call_ids"] == ["call-1"]
    assert first["requests"][1]["previous_investigation_common_prefix_chars"] is not None
    assert first["model_error_count"] == 1
    assert first["model_capture_incomplete_count"] == 1
    tool = first["tool_calls"][0]
    assert tool["elapsed_seconds"] == 0.75
    assert tool["started_at"] == "2026-01-01T00:00:01Z"
    assert tool["ended_at"] == "2026-01-01T00:00:02Z"
    assert tool["issued_by_request_id"] == "req-1"
    assert tool["truncated"] is True
    assert len(tool["result_head"]) <= 300
    assert len(tool["result_tail"]) <= 300
    assert rows[1]["result_status"] == "row_count_2"
    prompt = (output / "prompt.txt").read_text()
    assert "system one" in prompt and "system two" in prompt and "user question" in prompt
    assert '"messages"' not in rows[0]


def test_sealed_export_only_contains_aggregates(tmp_path):
    campaign = make_campaign(tmp_path)
    output = tmp_path / "sealed"
    manifest = export(campaign, output, sealed=True)

    assert manifest["mode"] == "sealed"
    assert (output / "summary.json").is_file()
    assert not (output / "attempts.jsonl").exists()
    assert not (output / "prompt.txt").exists()
    summary = json.loads((output / "summary.json").read_text())
    case_group = next(group for group in summary["groups"] if group["case"] == "case")
    assert case_group["success_rate"] == 1.0
