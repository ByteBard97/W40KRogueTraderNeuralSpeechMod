"""Score data/audio_llm_pilot2/*.json: top-1 vs human family, confusion, baseline, parse failures."""
import json, collections
from pathlib import Path
OUT = Path(__file__).resolve().parent.parent.parent / "data/audio_llm_pilot2"
lines = []
for tag in ("audio", "audio_text"):
    p = OUT / f"single_{tag}.json"
    if not p.exists(): continue
    rows = json.loads(p.read_text()); n = len(rows)
    hum = collections.Counter(r["human_family"] for r in rows)
    maj, majn = hum.most_common(1)[0]
    acc = sum(r["constrained_pred"] == r["human_family"] for r in rows) / n
    facc = sum(r["retry_parse"] == r["human_family"] for r in rows) / n
    pf1 = sum(r["free_parse"] is None for r in rows) / n
    pf2 = sum(r["retry_parse"] is None for r in rows) / n
    pred = collections.Counter(r["constrained_pred"] for r in rows)
    lines += [f"## {tag} (n={n})", f"- constrained top-1: {acc:.3f}", f"- free-gen (after retry) top-1: {facc:.3f}",
              f"- majority baseline ('{maj}'): {majn/n:.3f}",
              f"- parse failure free-gen first try: {pf1:.3f}; after 1 retry: {pf2:.3f}",
              f"- human family counts: {dict(hum)}", f"- predicted family counts: {dict(pred)}", "", "confusion (human -> predicted):"]
    conf = collections.defaultdict(collections.Counter)
    for r in rows: conf[r["human_family"]][r["constrained_pred"]] += 1
    for h, c in sorted(conf.items()):
        lines.append(f"- {h} (n={hum[h]}, recall {c[h]/hum[h]:.2f}): {dict(c)}")
    lines.append("")
p = OUT / "pair.json"
if p.exists():
    rows = json.loads(p.read_text()); n = len(rows)
    lines += [f"## pairwise (n={n}, chance 0.5)",
              f"- constrained acc: {sum(r['constrained_pred']==r['truth'] for r in rows)/n:.3f}",
              f"- free acc (unparsed=wrong): {sum(r['free_pred']==r['truth'] for r in rows)/n:.3f}",
              f"- free parse failures: {sum(r['free_pred'] is None for r in rows)/n:.3f}",
              f"- constrained predicts 'A' share: {sum(r['constrained_pred']=='A' for r in rows)/n:.3f}"]
(OUT / "report.md").write_text("\n".join(lines)); print("\n".join(lines))
