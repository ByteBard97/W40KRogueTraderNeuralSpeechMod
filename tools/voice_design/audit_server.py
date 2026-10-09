#!/usr/bin/env python3
"""Audition page for designed side-NPC voices. Local only (127.0.0.1:8907): it serves audio made from
the user's game files, so it is never published anywhere.

  python3 tools/voice_design/audit_server.py [--port 8907]

Per NPC: the voice description (editable; "Redo" stores it in overrides.json for design.py), the
candidate clips with the automatic accent hint (p_us) and UTMOS, clone-test lines, and your verdicts:
accent (british / american / other), voice fit 1-5, and one Pick. "Register picks" copies the picked
clips into the prompt bank (register.py). State lives in data/voice_design/audit.json.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
VD = ROOT / "data/voice_design"
FX_PRESETS = ROOT / "data/voice_fx/presets.json"      # per-speaker: what gets applied to rendered audio
FX_LIBRARY = ROOT / "data/voice_fx/library.json"       # named effect chains to start from (user-saved)
RENDER = ROOT / "data/render"
sys.path.insert(0, str(Path(__file__).parent))


def _load(name: str, default):
    p = VD / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _save(name: str, obj) -> None:
    tmp = (VD / name).with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, VD / name)


def sample_lines(rows: list[dict], n: int = 8) -> list[dict]:
    """Up to n rendered lines of one speaker, spread across the list, preferring 60-220 character texts."""
    ok = [r for r in rows if r.get("status") == "ok"]
    mid = [r for r in ok if 60 <= len(r.get("text", "")) <= 220] or ok
    mid.sort(key=lambda r: r["guid"])
    if len(mid) <= n:
        return mid
    return [mid[round(i * (len(mid) - 1) / (n - 1))] for i in range(n)]


def rendered_speakers(render_root: Path = RENDER, n: int = 8) -> dict:
    """{speaker: {"count": total ok lines here, "samples": [{"file": "render/<run>/wav/<guid>.wav", "text"}]}}
    from the per-machine manifests that exist on this machine."""
    by: dict[str, list[dict]] = {}
    for m in sorted(render_root.glob("*/manifest.jsonl")):
        if m.parent.name.endswith("-test"):
            continue
        for ln in m.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            if r.get("status") == "ok" and (m.parent / "wav" / f"{r['guid']}.wav").is_file():
                by.setdefault(r["speaker"], []).append({**r, "run": m.parent.name})
    return {sp: {"count": len(rows), "samples": [
        {"file": f"render/{r['run']}/wav/{r['guid']}.wav", "text": r["text"]} for r in sample_lines(rows, n)]}
        for sp, rows in sorted(by.items())}


def save_library(lib: dict, name: str, preset: dict) -> dict:
    """Named, reusable effect chain {fx, speed}. Re-saving a name overwrites it; nothing is ever removed."""
    name = name.strip()
    if not name or not preset:
        raise ValueError("name and preset required")
    lib[name] = {"fx": preset.get("fx", {}), "speed": round(float(preset.get("speed", 1.0)), 3)}
    return lib


def save_preset(presets: dict, name: str, preset: dict) -> dict:
    """Per-speaker voice FX preset {fx, speed}; an empty preset removes the entry. Pure, for tests."""
    if not preset or (not preset.get("fx") and abs(float(preset.get("speed", 1.0)) - 1.0) < 1e-3):
        presets.pop(name, None)
    else:
        presets[name] = {"fx": preset.get("fx", {}), "speed": round(float(preset.get("speed", 1.0)), 3)}
    return presets


def apply_verdict(audit: dict, body: dict) -> dict:
    """body: {name, cand, accent?|fit?|reject?|pick?}. Pure, for tests."""
    a = audit.setdefault(body["name"], {"cands": {}})
    c = a["cands"].setdefault(body["cand"], {})
    if "accent" in body:
        c["accent"] = body["accent"]
    if "fit" in body:
        c["fit"] = int(body["fit"])
    if "reject" in body:
        c["reject"] = bool(body["reject"])
    if "pick" in body:
        a["pick"] = body["cand"] if body["pick"] else None
    return audit


def apply_order(audit: dict, body: dict) -> dict:
    """body: {name, order: [cand, ...]} best to worst. Rank 1 becomes the pick. Pure, for tests."""
    a = audit.setdefault(body["name"], {"cands": {}})
    a["order"] = list(body["order"])
    a["pick"] = a["order"][0] if a["order"] else None
    return audit


LIVE_URL = "http://127.0.0.1:8909"   # live_backend.py


def keep_candidate(manifest: dict, name: str, tmp: Path, rec: dict, vd: Path = VD) -> str:
    """Copy a live take into the NPC's clips as the next cN.wav and record how it was made. Pure-ish, for tests."""
    import shutil
    m = manifest[name]
    nums = [int(c[1:-4]) for c in m["candidates"]]
    cand = f"c{max(nums, default=-1) + 1}.wav"
    dst = vd / "clips" / m["slug"] / cand
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tmp, dst)
    m["candidates"].append(cand)
    m.setdefault("gen", {}).setdefault("candidates", {})[cand] = {**rec, "live": True}
    return cand


