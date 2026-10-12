#!/usr/bin/env python3
"""Review page for roster -> known-speaker matches (known.match).

Every roster entry that matched a speaker the game already names gets a row with the entry's evidence, a few of its lines
and the proposed speaker. Flagged matches (gender warning / ambiguous) start undecided; clean ones start accepted.
Decisions are saved to data/npc_profile/match_decisions.json, keyed "<conversation>|<roster id>".

  python3 tools/npc_profile/match_review.py [--port 8913]     # then open http://127.0.0.1:8913/
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from known import build_known, match  # noqa: E402
from run_roster import ROOT  # noqa: E402

DECISIONS = ROOT / "data/npc_profile/match_decisions.json"
SAMPLE_LINES = 3


def build_rows() -> list[dict]:
    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    banks = set(json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8")))
    known = build_known(convs, banks)
    text = {ln["text_key"]: ln["text"] for cv in convs for ln in cv["lines"] if ln.get("text_key") and ln.get("text")}
    roster = json.loads((ROOT / "data/npc_profile/roster_35b_all.json").read_text(encoding="utf-8"))
    rows = []
    for c in roster:
        mine = defaultdict(list)
        for ln in c["lines"]:
            mine[ln["speaker"]].append((ln["key"], ln["n"]))
        for e in c["roster"]:
            pairs = mine.get(e["id"], [])
            if not pairs:
                continue
            keys = [k for k, _ in pairs]
            gaps = [pairs[i + 1][1] - pairs[i][1] > 1 for i in range(min(len(pairs), SAMPLE_LINES) - 1)]
            m = match(e, known)
            if not m:
                continue
            flagged = bool(m.get("warning") or m.get("ambiguous_with"))
            rows.append({
                "id": f"{c['conversation']}|{e['id']}", "conversation": c["conversation"], "entry": e["id"],
                "name": e.get("name"), "label": e.get("label"), "gender": e.get("gender"), "species": e.get("species"),
                "role": e.get("role"), "evidence": e.get("evidence", [])[:3], "lines": len(keys),
                "samples": [text.get(k, "")[:600] for k in keys[:SAMPLE_LINES]], "gaps": gaps,
                "speaker": m["speaker"], "has_bank": m["has_bank"], "speaker_lines": m["lines"], "game_gender": m["game_gender"],
                "warning": m.get("warning"), "ambiguous_with": m.get("ambiguous_with"), "flagged": flagged,
            })
    return rows


def render(rows: list[dict], decisions: dict) -> str:
    e = html.escape
    order = sorted(rows, key=lambda r: (not r["flagged"], not r["has_bank"], r["speaker"], r["conversation"]))
    n_flag = sum(r["flagged"] for r in rows)
    out = [f"""<!doctype html><meta charset=utf-8><title>Speaker match review</title>
<style>body{{font:14px system-ui;max-width:1100px;margin:1em auto;padding:0 1em;background:#16181c;color:#ddd}}
.r{{border:1px solid #333;border-radius:6px;padding:.6em .8em;margin:.5em 0;background:#1d2026}}
.r.flag{{border-color:#c80}}.sp{{font-weight:600;color:#9cf}}.bank{{color:#8d8}}.nobank{{color:#aaa}}
.s{{color:#999;font-size:13px;margin:.2em 0 0 1em}}.w{{color:#e90}}select{{background:#222;color:#ddd}}
h2{{margin-top:1.4em}}</style>
<h1>Speaker match review</h1>
<p>{len(rows)} matches, {n_flag} flagged. Saved automatically. Use the real voice only if the proposed speaker is the same person.
"reject" means the entry gets its own designed voice.</p>"""]
    for title, grp in (("Flagged", [r for r in order if r["flagged"]]),
                       ("Clean, speaker has a voice bank", [r for r in order if not r["flagged"] and r["has_bank"]]),
                       ("Clean, speaker has no voice bank (shared designed voice)", [r for r in order if not r["flagged"] and not r["has_bank"]])):
        out.append(f"<h2>{title} ({len(grp)})</h2>")
        for r in grp:
            cur = decisions.get(r["id"], "" if r["flagged"] else "accept")
            opts = "".join(f'<option value="{v}"{" selected" if cur == v else ""}>{v or "undecided"}</option>' for v in ("", "accept", "reject"))
            warn = f'<div class=w>{e(r["warning"])}</div>' if r["warning"] else ""
            amb = f'<div class=w>also matches: {e(", ".join(r["ambiguous_with"]))}</div>' if r["ambiguous_with"] else ""
            samples = "".join(("<div class=s>&hellip; (other speakers' lines in between)</div>" if i and r["gaps"][i - 1] else "") + f'<div class=s>{e(s)}</div>'
                              for i, s in enumerate(r["samples"]) if s)
            ev = "; ".join(e(x) for x in r["evidence"])
            out.append(f"""<div class="r{' flag' if r['flagged'] else ''}"><select data-id="{e(r['id'])}">{opts}</select>
 <b>{e(r['name'] or r['label'] or r['entry'])}</b> <i>({e(r['label'] or '')}, {e(r['gender'] or '?')}, {e(r['species'] or '?')})</i>
 &rarr; <span class=sp>{e(r['speaker'])}</span> <span class={'bank' if r['has_bank'] else 'nobank'}>[{'bank' if r['has_bank'] else 'no bank'}, game gender {e(r['game_gender'] or '?')}, {r['speaker_lines']} lines]</span>
 <div class=s>{e(r['conversation'])} · {r['lines']} lines · {e(r['role'] or '')}</div>{warn}{amb}
 <div class=s>evidence: {ev}</div>{samples}</div>""")
    out.append("""<script>document.querySelectorAll('select[data-id]').forEach(s=>s.onchange=()=>
fetch('/save',{method:'POST',body:JSON.stringify({id:s.dataset.id,value:s.value})}));</script>""")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8913)
    ap.add_argument("--dump", action="store_true", help="print the row counts and exit")
    a = ap.parse_args()
    rows = build_rows()
    if a.dump:
        print(len(rows), Counter((r["flagged"], r["has_bank"]) for r in rows))
        return

    def load() -> dict:
        return json.loads(DECISIONS.read_text(encoding="utf-8")) if DECISIONS.exists() else {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = render(rows, load()).encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            d = load()
            if msg["value"]:
                d[msg["id"]] = msg["value"]
            else:
                d.pop(msg["id"], None)
            DECISIONS.write_text(json.dumps(d, indent=1, sort_keys=True), encoding="utf-8")
            self.send_response(204); self.end_headers()

        def log_message(self, *args):
            pass

    print(f"http://127.0.0.1:{a.port}/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
