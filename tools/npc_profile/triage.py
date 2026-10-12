#!/usr/bin/env python3
"""Split the conversations into tiers and, after a pass, pick the ones the bigger model should re-check.

  python3 tools/npc_profile/triage.py plan                      # tier 0 (no model) vs tier 1 (35B) counts
  python3 tools/npc_profile/triage.py escalate RESULTS.jsonl    # names needing the 122B, one per line
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import roster  # noqa: E402
from run_roster import ROOT, load_targets  # noqa: E402


def tiers(convs: list[dict], targets: set[str]) -> dict:
    """tier0: every unnamed line is narration, nothing for a model to decide. tier1: has quoted speech."""
    t0, t1 = [], []
    for c in convs:
        ls = [l for l in roster.conversation_lines(c, targets) if l["target"]]
        if not ls:
            continue
        (t1 if any(not roster.is_pure_narration(l["text"]) for l in ls) else t0).append(c["name"])
    return {"tier0": sorted(t0), "tier1": sorted(t1)}


def escalate(rows: list[dict], limit_score: float | None = None) -> list[str]:
    """Conversations whose audit says a second opinion is needed, worst score first."""
    bad = [r for r in rows if r["audit"]["needs_review"] and (limit_score is None or r["audit"]["score"] <= limit_score)]
    bad.sort(key=lambda r: (r["audit"]["score"], r["conversation"]))
    return [r["conversation"] for r in bad]


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "plan":
        convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
        t = tiers(convs, load_targets())
        out = ROOT / "data/npc_profile/triage.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(t, indent=1), encoding="utf-8")
        print(f"tier0 (narration only, no model): {len(t['tier0'])}   tier1 (35B): {len(t['tier1'])}   -> {out}")
    elif cmd == "escalate":
        rows = [json.loads(l) for l in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines()]
        names = escalate(rows)
        print("\n".join(names))
        print(f"# {len(names)} of {len(rows)} conversations need a second opinion", file=sys.stderr)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
