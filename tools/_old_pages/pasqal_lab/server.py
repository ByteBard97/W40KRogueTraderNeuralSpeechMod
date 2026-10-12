#!/usr/bin/env python3
"""Pasqal clone lab. Local only (127.0.0.1:8910); serves audio from the user's game files, never published.

  python3 tools/pasqal_lab/server.py [--port 8910]

Pick one of Pasqal's 45 real clips (or any wav under data/) as the clone reference, pick lines from his 844 to
generate, set the model options, render, and compare: the original clip, the bank's current render of the line, the
raw clone, and the clone after an FX Lab preset. Profiles (reference + options + FX preset) save to
data/pasqal_lab/profiles/<name>.json; "Set active" copies one to data/voices/prompts/Pasqal/clone_settings.json.

Generation needs tools/voice_design/live_backend.py running (VoxCPM2 in memory, GPU). FX runs fx_apply.py under
tools/fx_lab/.venv-fx. Nothing here changes the render plan, the bank, or prompts.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LAB = ROOT / "data/pasqal_lab"
BACKEND = "http://127.0.0.1:8909"
FX_PY = ROOT / "tools/fx_lab/.venv-fx/bin/python"
ACTIVE = ROOT / "data/voices/prompts/Pasqal/clone_settings.json"
FILE_ROOTS = [ROOT / "data/voices", ROOT / "data/render", LAB, ROOT / "data/voice_design"]
DEFAULTS = {"cfg": 2.0, "timesteps": 10, "retry_badcase": False, "normalize": False, "seed": "",
            "use_instruct": False, "continuation": False, "fx": []}


# NOTE: LAB is rebound in __main__ for --data-dir; path helpers read the module global at call time.
def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("._")[:60] or "unnamed"


def in_roots(p: Path, roots: list[Path] = FILE_ROOTS) -> bool:
    p = p.resolve()
    return p.is_file() and any(r.resolve() in p.parents for r in roots)


def sources() -> list[dict]:
    cat = json.loads((ROOT / "data/voices/catalog.json").read_text(encoding="utf-8"))
    prompts = json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8")).get("Pasqal", [])
    curated = {p["event"]: p for p in prompts}
    out = []
    for e in cat.values():
        if e["speaker"] != "Pasqal":
            continue
        txt = " ".join(t["text"] for t in e["texts"])
        pr = curated.get(e["event"])
        out.append({"id": e["event"], "wav": "data/voices/" + e["wav"], "duration": e["duration"], "text": txt,
                    "curated_rank": pr["rank"] if pr else None, "noise_db": pr.get("noise_db") if pr else None})
    out.sort(key=lambda s: (s["curated_rank"] is None, s["curated_rank"] or 0, s["id"]))
    return out


def lines() -> list[dict]:
    index = json.loads((ROOT / "data/render/export/index.json").read_text(encoding="utf-8"))
    out = []
    for ln in (ROOT / "data/render/jobs.jsonl").open(encoding="utf-8"):
        r = json.loads(ln)
        if r.get("speaker") != "Pasqal":
            continue
        a = r.get("annotation") or {}
        base = index.get(r["guid"], {}).get("wav")
        out.append({"guid": r["guid"], "text": r["text"], "emotion": a.get("emotion"), "intensity": a.get("intensity"),
                    "pace": a.get("pace"), "instruct": a.get("instruct"),
                    "baseline": f"data/render/export/{base}" if base else None})
    return out


def fx_presets() -> list[str]:
    sc = json.loads((ROOT / "tools/fx_lab/scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    names = [s["name"] for s in sc]
    saved = ROOT / "data/fx_lab/presets.json"
    if saved.exists():
        names += [n for n in json.loads(saved.read_text(encoding="utf-8")) if n not in names]
    return names


def profile_path(name: str) -> Path:
    return LAB / "profiles" / f"{safe_name(name)}.json"


def make_profile(body: dict) -> dict:
    """Keep only known keys so a profile is always loadable; unknown settings fall back to DEFAULTS."""
    opts = {k: body.get("options", {}).get(k, v) for k, v in DEFAULTS.items()}
    return {"name": body["name"], "reference": body["reference"], "options": opts,
            "test_lines": body.get("test_lines", []), "notes": body.get("notes", ""),
            "saved": time.strftime("%Y-%m-%d %H:%M:%S")}


def _atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def backend(path: str, body: dict | None = None, timeout: int = 240) -> dict:
    req = urllib.request.Request(BACKEND + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}") or {"error": f"backend HTTP {e.code}"}
    except OSError:
        return {"error": "live backend not running (python tools/voice_design/live_backend.py)"}


def run_fx(src: Path, names: list[str], out: Path) -> dict:
    if not FX_PY.is_file():
        return {"error": "tools/fx_lab/.venv-fx is missing"}
    r = subprocess.run([str(FX_PY), str(HERE / "fx_apply.py"), "--in", str(src), "--out", str(out)]
                       + [a for n in names for a in ("--preset", n)], capture_output=True, text=True, timeout=120)
    return {} if r.returncode == 0 else {"error": (r.stderr or r.stdout).strip().splitlines()[-1][:300]}


class H(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(json.dumps(obj, ensure_ascii=False).encode(), code=code)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send((HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        if u.path == "/api/state":
            profs = sorted(p.stem for p in (LAB / "profiles").glob("*.json")) if (LAB / "profiles").is_dir() else []
            takes = json.loads((LAB / "takes.json").read_text(encoding="utf-8")) if (LAB / "takes.json").exists() else {}
            return self._json({"sources": sources(), "lines": lines(), "fx_presets": fx_presets(), "profiles": profs,
                               "takes": takes, "defaults": DEFAULTS})
        if u.path == "/api/profile":
            p = profile_path(parse_qs(u.query)["name"][0])
            return self._send(p.read_bytes()) if p.is_file() else self._send(b"{}", code=404)
        if u.path == "/api/health":
            return self._json(backend("/health"))
        if u.path == "/file":
            p = ROOT / parse_qs(u.query)["p"][0]
            if not in_roots(p):
                return self._send(b"no", "text/plain", 404)
            return self._send(p.read_bytes(), "audio/wav")
        self._send(b"no", "text/plain", 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/generate":
            o = body["options"]
            ref = ROOT / body["reference"]["wav"]
            if not in_roots(ref):
                return self._json({"error": "reference must be a wav under data/"}, 400)
            req = {"text": body["text"], "reference_wav": body["reference"]["wav"], "seed": o.get("seed", ""),
                   "cfg": o["cfg"], "timesteps": o["timesteps"], "retry_badcase": o["retry_badcase"],
                   "normalize": o["normalize"]}
            if o.get("use_instruct") and body.get("instruct"):
                req["instruct"] = body["instruct"]
            if o.get("continuation"):
                req["prompt_text"] = body["reference"].get("text", "")
            r = backend("/generate", req)
            if "error" in r:
                return self._json(r)
            src = ROOT / "data/voice_design" / r["file"]
            take = {"id": f"p{int(time.time() * 1000)}", "raw": f"data/voice_design/{r['file']}", "text": body["text"],
                    "guid": body.get("guid"), "reference": body["reference"]["wav"], "options": o,
                    "instruct": req.get("instruct"), "seed": r["seed"], "seconds": r["seconds"],
                    "audio_s": r.get("audio_s"), "rating": 0, "note": "", "fx": None}
            takes = json.loads((LAB / "takes.json").read_text(encoding="utf-8")) if (LAB / "takes.json").exists() else {}
            takes[take["id"]] = take
            _atomic(LAB / "takes.json", takes)
            return self._json(take)
        if self.path == "/api/fx":
            takes = json.loads((LAB / "takes.json").read_text(encoding="utf-8"))
            t = takes[body["id"]]
            names = body.get("presets", [])
            if not names:
                t["fx"] = None
            else:
                out = LAB / "fx" / f"{t['id']}.wav"
                r = run_fx(ROOT / t["raw"], names, out)
                if "error" in r:
                    return self._json(r)
                t["fx"] = {"presets": names, "wav": f"data/pasqal_lab/fx/{t['id']}.wav", "v": int(time.time())}
            _atomic(LAB / "takes.json", takes)
            return self._json(t)
        if self.path == "/api/rate":
            takes = json.loads((LAB / "takes.json").read_text(encoding="utf-8"))
            t = takes[body["id"]]
            for k in ("rating", "note"):
                if k in body:
                    t[k] = body[k]
            _atomic(LAB / "takes.json", takes)
            return self._json({})
        if self.path == "/api/profile":
            prof = make_profile(body)
            _atomic(profile_path(prof["name"]), prof)
            return self._json({"saved": profile_path(prof["name"]).name})
        if self.path == "/api/active":
            p = profile_path(body["name"])
            if not p.is_file():
                return self._json({"error": "no such profile"}, 404)
            _atomic(ACTIVE, json.loads(p.read_text(encoding="utf-8")))
            return self._json({"active": str(ACTIVE.relative_to(ROOT))})
        self._send(b"no", "text/plain", 404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8910)
    ap.add_argument("--data-dir", default=None, help="where takes/profiles live (default data/pasqal_lab); for testing")
    a = ap.parse_args()
    if a.data_dir:
        LAB = Path(a.data_dir).resolve()
        FILE_ROOTS[2] = LAB
    LAB.mkdir(parents=True, exist_ok=True)
    print(f"Pasqal lab on http://127.0.0.1:{a.port}")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
