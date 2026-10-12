"""Score every take from gen_best_of_n.py and build blind A/B pairs for a human check.

Run in tools/scorer/.venv-scorer:  python tools/scorer/rank_takes.py
Writes data/scorer_probe/best_of_n/{scores.json,pairs.json} (resumable)."""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from scorer import ROOT, VOICE_FEATURES, Character, ClipScorer, voice_composite  # noqa: E402
from selection import calibration  # noqa: E402,F401

BON = ROOT / "data/scorer_probe/best_of_n"
CAL = ROOT / "data/scorer_probe/calibration.json"
WER_GATE = 0.34


def main():
    manifest = json.load(open(BON / "manifest.json"))
    sp = BON / "scores.json"
    scores = json.load(open(sp)) if sp.exists() else {}
    scorer = ClipScorer()
    cur = json.load(open(ROOT / "data/voices/emotion_banks/curation.json"))["Abelard"]
    char = Character(scorer, ROOT / "data/voices/wav/Abelard", cur)
    print("probe trained on families:", dict(char.label_counts))
    for i, m in enumerate(manifest):
        if m["cell_id"] in scores:
            continue
        scores[m["cell_id"]] = char.score(ROOT / m["wav_path"], m["reference"]["wav"], m["text"], m["emotion"])
        if i % 10 == 0:
            json.dump(scores, open(sp, "w"))
            print(i, len(manifest), flush=True)
    json.dump(scores, open(sp, "w"))

    scale = calibration()
    by_line = {}
    for m in manifest:
        by_line.setdefault(m["guid"], []).append(m)
    rng = random.Random(7)
    pairs = []
    for guid, ms in sorted(by_line.items()):
        rows = [scores[m["cell_id"]] for m in ms]
        ok = [i for i, r in enumerate(rows) if r.get("wer", 0) <= WER_GATE and not r["clipped"]]
        if len(ok) < 4:
            print("skip line, too few gate-passing takes:", guid, len(ok))
            continue
        vc = voice_composite(rows, scale)
        by_voice = sorted(ok, key=lambda i: vc[i])
        picks = {"voice": (by_voice[-1], by_voice[0])}
        pt = [(rows[i]["p_target_family"], i) for i in ok if rows[i]["p_target_family"] is not None]
        if len(pt) >= 4 and np.ptp([p for p, _ in pt]) > 0.05:
            pt.sort()
            picks["emotion"] = (pt[-1][1], pt[0][1])
        for axis, (best, worst) in picks.items():
            a, b = (best, worst) if rng.random() < 0.5 else (worst, best)
            pairs.append({"id": f"{guid}_{axis}", "guid": guid, "axis": axis, "text": ms[0]["text"],
                          "instruct": ms[0]["instruct"], "emotion": ms[0]["emotion"],
                          "reference_wav": ms[0]["reference"]["wav"],
                          "a": ms[a]["wav_path"], "b": ms[b]["wav_path"],
                          "scorer_prefers": "a" if a == best else "b",
                          "a_score": float(vc[a]) if axis == "voice" else rows[a]["p_target_family"],
                          "b_score": float(vc[b]) if axis == "voice" else rows[b]["p_target_family"]})
    json.dump(pairs, open(BON / "pairs.json", "w"), indent=1)
    print(f"{len(pairs)} pairs written")


if __name__ == "__main__":
    main()
