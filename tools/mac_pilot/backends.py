"""Model backend for the judge pilot: any OpenAI-compatible chat server that accepts audio.

Start one on the Mac, for example (runtime audio support is UNVERIFIED, that is what `smoke` tests):
  python -m mlx_vlm.server --model mlx-community/Qwen3-Omni-30B-A3B-Instruct-8bit --port 8080
  llama-server -m <gguf> --mmproj <mmproj> --port 8080
Audio goes in as `input_audio` (base64 wav). Stdlib only.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.request
from pathlib import Path


class ChatBackend:
    def __init__(self, url: str = "http://127.0.0.1:8080", model: str = "default", timeout: float = 300.0):
        self.url, self.model, self.timeout = url.rstrip("/"), model, timeout

    def ask(self, prompt: str, audio_paths: list[Path], max_tokens: int = 24, logprobs: bool = True) -> dict:
        """Returns {'text', 'logprobs' (OpenAI content list or None), 'seconds'}."""
        content = []
        for p in audio_paths:
            data = base64.b64encode(Path(p).read_bytes()).decode()
            content.append({"type": "input_audio", "input_audio": {"data": data, "format": "wav"}})
        content.append({"type": "text", "text": prompt})
        body = {"model": self.model, "messages": [{"role": "user", "content": content}],
                "max_tokens": max_tokens, "temperature": 0.0}
        if logprobs:
            body.update(logprobs=True, top_logprobs=20)
        req = urllib.request.Request(self.url + "/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            resp = json.load(r)
        ch = resp["choices"][0]
        lp = (ch.get("logprobs") or {}).get("content")
        return {"text": ch["message"]["content"], "logprobs": lp, "seconds": round(time.monotonic() - t0, 2)}
