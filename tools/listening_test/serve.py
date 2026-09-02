#!/usr/bin/env python3
"""Local listening test server for the TTS bake-off (Chatterbox-Turbo, Qwen3-TTS, IndexTTS2,
plus an experimental EQ/compression-matched Chatterbox-Turbo variant - see tools/audio_match).

For every line, all engines with audio for it are presented together, each one labeled with its
real name (see ENGINE_LABELS) - this is a labeled comparison, not a blind test - and the listener
ranks them best to worst (or calls it a tie), plus can flag one or more error tags
(mispronunciation, wrong words, etc.) on each individual clip. Rank 1 of k scores k points, rank
2 scores k-1, ... down to 1 point for last place - a Borda count, not a single winner-take-all
pick, so a clip that's usually second still shows up in the standings.

Local-only by design: this serves voice-cloned audio built from the user's own game files, which
must never be distributed (see PROJECT_PLAN.md). Run it, open http://127.0.0.1:8899 yourself or
share the link on your own LAN with friends - never expose it publicly.

Usage: python3 serve.py [--port 8899]
Votes are stored keyed by line id in data/bakeoff/listening_votes.json (re-voting a line
overwrites its entry rather than piling up duplicates, so back/forward navigation is safe).
Tally with tally.py, or use the "Download results" link in the page to save the current votes.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent.parent
BAKEOFF = ROOT / "data/bakeoff"
ENGINES = [
    "chatterbox_turbo", "qwen3_tts", "indextts2",
    "chatterbox_turbo_eq",  # chatterbox_turbo + fitted EQ/compression match to real VO, see tools/audio_match
]  # fish_s2 has no generated audio (dropped mid-bakeoff)
ENGINE_LABELS = {
    "chatterbox_turbo": "Chatterbox Turbo",
    "qwen3_tts": "Qwen3 TTS",
    "indextts2": "IndexTTS2",
    "chatterbox_turbo_eq": "Chatterbox Turbo + EQ/compression match",
}
TEST_SET = json.loads((ROOT / "data/tts_test_set.json").read_text(encoding="utf-8"))
VOTES_PATH = BAKEOFF / "listening_votes.json"
STATIC_DIR = Path(__file__).resolve().parent
ERROR_TAGS = {
    "mispronunciation", "wrong_words", "garbled", "wrong_emotion", "wrong_accent",
    "voice_mismatch", "artifact", "other",
}

ANNOTATIONS_PATH = ROOT / "data/annotations/annotations.enGB.json"
ANNOTATIONS = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8")) if ANNOTATIONS_PATH.exists() else {}

VOICES_DIR = ROOT / "data/voices"
PROMPTS_PATH = VOICES_DIR / "prompts/prompts.json"
PROMPTS = json.loads(PROMPTS_PATH.read_text(encoding="utf-8")) if PROMPTS_PATH.exists() else {}
REFERENCE_CLIPS_PER_SPEAKER = 3


def acting_direction(item: dict) -> dict | None:
    ann = ANNOTATIONS.get(item.get("source_key"))
    if not ann:
        return None
    return {
        "instruct": ann.get("instruct"),
        "emotion": ann.get("emotion"),
        "intensity": ann.get("intensity"),
        "nonverbal": ann.get("nonverbal") or [],
    }


def reference_clips(speaker: str) -> list[dict]:
    # Real game VO for this character, best-scored first (see build_prompt_banks.py) - lets the
    # listener refresh what the actual voice actor sounds like before judging the clones below.
    bank = PROMPTS.get(speaker) or []
    return [
        {"text": c["text"], "duration": c.get("duration"), "url": f"/reference/{quote(speaker)}/{c['rank']}"}
        for c in bank[:REFERENCE_CLIPS_PER_SPEAKER]
    ]


_votes_lock = threading.Lock()


def wav_path(engine: str, item: dict) -> Path:
    return BAKEOFF / engine / f"{item['id']}_{item['speaker']}.wav"


def load_votes() -> dict:
    if not VOTES_PATH.exists():
        return {}
    return json.loads(VOTES_PATH.read_text(encoding="utf-8"))


def save_votes(votes: dict) -> None:
    tmp = VOTES_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(votes, indent=2), encoding="utf-8")
    os.replace(tmp, VOTES_PATH)


def compute_tally(votes: dict) -> dict:
    """Borda count: in a k-way ranking, rank 1 (best) scores k points down to 1 for last place."""
    points = Counter()
    firsts = Counter()
    ranked_n = Counter()
    ties = 0
    for v in votes.values():
        if v.get("tie"):
            ties += 1
            continue
        ranking = v.get("ranking") or []
        k = len(ranking)
        for idx, engine in enumerate(ranking):
            points[engine] += k - idx
            ranked_n[engine] += 1
            if idx == 0:
                firsts[engine] += 1
    engines = sorted(set(points) | set(ranked_n), key=lambda e: -points[e])
    return {
        "standings": [
            {"engine": e, "points": points[e], "first_place": firsts[e], "n": ranked_n[e]}
            for e in engines
        ],
        "ties": ties,
        "n_votes": len(votes),
    }


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
        if path == "/items":
            return self._items()
        if path == "/tally":
            return self._tally()
        if path == "/export":
            return self._export()
        if path.startswith("/audio/"):
            return self._audio(path)
        if path.startswith("/reference/"):
            return self._reference_audio(path)
        self.send_error(404)

    def _serve_static(self, name, content_type):
        data = (STATIC_DIR / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _items(self):
        # Both line order and per-line clip order are stable (ENGINES declaration order) so
        # "Line N of 142" and "which row is which engine" both stay put across requests/restarts.
        # Clips are labeled with their real engine name - this is a labeled comparison, not a
        # blind test, so there's no reason to hide or shuffle identity.
        with _votes_lock:
            saved_votes = load_votes()
        items = []
        for item in TEST_SET:
            available = [e for e in ENGINES if wav_path(e, item).exists()]
            if len(available) < 2:
                continue
            items.append({
                "id": item["id"], "speaker": item["speaker"], "text": item["text"],
                "direction": acting_direction(item),
                "reference": reference_clips(item["speaker"]),
                "clips": [
                    {"engine": e, "label": ENGINE_LABELS.get(e, e),
                     "url": f"/audio/{e}/{item['id']}_{item['speaker']}.wav"}
                    for e in available
                ],
                "saved": saved_votes.get(item["id"]),
            })
        self._send_json({"items": items})

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

    def _reference_audio(self, path):
        parts = path.split("/", 3)  # '', 'reference', speaker, rank
        if len(parts) != 4:
            return self.send_error(404)
        speaker, rank_str = unquote(parts[2]), parts[3]
        bank = PROMPTS.get(speaker)
        if not bank or not rank_str.isdigit():
            return self.send_error(404)
        entry = next((c for c in bank if c["rank"] == int(rank_str)), None)
        if entry is None:
            return self.send_error(404)
        fp = (VOICES_DIR / entry["wav"]).resolve()
        if VOICES_DIR.resolve() not in fp.parents or not fp.is_file():
            return self.send_error(404)
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _tally(self):
        with _votes_lock:
            votes = load_votes()
        self._send_json(compute_tally(votes))

    def _export(self):
        with _votes_lock:
            votes = load_votes()
        body = json.dumps(list(votes.values()), indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Disposition", 'attachment; filename="listening_votes.json"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/vote":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", 0))
        try:
            vote = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self.send_error(400)
        required = {"id", "speaker", "order"}
        if not required.issubset(vote):
            return self.send_error(400)
        if vote.get("tie"):
            vote["ranking"] = None
        else:
            ranking = vote.get("ranking")
            if not ranking or sorted(ranking) != sorted(vote["order"]):
                return self.send_error(400)  # must rank every clip that was shown, no more/less
        for entry in vote.get("clip_errors", []):
            if not set(entry.get("tags", [])) <= ERROR_TAGS:
                return self.send_error(400)
        vote["ts"] = time.time()
        with _votes_lock:
            votes = load_votes()
            votes[vote["id"]] = vote
            save_votes(votes)
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
