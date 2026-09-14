#!/usr/bin/env python3
"""Serve a page comparing, for each sampled Abelard line: the text + assigned emotion,
the zero-shot reference clip that was used (with its own text/emotion/match quality),
and every TTS engine's generated output - so you can judge (a) whether the reference
match sounds right and (b) which engine produced the best result.

Reads data/bakeoff_abelard_emotion_matched/manifest.json fresh on every request, so it
reflects generation runs still in progress - refresh the page as more engines finish.

Usage: python3 tools/tts_bakeoff/review_abelard_samples.py [--port 8901]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = ROOT / "data/bakeoff_abelard_emotion_matched/manifest.json"


def load_by_guid() -> dict[str, dict]:
    """{guid: {"text", "annotation", "reference", "engines": {engine: entry}}}"""
    if not MANIFEST_PATH.exists():
        return {}
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_guid: dict[str, dict] = {}
    for entry in manifest.values():
        guid = entry["guid"]
        g = by_guid.setdefault(guid, {
            "text": entry["text"], "annotation": entry["annotation"],
            "reference": entry["reference"], "engines": {},
        })
        g["engines"][entry["engine"]] = entry
    return by_guid


def escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def render_page() -> str:
    by_guid = load_by_guid()
    if not by_guid:
        return "<html><body><h1>No samples yet</h1><p>Waiting for generation to produce " \
               "data/bakeoff_abelard_emotion_matched/manifest.json</p></body></html>"

    all_engines = sorted({e for g in by_guid.values() for e in g["engines"]})
    blocks = []
    for guid, g in by_guid.items():
        ann = g["annotation"]
        ref = g["reference"]
        match_note = ("exact match" if ref["exact_match"]
                      else f"nearest neighbor (distance {ref['distance']}, from real "
                           f"emotion '{ref['matched_emotion']}')")
        engine_players = []
        for engine in all_engines:
            entry = g["engines"].get(engine)
            if not entry:
                engine_players.append(f'<div class="engine"><h4>{engine}</h4><p class="muted">not run</p></div>')
            elif "error" in entry:
                engine_players.append(
                    f'<div class="engine"><h4>{engine}</h4>'
                    f'<p class="error">{escape(entry["error"])}</p></div>')
            else:
                engine_players.append(
                    f'<div class="engine"><h4>{engine}</h4>'
                    f'<audio controls preload="none" src="/wav?path={escape(entry["wav_path"])}"></audio>'
                    f'<p class="muted">{entry.get("audio_seconds", "?")}s, '
                    f'synth {entry.get("synth_seconds", "?")}s</p></div>')

        blocks.append(f"""
    <div class="line-block">
      <div class="text">"{escape(g['text'])}"</div>
      <div class="meta">emotion: <strong>{escape(ann['emotion'])}</strong>
        (intensity {ann['intensity']}, pace {ann['pace']}) &middot;
        instruct: <em>{escape(ann['instruct'])}</em></div>
      <div class="reference">
        <h4>Zero-shot reference used ({match_note})</h4>
        <audio controls preload="none" src="/wav?path={escape(str(Path(ref['wav']).relative_to(ROOT)))}"></audio>
        <div class="text">"{escape(ref['text'])}"</div>
      </div>
      <div class="engines">{''.join(engine_players)}</div>
    </div>""")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Abelard TTS sample review</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ background: #12121a; color: #e8e8f0; font-family: system-ui, sans-serif;
          max-width: 1100px; margin: 0 auto; padding: 24px; }}
  .line-block {{ border: 1px solid #33334a; border-radius: 8px; padding: 16px; margin-bottom: 24px; }}
  .text {{ font-size: 15px; margin: 6px 0; }}
  .meta {{ color: #8a8aa0; font-size: 13px; margin-bottom: 10px; }}
  .reference {{ background: #1c1c28; border-radius: 6px; padding: 10px; margin-bottom: 12px; }}
  .reference h4 {{ margin: 0 0 6px; font-size: 13px; color: #c9a227; }}
  .engines {{ display: flex; flex-wrap: wrap; gap: 12px; }}
  .engine {{ background: #1c1c28; border-radius: 6px; padding: 10px; min-width: 180px; }}
  .engine h4 {{ margin: 0 0 6px; font-size: 13px; }}
  .muted {{ color: #8a8aa0; font-size: 11px; }}
  .error {{ color: #b23f4e; font-size: 12px; }}
  audio {{ width: 100%; height: 32px; filter: invert(88%) hue-rotate(180deg); }}
</style></head><body>
<h1>Abelard TTS sample review</h1>
<p class="muted">{len(by_guid)} line(s), engines: {', '.join(all_engines) if all_engines else '(none yet)'}</p>
{''.join(blocks)}
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/wav":
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query)
            rel = unquote(q.get("path", [""])[0])
            full = (ROOT / rel).resolve()
            if not str(full).startswith(str(ROOT)) or not full.exists():
                self.send_response(404)
                self.end_headers()
                return
            data = full.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        body = render_page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8901)
    args = ap.parse_args()
    print(f"serving on http://127.0.0.1:{args.port}/")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
