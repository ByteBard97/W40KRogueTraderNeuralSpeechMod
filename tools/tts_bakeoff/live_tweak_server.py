#!/usr/bin/env python3
"""Real-time parameter-tweak frontend for the Abelard bake-off's two finalist engines
(qwen3_tts, voxcpm2). Pick a line, edit its text/instruction, adjust engine-specific
parameters, and render on demand - each render plays immediately and is kept in a
session-local history for A/B comparison, on top of the fixed cfg_value sweep in
sweep_voxcpm2_cfg.py / the vote_abelard_samples.py voting page.

This process itself never imports voxcpm2 or qwen3_tts - it's a thin HTML+proxy layer.
Each engine needs a different, incompatible Python environment (see
[[tts-engine-environments]] memory), so the actual model + generation work happens in two
separate live_tweak_backend.py processes (one per engine, each in its own env); this
frontend just serves the page and forwards /render calls to whichever backend port matches
the engine selected in the UI.

Usage:
  python3 tools/tts_bakeoff/live_tweak_server.py [--port 8903]
  (also start the two backends - see live_tweak_backend.py's docstring)
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from select_reference_clip import ReferenceLibrary  # noqa: E402  (stdlib-only, no engine imports)
BASE_MANIFEST_PATH = ROOT / "data/bakeoff_abelard_emotion_matched/manifest.json"

PAGE_PATH = Path(__file__).with_name("live_tweak.html")
RUNS_DIR = ROOT / "data/bakeoff_abelard_live_tweak/runs"
RUNS_PATH = ROOT / "data/bakeoff_abelard_live_tweak/runs.json"
_runs_lock = threading.Lock()

BACKEND_PORTS = {"voxcpm2": 8904, "qwen3_tts": 8905}


def load_runs() -> list[dict]:
    return json.loads(RUNS_PATH.read_text(encoding="utf-8")) if RUNS_PATH.exists() else []


def save_runs(runs: list[dict]) -> None:
    RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = RUNS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(runs, indent=2), encoding="utf-8")
    tmp.replace(RUNS_PATH)


def record_run(q: dict, wav: bytes, elapsed: float) -> str:
    """Persist a finished render: wav to runs/<id>.wav plus its settings in runs.json."""
    run_id = str(int(time.time() * 1000))
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{run_id}.wav").write_bytes(wav)
    ref_event = q.get("ref_event") or None
    clip = ReferenceLibrary("Abelard").by_event(ref_event) if ref_event else None
    run = {
        "id": run_id, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "engine": q["engine"],
        "guid": q.get("guid", ""), "text": q.get("text", ""),
        "params": {k: q[k] for k in ("instruct", "cfg", "ts", "retry") if k in q},
        "ref_event": ref_event,
        "ref": {"emotion": clip["emotion"], "duration": clip["duration"]} if clip else None,
        "elapsed": round(elapsed, 1), "star": False, "note": "",
    }
    with _runs_lock:
        runs = load_runs()
        runs.append(run)
        save_runs(runs)
    return run_id


def load_lines() -> dict[str, dict]:
    """guid -> {n, text, emotion, engines: {engine: {instruct, prompt_wav, prompt_text}}}"""
    manifest = json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8"))
    lines: dict[str, dict] = {}
    order: list[str] = []
    for key, entry in manifest.items():
        engine, guid = key.split(":", 1)
        if engine not in ("voxcpm2", "qwen3_tts"):
            continue
        if guid not in lines:
            lines[guid] = {"text": entry["text"], "emotion": entry["annotation"].get("emotion"),
                           "engines": {}}
            order.append(guid)
        lines[guid]["engines"][engine] = {
            "instruct": entry["annotation"].get("instruct"),
            "prompt_wav": entry["reference"]["wav"],
            "prompt_text": entry["reference"]["text"],
            "ref_event": entry["reference"]["event"],
            "ref_emotion": entry["reference"]["matched_emotion"],
            "ref_exact": entry["reference"]["exact_match"],
            "ref_distance": entry["reference"]["distance"],
        }
    for i, guid in enumerate(sorted(order, key=lambda g: lines[g]["text"]), start=1):
        lines[guid]["n"] = i
    return lines


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._index()
        if path == "/render":
            return self._render()
        if path == "/ref_wav":
            return self._ref_wav()
        if path == "/runs":
            return self._json(load_runs())
        if path == "/run_wav":
            return self._run_wav()
        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/run_meta":
            return self.send_error(404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except json.JSONDecodeError:
            return self.send_error(400)
        with _runs_lock:
            runs = load_runs()
            run = next((r for r in runs if r["id"] == body.get("id")), None)
            if run is None:
                return self.send_error(404)
            if isinstance(body.get("star"), bool):
                run["star"] = body["star"]
            if isinstance(body.get("note"), str):
                run["note"] = body["note"][:500]
            save_runs(runs)
        self._json({"ok": True})

    def _json(self, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _run_wav(self):
        run_id = parse_qs(urlparse(self.path).query).get("id", [""])[0]
        path = RUNS_DIR / f"{run_id}.wav"
        if not run_id.isdigit() or not path.exists():
            return self.send_error(404)
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _ref_wav(self):
        event = parse_qs(urlparse(self.path).query).get("event", [""])[0]
        clip = ReferenceLibrary("Abelard").by_event(event)
        if clip is None:
            return self.send_error(404)
        data = Path(clip["wav"]).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _index(self):
        lines = load_lines()
        lines_json = json.dumps({
            guid: {"n": v["n"], "text": v["text"], "emotion": v["emotion"], "engines": v["engines"]}
            for guid, v in lines.items()
        })
        line_options = "\n".join(
            f'<option value="{g}">Line {lines[g]["n"]} · [{lines[g]["emotion"]}] '
            f'{html.escape(lines[g]["text"][:60])}</option>'
            for g in sorted(lines, key=lambda g: lines[g]["n"])
        )
        by_emotion: dict[str, list[dict]] = {}
        for c in ReferenceLibrary("Abelard").all_clips():
            by_emotion.setdefault(c["emotion"], []).append(c)
        ref_options = "\n".join(
            f'<optgroup label="{emo} ({len(cs)})">' + "".join(
                f'<option value="{c["event"]}">{emo} · {c["duration"]:.1f}s · '
                f'{"✓ " if c["decision"] == "accept" else ""}{html.escape(c["text"][:50])}</option>'
                for c in sorted(cs, key=lambda c: -c["duration"])
            ) + '</optgroup>'
            for emo, cs in sorted(by_emotion.items())
        )
        refs_json = json.dumps({c["event"]: c["text"] for cs in by_emotion.values() for c in cs})
        body = (PAGE_PATH.read_text(encoding="utf-8")
                .replace("__LINES_JSON__", lines_json)
                .replace("__LINE_OPTIONS__", line_options)
                .replace("__REF_OPTIONS__", ref_options.replace("`", "'"))
                .replace("__REFS_JSON__", refs_json))
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _render(self):
        q = parse_qs(urlparse(self.path).query)

        def g(key, default=""):
            return q.get(key, [default])[0]

        engine = g("engine")
        if engine not in BACKEND_PORTS:
            return self._error(400, f"unknown engine {engine!r}")
        port = BACKEND_PORTS[engine]
        backend_url = f"http://127.0.0.1:{port}/render?{urlparse(self.path).query}"
        t0 = time.time()
        try:
            with urllib.request.urlopen(backend_url, timeout=120) as resp:
                data = resp.read()
                content_type = resp.headers.get("Content-Type", "audio/wav")
        except urllib.error.HTTPError as exc:
            return self._error(exc.code, exc.read().decode("utf-8", "replace"))
        except urllib.error.URLError as exc:
            return self._error(
                502, f"{engine} backend on port {port} unreachable ({exc.reason}) - "
                     f"is live_tweak_backend.py --engine {engine} --port {port} running?")

        run_id = record_run({k: v[0] for k, v in q.items()}, data, time.time() - t0)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Run-Id", run_id)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _error(self, code, msg):
        data = msg.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8903)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    if not BASE_MANIFEST_PATH.exists():
        raise SystemExit(f"no manifest at {BASE_MANIFEST_PATH}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Live tweak frontend running at http://{args.host}:{args.port} (Ctrl+C to stop)")
    print(f"Expects backends at {BACKEND_PORTS} - start live_tweak_backend.py for each engine first.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
