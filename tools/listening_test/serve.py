#!/usr/bin/env python3
"""Local blind A/B listening test server for the TTS bake-off (Chatterbox-Turbo vs Qwen3-TTS -
the two license-clean release candidates; the objective metrics in data/bakeoff/RESULTS.md put
them within ECAPA noise of each other, so this is the actual tiebreaker).

Local-only by design: this serves voice-cloned audio built from the user's own game files, which
must never be distributed (see PROJECT_PLAN.md). Run it, open http://127.0.0.1:8899 yourself or
share the link on your own LAN with friends - never expose it publicly.

Usage: python3 serve.py [--port 8899]
Votes append to data/bakeoff/listening_votes.jsonl (one JSON object per line, resumable/safe to
stop and restart the server at any time). Tally with tally.py once you have enough votes.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent.parent
BAKEOFF = ROOT / "data/bakeoff"
ENGINES = ["chatterbox_turbo", "qwen3_tts"]
TEST_SET = json.loads((ROOT / "data/tts_test_set.json").read_text(encoding="utf-8"))
VOTES_PATH = BAKEOFF / "listening_votes.jsonl"
STATIC_DIR = Path(__file__).resolve().parent

ID_RE = re.compile(r"^t\d{3}$")


def wav_path(engine: str, item: dict) -> Path:
    return BAKEOFF / engine / f"{item['id']}_{item['speaker']}.wav"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter default logging
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            return self._serve_static("index.html", "text/html")
        if path == "/pairs":
            return self._pairs()
        if path.startswith("/audio/"):
            return self._audio(path)
        self.send_error(404)

    def _serve_static(self, name, content_type):
        data = (STATIC_DIR / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _pairs(self):
        # Fresh random A/B assignment per page load. Only two engines exist right now, but this
        # doesn't hardcode that - it works if a third candidate is ever added to ENGINES.
        pairs = []
        for item in TEST_SET:
            if not all(wav_path(e, item).exists() for e in ENGINES):
                continue  # a clip is missing for this line on one engine - skip it, not fatal
            engines = ENGINES[:]
            random.shuffle(engines)
            pairs.append({
                "id": item["id"], "speaker": item["speaker"], "text": item["text"],
                "a_engine": engines[0], "b_engine": engines[1],
                "a_url": f"/audio/{engines[0]}/{item['id']}_{item['speaker']}.wav",
                "b_url": f"/audio/{engines[1]}/{item['id']}_{item['speaker']}.wav",
            })
        random.shuffle(pairs)
        self._send_json({"pairs": pairs})

    def _audio(self, path):
        parts = path.split("/", 3)  # '', 'audio', engine, filename
        if len(parts) != 4:
            return self.send_error(404)
        engine, filename = parts[2], parts[3]
        if engine not in ENGINES or "/" in filename or "\\" in filename:
            return self.send_error(403)
        fp = BAKEOFF / engine / filename
        if not fp.is_file():
            return self.send_error(404)
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if urlparse(self.path).path != "/vote":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", 0))
        try:
            vote = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self.send_error(400)
        required = {"id", "speaker", "a_engine", "b_engine", "choice"}
        if not required.issubset(vote) or vote["choice"] not in ("a", "b", "tie"):
            return self.send_error(400)
        with VOTES_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(vote) + "\n")
        self._send_json({"ok": True})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    missing = [e for e in ENGINES if not (BAKEOFF / e).is_dir()]
    if missing:
        raise SystemExit(f"missing bake-off output for engines: {missing}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Listening test running at http://{args.host}:{args.port} (Ctrl+C to stop)")
    print(f"Votes -> {VOTES_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
