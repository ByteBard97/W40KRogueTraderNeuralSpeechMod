#!/usr/bin/env python3
"""Score generated takes and pick a winner per line (resumable; run in tools/scorer/.venv-scorer).

Reads data/bon/<speaker>/manifest.jsonl (from bon_generate.py), appends to scores.jsonl, and
rewrites winners.json. Gates first (transcript check, clipping, long trailing silence), then
the winner is the take with the best voice composite. The emotion-family probability of the
winner is recorded and flagged when low; it is NOT used to rank until the human A/B check
(review_server.py) shows it agrees with listeners.

  python tools/scorer/bon_score.py [--speaker Abelard] [--watch]
--watch keeps scoring as the generator produces takes, and exits after 15 idle minutes.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scorer import ROOT, Character, ClipScorer  # noqa: E402
from selection import calibration, select_winners, take_key  # noqa: E402


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def write_winners(out: Path, manifest: list[dict], scores: dict) -> dict:
    winners = select_winners(manifest, scores, calibration())
    (out / "winners.json").write_text(json.dumps(winners, ensure_ascii=False, indent=1), encoding="utf-8")
    return winners


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="Abelard")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--out-name", default=None, help="data/bon subdir (default: speaker)")
    ap.add_argument("--asr-device", default=None, help="cpu keeps Whisper off a GPU shared with a TTS engine")
    args = ap.parse_args()
    out = ROOT / "data/bon" / (args.out_name or args.speaker)
    sp = out / "scores.jsonl"

    scorer = ClipScorer(asr_device=args.asr_device)
    cur = json.loads((ROOT / "data/voices/emotion_banks/curation.json").read_text(encoding="utf-8"))[args.speaker]
    char = Character(scorer, ROOT / "data/voices/wav" / args.speaker, cur)
    print("probe families:", dict(char.label_counts), flush=True)

    scores = {}
    for r in read_jsonl(sp):
        scores[r["key"]] = r["score"]
    idle_since = time.time()
    while True:
        manifest = read_jsonl(out / "manifest.jsonl")
        todo = [m for m in manifest if take_key(m['guid'], m['take']) not in scores]
        for i, m in enumerate(todo):
            key = take_key(m['guid'], m['take'])
            try:
                s = char.score(ROOT / m["wav"], m["reference"]["wav"], m["text"], m["emotion"])
            except Exception as e:
                print("score failed", key, e, flush=True)
                continue
            scores[key] = s
            with open(sp, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "score": s}, ensure_ascii=False) + "\n")
            if i % 25 == 0:
                print(f"scored {len(scores)}/{len(manifest)}", flush=True)
                write_winners(out, manifest, scores)
            idle_since = time.time()
        w = write_winners(out, manifest, scores)
        print(f"winners for {len(w)} lines ({sum(v['status'] == 'ok' for v in w.values())} ok)", flush=True)
        if not args.watch or time.time() - idle_since > 900:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
