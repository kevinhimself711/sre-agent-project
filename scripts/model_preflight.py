"""Validate the configured Bailian endpoint without logging authorization headers."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get(
    "AGENT_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
ROOT = Path(__file__).resolve().parents[1]


def completion(key, **body):
    request = urllib.request.Request(
        BASE + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def main():
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        key = re.search(
            r"sk-[A-Za-z0-9_-]+",
            (ROOT / "Bailian API.txt").read_text(encoding="utf-8-sig"),
        ).group()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_status",
                "description": "Read service health",
                "parameters": {
                    "type": "object",
                    "properties": {"service": {"type": "string"}},
                    "required": ["service"],
                },
            },
        }
    ]
    records = []
    for model in ["qwen3.8-max", "qwen3-max", "qwen-plus"]:
        entry = {"requested_model": model, "endpoint": BASE}
        try:
            messages = [
                {
                    "role": "user",
                    "content": "Use read_status to check service api, then report its health.",
                }
            ]
            first = completion(
                key,
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="required",
                enable_thinking=False,
                max_tokens=256,
            )
            message = first["choices"][0]["message"]
            calls = message.get("tool_calls", [])
            if not calls:
                raise ValueError("Expected tool_calls")
            messages.append(message)
            for call in calls:
                json.loads(call["function"]["arguments"])
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": '{"status":"healthy"}',
                    }
                )
            second = completion(
                key,
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="none",
                enable_thinking=False,
                max_tokens=256,
            )
            entry.update(
                status="ok",
                response_model=first.get("model"),
                tool_roundtrip=True,
                usage=[first.get("usage"), second.get("usage")],
                final=second["choices"][0]["message"].get("content"),
            )
            records.append(entry)
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace").replace(key, "[REDACTED]")
            entry.update(status="http_error", code=error.code, detail=detail[:600])
        except Exception as error:
            entry.update(
                status="error", detail=str(error).replace(key, "[REDACTED]")[:300]
            )
        records.append(entry)
    destination = ROOT / "artifacts/model-preflight.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(records, ensure_ascii=False, indent=2))
    if not records or records[-1]["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
