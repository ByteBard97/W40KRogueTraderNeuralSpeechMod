#!/usr/bin/env python3
"""FX lab: tweak a Faust effect graph live on looping dialogue, then save the settings. Local only.

  python3 tools/fx_lab/server.py [--port 8908]     ->  http://127.0.0.1:8908/

Needs tools/fx_lab/vendor (FaustWasm + libfaust, see vendor/README). Effect graphs are the .dsp files in
tools/fx_lab/faust/; saved settings go to data/fx_lab/presets.json as {name: {dsp, params, notes}}.
The batch side (DawDreamer) reads the same .dsp and params.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import reference  # noqa: E402
EXPORT = ROOT / "data/render/export"
PRESETS = ROOT / "data/fx_lab/presets.json"
STATIC = {"/": HERE / "index.html", "/fx/": HERE / "index.html"}


def load_index() -> dict:
    return json.loads((EXPORT / "index.json").read_text(encoding="utf-8"))


def speakers(index: dict) -> list[dict]:
    counts: dict[str, int] = {}
    for e in index.values():
        counts[e.get("speaker") or "?"] = counts.get(e.get("speaker") or "?", 0) + 1
    return [{"speaker": s, "count": n} for s, n in sorted(counts.items(), key=lambda kv: -kv[1])]


def lines_for(index: dict, speaker: str, limit: int = 300) -> list[dict]:
    out = []
    for guid, e in index.items():
        if (e.get("speaker") or "?") == speaker:
            out.append({"guid": guid, "text": e.get("text", "")[:160], "wav": e["wav"]})
            if len(out) >= limit:
                break
    return out


def flat_presets(presets: dict) -> dict:
    """The presets this page can edit. Ones saved from the pedalboard hold a graph and a program under presets/, with per-pedal control keys
    the flat chain page cannot show; they are used by the batch script and the Studio, and left out of this page's list."""
    return {name: p for name, p in presets.items() if "graph" not in p}


def save_preset(presets: dict, name: str, body: dict) -> dict:
    """Re-saving a name overwrites it. Pure, for tests."""
    presets[name] = {"dsp": body["dsp"], "params": body.get("params", {}), "notes": body.get("notes", "")}
    return presets


class H(BaseHTTPRequestHandler):
    index: dict = {}

    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, p: Path):
        if not p.is_file():
            return self._send(b"not found", "text/plain", 404)
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        if p.suffix == ".wasm":
            ctype = "application/wasm"
        self._send(p.read_bytes(), ctype)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = unquote(u.path)
        if path in STATIC:
            return self._file(STATIC[path])
        if path == "/api/speakers":
            return self._send(json.dumps(speakers(self.index)).encode())
        if path == "/api/lines":
            return self._send(json.dumps(lines_for(self.index, q.get("speaker", [""])[0])).encode())
        if path == "/api/dsps":
            return self._send(json.dumps(sorted(p.name for p in (HERE / "faust").glob("*.dsp"))).encode())
        if path.startswith("/api/dsp/"):
            return self._file(HERE / "faust" / Path(path[9:]).name)
        if path == "/api/ref/speakers":
            return self._send(json.dumps(reference.speakers(ROOT)).encode())
        if path == "/api/ref/ltas":
            try:
                return self._send(json.dumps(reference.ltas(ROOT, q.get("speaker", [""])[0])).encode())
            except KeyError:
                return self._send(b'{"error":"no game audio for that speaker"}', code=404)
        if path == "/api/scenarios":
            return self._file(HERE / "scenarios.json")
        if path == "/api/presets":
            saved = json.loads(PRESETS.read_text(encoding="utf-8")) if PRESETS.exists() else {}
            return self._send(json.dumps(flat_presets(saved)).encode())
        if path.startswith("/wav/"):
            p = (EXPORT / path[5:]).resolve()
            if EXPORT.resolve() not in p.parents:
                return self._send(b"forbidden", "text/plain", 403)
            return self._file(p)
        if path.startswith("/libfaust-wasm/"):
            return self._file(HERE / "vendor/libfaust-wasm" / Path(path).name)
        if path.startswith("/faustwasm/"):
            return self._file(HERE / "vendor/faustwasm" / Path(path).name)
        self._send(b"not found", "text/plain", 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/presets":
            cur = json.loads(PRESETS.read_text(encoding="utf-8")) if PRESETS.exists() else {}
            save_preset(cur, body["name"], body)
            PRESETS.parent.mkdir(parents=True, exist_ok=True)
            tmp = PRESETS.with_suffix(".tmp")
            tmp.write_text(json.dumps(cur, indent=1, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, PRESETS)
            return self._send(b'{"ok":true}')
        if self.path.startswith("/api/dsp/"):
            name = Path(self.path[9:]).name
            if not name.endswith(".dsp"):
                return self._send(b"bad name", "text/plain", 400)
            (HERE / "faust" / name).write_text(body["code"], encoding="utf-8")
            return self._send(b'{"ok":true}')
        self._send(b"not found", "text/plain", 404)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8908)
    args = ap.parse_args()
    H.index = load_index()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), H)
    print(f"fx lab on http://127.0.0.1:{args.port}/  ({len(H.index)} lines)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