def _live_call(path: str, body: dict | None = None, timeout: int = 180) -> dict:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(LIVE_URL + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}") or {"error": f"backend HTTP {e.code}"}
    except OSError:
        return {"error": "live backend not running (start tools/voice_design/live_backend.py)"}


class H(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            html = (Path(__file__).parent / "audit.html").read_text(encoding="utf-8")
            return self._send(html.encode(), "text/html; charset=utf-8")
        if u.path == "/state":
            return self._send(json.dumps({
                "manifest": _load("design_manifest.json", {}), "scores": _load("scores.json", {}),
                "clones": _load("clone_manifest.json", {}), "audit": _load("audit.json", {}),
                "overrides": _load("overrides.json", {}), "rendered": rendered_speakers()}).encode())
        if u.path == "/live/health":
            return self._send(json.dumps(_live_call("/health", timeout=3)).encode())
        if u.path == "/dsp.js":
            return self._send((Path(__file__).parent / "dsp.js").read_bytes(), "text/javascript; charset=utf-8")
        if u.path == "/library":
            return self._send(FX_LIBRARY.read_bytes() if FX_LIBRARY.exists() else b"{}")
        if u.path == "/fx":
            return self._send(FX_PRESETS.read_bytes() if FX_PRESETS.exists() else b"{}")
        if u.path == "/file":
            rel = parse_qs(u.query)["p"][0]
            base = RENDER.parent if rel.startswith("render/") else VD  # rendered lines live under data/render
            p = (base / rel).resolve()
            if (RENDER if rel.startswith("render/") else VD).resolve() not in p.parents or not p.is_file():
                return self._send(b"no", "text/plain", 404)
            return self._send(p.read_bytes(), mimetypes.guess_type(p.name)[0] or "audio/wav")
        self._send(b"no", "text/plain", 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/verdict":
            _save("audit.json", apply_verdict(_load("audit.json", {}), body))
            return self._send(b"{}")
        if self.path == "/live/generate":
            return self._send(json.dumps(_live_call("/generate", body)).encode())
        if self.path == "/live/keep":
            man = _load("design_manifest.json", {})
            tmp = (VD / body["file"]).resolve()
            if (VD / "live_tmp").resolve() not in tmp.parents or not tmp.is_file() or body["name"] not in man:
                return self._send(b'{"error":"bad take"}', code=400)
            rec = {k: body[k] for k in ("seed", "cfg", "timesteps", "description", "text") if k in body}
            cand = keep_candidate(man, body["name"], tmp, rec)
            _save("design_manifest.json", man)
            return self._send(json.dumps({"cand": cand}).encode())
        if self.path == "/order":
            _save("audit.json", apply_order(_load("audit.json", {}), body))
            return self._send(b"{}")
        if self.path == "/library":
            cur = json.loads(FX_LIBRARY.read_text(encoding="utf-8")) if FX_LIBRARY.exists() else {}
            try:
                lib = save_library(cur, body.get("name", ""), body.get("preset"))
            except ValueError as e:
                return self._send(json.dumps({"error": str(e)}).encode(), code=400)
            FX_LIBRARY.parent.mkdir(parents=True, exist_ok=True)
            tmp = FX_LIBRARY.with_suffix(".tmp")
            tmp.write_text(json.dumps(lib, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, FX_LIBRARY)
            return self._send(b"{}")
        if self.path == "/fx":
            cur = json.loads(FX_PRESETS.read_text(encoding="utf-8")) if FX_PRESETS.exists() else {}
            FX_PRESETS.parent.mkdir(parents=True, exist_ok=True)
            tmp = FX_PRESETS.with_suffix(".tmp")
            tmp.write_text(json.dumps(save_preset(cur, body["name"], body.get("preset")), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            os.replace(tmp, FX_PRESETS)
            return self._send(b"{}")
        if self.path == "/redo":
            ov = _load("overrides.json", {})
            ov[body["name"]] = body["description"]
            _save("overrides.json", ov)
            return self._send(b"{}")
        if self.path == "/register":
            from register import PROMPTS, register
            prompts = json.loads(PROMPTS.read_text(encoding="utf-8"))
            done = register(_load("audit.json", {}), _load("design_manifest.json", {}), prompts)
            PROMPTS.write_text(json.dumps(prompts, ensure_ascii=False, indent=1), encoding="utf-8")
            return self._send(json.dumps({"registered": done}).encode())
        self._send(b"no", "text/plain", 404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8907)
    args = ap.parse_args()
    print(f"voice audit on http://127.0.0.1:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()
