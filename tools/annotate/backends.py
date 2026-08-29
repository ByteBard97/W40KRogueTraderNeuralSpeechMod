"""LLM backends for the annotation harness. Each takes (system, user, json_schema) -> dict.

- ollama:  local models via the /api/chat endpoint with format=json_schema (constrained decoding)
- claude_cli: `claude -p` headless (subscription; pack whole conversations per call)
- kimi_cli:   `kimi -p` headless
All raise BackendError on refusal/truncation so the harness can retry with smaller chunks.
"""
from __future__ import annotations

import json
import subprocess
import urllib.request


class BackendError(RuntimeError):
    pass


def ollama(system: str, user: str, schema: dict, model: str = "qwen3:14b", host: str = "http://localhost:11434") -> dict:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "format": schema,
        "think": False,  # qwen3/deepseek-r1-class models: skip the reasoning trace, we only need the JSON
        "options": {"temperature": 0.2, "num_ctx": 16384},
    }
    req = urllib.request.Request(f"{host}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.load(r)
    if resp.get("done_reason") not in (None, "stop"):
        raise BackendError(f"ollama done_reason={resp.get('done_reason')}")
    try:
        return json.loads(resp["message"]["content"])
    except (KeyError, json.JSONDecodeError) as e:
        raise BackendError(f"ollama bad payload: {e}")


def _cli(cmd: list[str], system: str, user: str) -> dict:
    prompt = f"{system}\n\n{user}\n\nRespond with ONLY the JSON object, no prose, no code fences."
    r = subprocess.run(cmd + [prompt], capture_output=True, text=True, timeout=1200)
    if r.returncode != 0:
        raise BackendError(f"{cmd[0]} rc={r.returncode}: {r.stderr[-300:]}")
    out = r.stdout.strip()
    start, end = out.find("{"), out.rfind("}")
    if start < 0 or end <= start:
        raise BackendError(f"{cmd[0]}: no JSON in output")
    try:
        return json.loads(out[start:end + 1])
    except json.JSONDecodeError as e:
        raise BackendError(f"{cmd[0]}: bad JSON: {e}")


def claude_cli(system: str, user: str, schema: dict, model: str = "haiku") -> dict:
    return _cli(["claude", "-p", "--model", model, "--output-format", "text"], system, user)


def kimi_cli(system: str, user: str, schema: dict, model: str | None = None) -> dict:
    cmd = ["kimi", "-p"]
    return _cli(cmd, system, user)


BACKENDS = {"ollama": ollama, "claude": claude_cli, "kimi": kimi_cli}
