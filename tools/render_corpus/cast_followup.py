#!/usr/bin/env python3
"""After the cast render: find out why anything failed, re-render it, accept what cannot do better, audit, report.

Run by cast_ready.py whenever the `cast` queue is idle (pending and leased both 0). Safe to run any number of times: it reads the state of
the render, writes data/studio/cast_followup.json, and does only what is still to do.

A piece needs another take when none of its takes is usable (stitch_mixed.usable_segments: rendered ok, plausible length, no truncated /
extra-words Whisper flag; a plain asr_bad is lenient). Each such piece gets up to MAX_REDO redo takes "<guid>@r1", "@r2" (same job, new guid,
queued into the running `cast` run through cast_jobs/redo-<round>.jsonl, so the workers already attached pick them up). stitch_mixed uses the
first usable take of a piece. A piece still flagged after its redos is accepted with its best take (lowest word error) and written to
data/render/cast_accept.json for a listen; a piece with no ok take at all is listed as unrenderable. Then audit_renders.py checks the stitched
clips and a report is written to data/render/cast_followup_report.md. Never deletes anything.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from jobs import take_problem  # noqa: E402

RUN = "cast"
PORT = 8952
MAX_REDO = 2          # redo takes per piece (the stitcher also looks for @r3)
BLOCKING = {"asr_truncated", "asr_extra_words"}      # asr_bad alone is lenient for this run (usually a misheard name)


def read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.is_file() else []


def pieces(root: Path) -> dict[str, dict]:
    """The planned pieces of the render (not the redo takes): guid -> job row."""
    out: dict[str, dict] = {}
    for f in sorted((root / "data/render/cast_jobs").glob("*.jsonl")):
        if f.name.startswith("redo-"):
            continue
        for r in lines(f):
            out[r["guid"]] = r
    return out


class Takes:
    """Everything the render knows about each take (manifest rows, Whisper results, accepted takes), by take guid."""

    def __init__(self, root: Path):
        run = root / "data/render" / RUN
        self.run = run
        self.rows: dict[str, list[dict]] = defaultdict(list)
        for r in lines(run / "manifest.jsonl"):
            self.rows[r["guid"]].append(r)
        self.asr = {r["guid"]: r for r in lines(run / "asr.jsonl")}
        self.accept = read(root / "data/render/cast_accept.json", {})

    def ok_row(self, guid: str) -> dict | None:
        return next((r for r in reversed(self.rows.get(guid, [])) if r.get("status") == "ok"), None)

    def problem(self, guid: str) -> str | None:
        """Why this take cannot be used, or None when it can."""
        r = self.ok_row(guid)
        if r is None:
            fails = self.rows.get(guid, [])
            return f"render failed: {(fails[-1].get('error') or 'unknown')[:70]}" if fails else "not rendered"
        if not (self.run / "wav" / f"{guid}.wav").is_file():
            return "wav missing"
        tp = take_problem(r.get("text", ""), r.get("seconds", 0))
        if tp:
            return f"take problem: {tp}"
        flags = set(self.asr.get(guid, {}).get("flags", [])) & BLOCKING
        if flags and guid not in self.accept:
            return "whisper: " + ", ".join(sorted(flags))
        return None

    def wer(self, guid: str) -> float:
        return float(self.asr.get(guid, {}).get("wer", 9.9))


def take_guids(base: str, upto: int = MAX_REDO) -> list[str]:
    return [base] + [f"{base}@r{k}" for k in range(1, upto + 1)]


def classify(root: Path) -> dict:
    """Piece by piece: usable, still to redo, or out of attempts."""
    t = Takes(root)
    out = {"usable": [], "redo": [], "exhausted": []}
    for base in pieces(root):
        guids = take_guids(base)
        if any(t.problem(g) is None for g in guids):
            out["usable"].append(base)
            continue
        tried = [g for g in guids if t.rows.get(g)]
        if len(tried) < len(guids):
            out["redo"].append(base)
        else:
            out["exhausted"].append(base)
    return out


def queue_redo(root: Path, state: dict) -> int:
    """Queue one more take for every piece that still has none and has attempts left (written where the queue server watches)."""
    t = Takes(root)
    plan = pieces(root)
    rows = []
    for base in classify(root)["redo"]:
        tried = [g for g in take_guids(base) if t.rows.get(g)]
        if not tried:
            continue                       # never rendered at all: the queue still owns it, not a redo
        nxt = next(g for g in take_guids(base) if not t.rows.get(g))
        rows.append({**plan[base], "guid": nxt, "redo_of": base, "redo_reason": t.problem(tried[-1])})
    if not rows:
        return 0
    state["round"] = state.get("round", 0) + 1
    f = root / "data/render/cast_jobs" / f"redo-{state['round']:02d}.jsonl"
    tmp = f.with_name(f".{f.name}.tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    os.replace(tmp, f)
    state.setdefault("reasons", {}).update({r["redo_of"]: r["redo_reason"] for r in rows})
    return len(rows)


def settle(root: Path) -> dict:
    """For pieces out of attempts: accept the best flagged take (lowest word error), or list the piece as unrenderable."""
    t = Takes(root)
    accept = dict(t.accept)
    plan = pieces(root)
    unrenderable = []
    for base in classify(root)["exhausted"]:
        cands = [g for g in take_guids(base) if t.ok_row(g) and (t.run / "wav" / f"{g}.wav").is_file()
                 and not take_problem(t.ok_row(g).get("text", ""), t.ok_row(g).get("seconds", 0))]
        if not cands:
            unrenderable.append({"piece": base, "speaker": plan[base]["speaker"], "text": plan[base]["text"][:120],
                                 "why": [t.problem(g) for g in take_guids(base)]})
            continue
        best = min(cands, key=t.wer)
        accept[best] = {"piece": base, "speaker": plan[base]["speaker"], "wer": round(t.wer(best), 3), "text": plan[base]["text"][:160],
                        "heard": t.asr.get(best, {}).get("heard", "")[:160], "why": "still flagged after the redo takes; best take accepted, listen to it"}
    if accept != t.accept:
        write(root / "data/render/cast_accept.json", accept)
    return {"accepted": accept, "unrenderable": unrenderable}


def queue_idle(port: int = PORT) -> bool:
    try:
        q = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=3).read())
    except OSError:
        return False
    return q["total"] > 0 and q["pending"] + q["leased"] == 0


def audit(root: Path) -> str:
    """CPU-only check of the stitched clips: silence, gaps, abrupt ends, a quiet start, speed outliers."""
    r = subprocess.run([sys.executable, str(root / "tools/render_corpus/audit_renders.py"), "--export", "cast-stitched", "--out",
                        str(root / "data/render/audit/cast_audit.json")], capture_output=True, text=True, cwd=root)
    return (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:]])[-1]


def report(root: Path, state: dict, s: dict, audit_line: str) -> Path:
    c = classify(root)
    t = Takes(root)
    stitched = len(lines(root / "data/render/cast-stitched/manifest.jsonl"))
    cues = len({p["parent"] for p in pieces(root).values()})
    lenient = sum(1 for p in pieces(root) if t.ok_row(p) and "asr_bad" in t.asr.get(p, {}).get("flags", []))
    md = [f"# Cast render follow-up ({time.strftime('%Y-%m-%d %H:%M')})", "",
          f"- pieces: {len(pieces(root))}; usable {len(c['usable'])}, still to redo {len(c['redo'])}, out of attempts {len(c['exhausted'])}",
          f"- cues stitched: {stitched} of {cues}; redo rounds so far: {state.get('round', 0)}",
          f"- pieces accepted with only a plain Whisper 'asr_bad' (usually a misheard name): {lenient}",
          f"- accepted despite a truncated / extra-words flag (listen to these): {len(s['accepted'])}",
          f"- unrenderable (no usable take at all): {len(s['unrenderable'])}", f"- audit: {audit_line}", ""]
    for g, a in list(s["accepted"].items())[:60]:
        md.append(f"  - accepted {g}: {a.get('speaker')} (word error {a.get('wer')}) wanted {a.get('text')!r} heard {a.get('heard')!r} {a.get('why', '')}")
    for u in s["unrenderable"][:60]:
        md.append(f"  - UNRENDERABLE {u['piece']}: {u['speaker']} {u['text']!r} why {u['why']}")
    if state.get("reasons"):
        why = Counter(v.split(":")[0] if v else "?" for v in state["reasons"].values())
        md += ["", f"Why pieces needed a redo: {dict(why)}"]
    f = root / "data/render/cast_followup_report.md"
    f.write_text("\n".join(md) + "\n", encoding="utf-8")
    return f


def step(root: Path = ROOT) -> dict:
    """One follow-up pass; call it whenever the queue is idle."""
    sf = root / "data/studio/cast_followup.json"
    state = read(sf, {})
    if not queue_idle():
        return {"followup": "waiting for the queue to finish"}
    n = queue_redo(root, state)
    if n:
        write(sf, state)
        return {"followup": f"queued {n} redo takes (round {state['round']})"}
    s = settle(root)
    if not state.get("audited_at") or time.time() - state["audited_at"] > 3600:
        state["audit"] = audit(root)
        state["audited_at"] = time.time()
    write(sf, state)
    f = report(root, state, s, state.get("audit", ""))
    return {"followup": f"done; report {f.name}", "accepted": len(s["accepted"]), "unrenderable": len(s["unrenderable"])}


if __name__ == "__main__":
    print(step())
