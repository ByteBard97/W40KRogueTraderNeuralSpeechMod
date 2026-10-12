#!/usr/bin/env python3
"""Audit page for the rendered corpus. Local only (127.0.0.1:8913): it serves audio made from the
user's game files, so it is never published anywhere.

  python3 tools/render_corpus/audit_server.py [--port 8913] [--export data/render/export]
  python3 tools/render_corpus/audit_server.py --run win-narr-real-pilot [--only guids.txt]   # one render run, per-clip clone source

Lists every clip in <export>/index.json with its text, speaker, engine, duration and characters/second,
auto-flags suspicious ones (hit the ~30 s generation cap, far too slow or fast for the text, very short),
and records your verdict per clip (good / bad + reason tags + note). Verdicts live in
data/render/audit/verdicts.json and are written on every click.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import io
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import numpy as np

from deburst import PRESETS, deburst

ROOT = Path(__file__).resolve().parents[2]
HTML = Path(__file__).with_name("audit.html")
CAP_S = (27.0, 30.2)          # voxcpm2 runs away until its ~30 s generation cap
SLOW_CPS, FAST_CPS = 7.0, 26.0   # chars/second of spoken text; the corpus median is ~15
SHORT_S = 0.7


def spoken_text(t: str) -> str:
    return re.sub(r"\{[^}]*\}", "", t).strip()


def auto_flags(dur: float, chars: int, existing: list[str]) -> list[str]:
    """Why a clip looks wrong without listening. `existing` are the flags render.py already set."""
    fl = list(existing)
    cps = chars / dur if dur else 0
    if CAP_S[0] <= dur <= CAP_S[1]:
        fl.append("cap_hit")
    if chars >= 8 and cps < SLOW_CPS:
        fl.append("slow")
    if chars >= 8 and cps > FAST_CPS:
        fl.append("fast")
    if dur < SHORT_S:
        fl.append("short")
    if dur > 40:
        fl.append("very_long")
    return fl


def build_clips(export: Path) -> list[dict]:
    index = json.loads((export / "index.json").read_text(encoding="utf-8"))
    jobs: dict[str, dict] = {}
    for f in sorted(glob.glob(str(ROOT / "data/render/jobs*.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            j = json.loads(ln)
            jobs[j["guid"]] = j
    out = []
    for g, e in index.items():
        p = export / e["wav"]
        try:
            with wave.open(str(p)) as w:
                dur = w.getnframes() / w.getframerate()
        except Exception:
            continue
        j = jobs.get(g, {})
        text = spoken_text(j.get("text") or e["text"])
        ann = j.get("annotation") or {}
        out.append({
            "guid": g, "wav": e["wav"], "text": text, "context": spoken_text(e["text"]) if j.get("text") and spoken_text(e["text"]) != text else "",
            "speaker": e["speaker"], "engine": e["engine"], "voice_source": e.get("voice_source", ""),
            "dur": round(dur, 2), "cps": round(len(text) / dur, 1) if dur else 0,
            "emotion": ann.get("emotion", ""), "instruct": ann.get("instruct", ""),
            "ref_path": (j.get("ref") or {}).get("wav", ""), "ref": Path((j.get("ref") or {}).get("wav", "")).stem,
            "flags": auto_flags(dur, len(text), e.get("flags", [])),
        })
    return out


def build_run_clips(run: Path, only: set[str] | None) -> list[dict]:
    """Clips of one render run (data/render/<run>/manifest.jsonl + wav/), with the clone source each one used."""
    jobs: dict[str, dict] = {}
    for f in sorted(glob.glob(str(ROOT / "data/render/jobs*.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            j = json.loads(ln)
            jobs[j["guid"]] = j
    asr = {}
    if (run / "asr.jsonl").exists():   # written by asr_check.py: what Whisper heard, word error rate, flags
        for ln in open(run / "asr.jsonl", encoding="utf-8"):
            r = json.loads(ln)
            asr[r["guid"]] = r
    real = json.loads((run / "real.json").read_text(encoding="utf-8")) if (run / "real.json").exists() else {}
    out = []
    for ln in open(run / "manifest.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        g = r["guid"]
        if r.get("status") != "ok" or (only is not None and g not in only):
            continue
        j = jobs.get(g, {})
        with wave.open(str(run / "wav" / f"{g}.wav")) as w:
            dur = w.getnframes() / w.getframerate()
        text = (r.get("text") or j.get("text", "")).strip()   # exactly what was sent, braced phonemes included
        ref = (j.get("ref") or {}).get("wav", "")
        out.append({
            "guid": g, "wav": f"wav/{g}.wav", "text": text, "context": "", "speaker": r.get("speaker", ""),
            "engine": r.get("engine", ""), "voice_source": r.get("voice_source", ""), "ref": Path(ref).stem if ref else "",
            "dur": round(dur, 2), "cps": round(len(spoken_text(text)) / dur, 1) if dur else 0, "emotion": "", "instruct": "",
            "ref_path": ref, "real": real.get(g.removeprefix("lexall-").replace("_", " "), []),
            "flags": auto_flags(dur, len(spoken_text(text)), r.get("flags", [])) + asr.get(g, {}).get("flags", []),
            "old": (ROOT / "data/render/export/wav" / f"{g}.wav").is_file(),
            "heard": asr.get(g, {}).get("heard", ""), "wer": asr.get(g, {}).get("wer"),
        })
    return out


def apply_fx(data: bytes, fx: str) -> bytes:
    """Return the WAV bytes with the consonant-burst compressor applied (16-bit PCM in and out)."""
    with wave.open(io.BytesIO(data)) as w:
        ch, sr, n = w.getnchannels(), w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    y = np.clip(deburst(x, sr, **PRESETS[fx]), -1, 1)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((y * 32767).astype("<i2").tobytes())
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    fx_cache: dict = {}
    clips: list[dict] = []
    wavdir: Path
    run_dir: Path | None = None
    verdicts_path: Path
    verdicts: dict = {}
    lock = threading.Lock()

    def _send(self, body: bytes, ctype="application/json", code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(HTML.read_bytes(), "text/html; charset=utf-8")
        if u.path == "/api/clips":
            return self._send(json.dumps({"clips": self.clips, "verdicts": self.verdicts}).encode())
        if u.path.startswith("/realvo/") and self.run_dir:   # snippets of the game's own voice acting (real_vo_snippets.py)
            p = (self.run_dir / "real" / os.path.basename(unquote(u.path))).resolve()
            return self._send(p.read_bytes(), "audio/wav") if p.is_file() else self._send(b"{}", code=404)
        if u.path == "/refwav":   # the clip a take was cloned from, so you can judge the match
            rel = parse_qs(u.query).get("path", [""])[0]
            p = (ROOT / rel).resolve()
            if not p.is_file() or p.suffix != ".wav" or ROOT / "data/voices" not in p.parents:
                return self._send(b"{}", code=404)
            return self._send(p.read_bytes(), "audio/wav")
        if u.path.startswith("/old/"):   # the earlier render of the same line, from the merged export, for before/after listening
            p = (ROOT / "data/render/export/wav" / os.path.basename(unquote(u.path))).resolve()
            return self._send(p.read_bytes(), "audio/wav") if p.is_file() else self._send(b"{}", code=404)
        if u.path.startswith("/wav/"):
            p = (self.wavdir / os.path.basename(unquote(u.path))).resolve()
            if not p.is_file():
                return self._send(b"{}", code=404)
            data = p.read_bytes()
            fx = parse_qs(u.query).get("fx", ["off"])[0]
            if fx in PRESETS:
                if (p, fx) not in self.fx_cache:
                    self.fx_cache[(p, fx)] = apply_fx(data, fx)
                data = self.fx_cache[(p, fx)]
            rng = self.headers.get("Range")
            m = re.match(r"bytes=(\d+)-(\d*)", rng or "")
            if m:
                a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else len(data) - 1
                part = data[a:b + 1]
                return self._send(part, "audio/wav", 206, {"Content-Range": f"bytes {a}-{a + len(part) - 1}/{len(data)}", "Accept-Ranges": "bytes"})
            return self._send(data, "audio/wav", extra={"Accept-Ranges": "bytes"})
        self._send(b"{}", code=404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/verdict":
            return self._send(b"{}", code=404)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        g = body.get("guid")
        if not g:
            return self._send(b'{"error":"guid"}', code=400)
        with self.lock:   # concurrent clicks share one temp file
            if body.get("verdict") is None:
                self.verdicts.pop(g, None)
            else:
                self.verdicts[g] = {"verdict": body["verdict"], "tags": body.get("tags", []), "note": body.get("note", "")}
            tmp = self.verdicts_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.verdicts, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.verdicts_path)
        self._send(b'{"ok":true}')

    def log_message(self, *a):
        pass


class Server(ThreadingHTTPServer):
    request_queue_size = 128   # the default backlog of 5 resets connections when the page fires several requests at once
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8913)
    ap.add_argument("--export", default=str(ROOT / "data/render/export"))
    ap.add_argument("--run", help="audit one render run, data/render/<run>, instead of the merged export")
    ap.add_argument("--only", help="with --run: text file of guids to include, one per line")
    a = ap.parse_args()
    export = Path(a.export)
    vp = ROOT / "data/render/audit" / (f"verdicts_{a.run}.json" if a.run else "verdicts.json")
    vp.parent.mkdir(parents=True, exist_ok=True)
    Handler.wavdir = (ROOT / "data/render" / a.run / "wav") if a.run else export / "wav"
    Handler.run_dir = (ROOT / "data/render" / a.run) if a.run else None
    Handler.verdicts_path = vp
    Handler.verdicts = json.loads(vp.read_text(encoding="utf-8")) if vp.exists() else {}
    print("indexing clips...", flush=True)
    if a.run:
        only = set(Path(a.only).read_text().split()) if a.only else None
        Handler.clips = build_run_clips(ROOT / "data/render" / a.run, only)
    else:
        Handler.clips = build_clips(export)
    print(f"{len(Handler.clips)} clips; http://127.0.0.1:{a.port}/", flush=True)
    Server(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
