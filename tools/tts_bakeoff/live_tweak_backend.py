#!/usr/bin/env python3
"""Single-engine render backend for the live parameter-tweak tool. Run one instance per
engine, each under that engine's own environment (see [[tts-engine-environments]] memory /
tools/tts_bakeoff docs — qwen3_tts and voxcpm2 need different, incompatible dependency sets,
so they can't share a process). live_tweak_frontend.py proxies to whichever backend port
matches the engine selected in the UI.

Usage:
  tools/tts_bakeoff/.venv-qwen/bin/python3 tools/tts_bakeoff/live_tweak_backend.py --engine qwen3_tts --port 8905
  conda run -n roguetts python3 tools/tts_bakeoff/live_tweak_backend.py --engine voxcpm2 --port 8904
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_MANIFEST_PATH = ROOT / "data/bakeoff_abelard_emotion_matched/manifest.json"
OUT_ROOT = ROOT / "data/bakeoff_abelard_live_tweak"
WAV_DIR = OUT_ROOT / "wav"

sys.path.insert(0, str(ROOT / "tools/tts_engines"))
sys.path.insert(0, str(ROOT / "tools"))

_gpu_lock = threading.Lock()
_model = None
ENGINE = None  # set in main()


def _load():
    global _model
    if _model is not None:
        return _model
    if ENGINE == "voxcpm2":
        import voxcpm2 as eng
        _model = eng.load()
    elif ENGINE == "qwen3_tts":
        import qwen3_tts as eng
        _model = eng.load()
    return _model


def load_lines() -> dict[str, dict]:
    manifest = json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8"))
    lines: dict[str, dict] = {}
    for key, entry in manifest.items():
        engine, guid = key.split(":", 1)
        if engine != ENGINE:
            continue
        lines[guid] = {
            "text": entry["text"],
            "instruct": entry["annotation"].get("instruct"),
            "prompt_wav": entry["reference"]["wav"],
            "prompt_text": entry["reference"]["text"],
        }
    return lines


def render(guid, text, params):
    lines = load_lines()
    if guid not in lines:
        raise ValueError(f"unknown guid {guid!r} for engine {ENGINE}")
    ref = dict(lines[guid])
    ref_event = params.get("ref_event")
    if ref_event:
        from select_reference_clip import ReferenceLibrary
        clip = ReferenceLibrary("Abelard").by_event(ref_event)
        if clip is None:
            raise ValueError(f"unknown reference clip {ref_event!r}")
        ref["prompt_wav"], ref["prompt_text"] = clip["wav"], clip["text"]
    model = _load()

    if ENGINE == "voxcpm2":
        instruct = params.get("instruct") or None
        cfg = float(params.get("cfg", "2.0"))
        ts = int(params.get("ts", "10"))
        retry = params.get("retry", "1") == "1"
        full_text = f"({instruct}){text}" if instruct else text
        wav = model.generate(
            text=full_text, reference_wav_path=ref["prompt_wav"],
            cfg_value=cfg, inference_timesteps=ts, retry_badcase=retry,
        )
        wav = np.asarray(wav, dtype=np.float32).reshape(-1)
        sr = model.tts_model.sample_rate
        tag = f"cfg{cfg}_ts{ts}_retry{int(retry)}"
        tag += f"_ref{ref_event[:8]}" if ref_event else ""
    else:
        import qwen3_tts as eng
        wav, sr = eng.synth(model, text, prompt_wav=ref["prompt_wav"], prompt_text=ref["prompt_text"])
        tag = f"ref{ref_event[:8]}" if ref_event else "default"
    return wav, sr, tag


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._send(200, b"ok", "text/plain")
        if path == "/lines":
            data = json.dumps(load_lines()).encode("utf-8")
            return self._send(200, data, "application/json")
        if path == "/render":
            return self._render()
        self.send_error(404)

    def _render(self):
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        guid = q.get("guid", "")
        text = q.get("text", "")
        if not guid or not text.strip():
            return self._send(400, b"missing guid or text", "text/plain")
        try:
            with _gpu_lock:
                t0 = time.time()
                wav, sr, tag = render(guid, text, q)
                elapsed = time.time() - t0
        except Exception as exc:  # noqa: BLE001
            return self._send(500, f"{type(exc).__name__}: {exc}".encode("utf-8"), "text/plain")

        WAV_DIR.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time() * 1000)
        wav_path = WAV_DIR / f"{guid[:8]}_{ENGINE}_{tag}_{stamp}.wav"
        sf.write(str(wav_path), wav, sr)
        print(f"[render] {ENGINE} {guid[:8]} {tag} -> {wav_path.name} ({elapsed:.1f}s gen)")
        self._send(200, wav_path.read_bytes(), "audio/wav")

    def _send(self, code, data, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    global ENGINE
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, choices=["voxcpm2", "qwen3_tts"])
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    ENGINE = args.engine

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"{ENGINE} render backend on http://{args.host}:{args.port} (Ctrl+C to stop)")
    print("Model loads lazily on first /render call - expect ~20-45s delay on first use.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
