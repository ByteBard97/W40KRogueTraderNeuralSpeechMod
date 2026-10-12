"""Write one readable review file per flagged conversation (full text, model roster, model attribution, flag reasons).

  python3 tools/npc_profile/review_dump.py --out data/npc_profile/review/dump
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from roster import conversation_lines  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def load_targets() -> set[str]:
    jobs = (json.loads(ln) for ln in (ROOT / "data/render/jobs.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip())
    return {j["guid"] for j in jobs}


def render(conv: dict, res: dict, targets: set[str]) -> str:
    lines = conversation_lines(conv, targets)
    attr = {a["n"]: a for a in res["lines"]}
    out = [f"# {res['conversation'].strip()}", "", "## Flag reasons"]
    out += [f"- {r}" for r in res["audit"]["reasons"]]
    out += ["", "## Model roster"]
    for r in res["roster"]:
        out.append(f"- id={r['id']} name={r.get('name')} label={r.get('label')!r} {r['gender']}/{r['species']}/{r['age']} fx={r.get('fx')} evidence={r.get('evidence')}")
    out += ["", "## Conversation (numbered lines are the ones needing a speaker; [who] is what the game data says)", ""]
    for l in lines:
        a = attr.get(l["n"])
        mark = f"#{l['n']} " if l["target"] else f"{l['n']} "
        model = f"   <-- model: {a['speaker']} p={a.get('conf', {}).get('speaker')}" if a else ""
        out.append(f"{mark}[{l['who']}] {l['text']}{model}")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    convs = {c["name"].strip(): c for c in json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))}
    results = json.loads((ROOT / "data/npc_profile/roster_35b_all.json").read_text(encoding="utf-8"))
    targets = load_targets()
    flagged = sorted((r for r in results if r.get("audit", {}).get("needs_review")), key=lambda r: r["audit"]["score"])
    index = []
    for r in flagged:
        name = r["conversation"].strip()
        conv = convs.get(name)
        if not conv:
            print("missing", name)
            continue
        (out / f"{name}.md").write_text(render(conv, r, targets), encoding="utf-8")
        index.append(name)
    (out / "_index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(len(index), "files")


if __name__ == "__main__":
    main()
