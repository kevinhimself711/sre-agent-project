"""Audit downloaded frozen campaign evidence and render descriptive measurements."""

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

from campaign import completed, digest, public_summary, selected_records


def audit(state, directory):
    issues = []
    observations = []
    for row in state["attempts"]:
        if row["execution"] == "running":
            continue
        attempt = directory / "attempts" / Path(row["artifact_directory"]).name
        files = list(attempt.glob(f"holmes/{row['case']}/run_*/*_results.csv"))
        if not files:
            observations.append({"key": row["key"], "trace": "missing"})
            if row.get("data") == "complete" or row.get("execution") == "complete":
                issues.append(f"{row['key']}: completed result missing from local evidence")
            continue
        run = files[-1].parent
        for name, expected in row.get("artifacts", {}).items():
            if not (run / name).exists() or digest(run / name) != expected["sha256"]:
                issues.append(f"{row['key']}: artifact mismatch: {name}")
        trace = run / "holmes.events.jsonl"
        if not trace.exists():
            observations.append({"key": row["key"], "trace": "missing"})
            if row.get("data") == "complete":
                issues.append(f"{row['key']}: accepted trace missing from local evidence")
            continue
        events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
        reviews = [
            e for e in events if e["event"] == "diagnosis_review" and e["state"] == "triggered"
        ]
        if len(reviews) > 1:
            issues.append(f"{row['key']}: multiple reviews")
        if reviews and row["variant"] not in {"review", "combined"}:
            issues.append(f"{row['key']}: review unexpectedly enabled")
        drafts = {e["draft_request_id"] for e in reviews}
        sample_file = run / "sft-format-samples.jsonl"
        samples = (
            [json.loads(line) for line in sample_file.read_text(encoding="utf-8").splitlines()]
            if sample_file.exists()
            else []
        )
        if row["phase"] == "validation" and samples:
            issues.append(f"{row['key']}: validation leaked into SFT")
        if row.get("success") is not True and samples:
            issues.append(f"{row['key']}: unsuccessful attempt exported as positive SFT")
        if any(s["provenance"]["request_id"] in drafts for s in samples):
            issues.append(f"{row['key']}: draft used as a supervision target")
        requests = {e["request_id"]: e["request"] for e in events if e["event"] == "model_request"}
        for sample in samples:
            request = requests.get(sample["provenance"]["request_id"])
            if request is None or (
                sample["messages"][:-1] != request["messages"]
                or sample["tools"] != request.get("tools", [])
                or sample["loss_mask_messages"] != [0] * len(request["messages"]) + [1]
            ):
                issues.append(f"{row['key']}: SFT sample differs from the actual model input")
        tools = [e["result"]["result"] for e in events if e["event"] == "tool_end"]
        starts = [e["timestamp"] for e in events if e["event"] == "tool_catalog"]
        ends = [e["timestamp"] for e in events if e["event"] == "agent_final"]
        investigation_seconds = (
            (datetime.fromisoformat(ends[-1]) - datetime.fromisoformat(starts[0])).total_seconds()
            if starts and ends
            else None
        )
        rejected = [t for t in tools if str(t.get("data", "")).startswith("Command Rejected")]
        if row["variant"] in {"recovery", "combined"} and any(
            t["status"] != "error" for t in rejected
        ):
            issues.append(f"{row['key']}: rejection missing ERROR semantics")
        observations.append(
            {
                "key": row["key"],
                "attempt": row["attempt_number"],
                "reviews": len(reviews),
                "drafts_excluded": len(drafts),
                "sft_samples": len(samples),
                "investigation_seconds": investigation_seconds,
                "tool_errors": sum(t["status"] == "error" for t in tools),
                "classified_rejections": [t.get("error") for t in rejected],
            }
        )
    return {"issues": issues, "observations": observations}


def measured_mean(rows, field):
    values = [field(row) for row in rows]
    if not values or any(not isinstance(v, (int, float)) for v in values):
        return "unknown"
    return f"{mean(values):.2f}"


def render(state, audit_result):
    durations = {
        r.get("attempt"): r.get("investigation_seconds") for r in audit_result["observations"]
    }
    groups = defaultdict(list)
    for phase in ("dev", "validation"):
        for row in selected_records(state, phase):
            groups[phase, row["case"], row["variant"]].append(row)
    lines = [
        "# 冻结实验逐案例测量",
        "",
        f"代码：`{state['provenance']['commit']}`。",
        f"镜像：`{state['provenance']['image_id']}`。",
        "",
        "成功数和均值仅覆盖已完成且复位通过的有效观察；Agent 超时计失败。缺测单列，"
        "原始失败 attempt 保留在 JSON 中。token 均值包含可捕获的 Agent 辅助调用；"
        "缓存 token 是输入 token 的子集。调查耗时为 tool_catalog 至 agent_final 的墙钟跨度，"
        "排除环境准备、MCP 初始化和评分；上游完整阶段耗时另保存在 JSON。账单费用未知。",
        "",
        "| 阶段 | 案例 | 配置 | 有效/计划 | 成功 | composite 均值 | 输入 token | 输出 token | 缓存 token | 调查秒 | 拒绝/次 | 重复调用/次 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for (phase, case, variant), records in sorted(groups.items()):
        rows = [r for r in records if completed(r)]
        metrics = [measured_mean(rows, lambda r: r.get("score"))]
        for key in ("input", "output", "cached"):
            metrics.append(measured_mean(rows, lambda r, k=key: r.get("tokens", {}).get(k)))
        metrics.append(measured_mean(rows, lambda r: durations.get(r["attempt_number"])))
        for key in ("rejections", "repeated_tool_calls"):
            metrics.append(measured_mean(rows, lambda r, k=key: r.get(k)))
        lines.append(
            f"| {phase} | {case} | {variant} | {len(rows)}/3 | "
            f"{sum(r.get('success') is True for r in rows)} | " + " | ".join(metrics) + " |"
        )
    lines.extend(
        [
            "",
            f"替代 attempt：{state['replacement_count']}/4。",
            f"本地产物哈希、复核次数和导出隔离审计发现：{len(audit_result['issues'])} 项。",
            "",
            "此表为小样本描述统计，不提供稳定提分或充分泛化结论。具体失败机制及人工核对见实施报告。",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads((args.directory / "state.json").read_text(encoding="utf-8"))
    result = audit(state, args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(state, result), encoding="utf-8")
    args.output.with_suffix(".json").write_text(
        json.dumps({**public_summary(state), "audit": result}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"attempts": len(state["attempts"]), "audit_issues": result["issues"]}))
    if result["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
