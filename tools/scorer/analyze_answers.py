"""Agreement between automated pickers and the human's blind A/B answers.

  python3 tools/scorer/analyze_answers.py [--judge path/to/results/report.json]
Free scorer picks come from pairs.json; the audio-LLM judge (tools/mac_pilot) is included when its
report.json is given. Reads data/scorer_probe/best_of_n/{pairs,answers}.json.
"""
import argparse
import json
from pathlib import Path

from ab_analysis import agreement, render

BON = Path(__file__).resolve().parents[2] / "data/scorer_probe/best_of_n"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default=None)
    args = ap.parse_args()
    pairs = json.load(open(BON / "pairs.json"))
    if not (BON / "answers.json").exists():
        raise SystemExit("no answers.json yet (the A/B review server on :8906 writes it as answers come in)")
    ans = json.load(open(BON / "answers.json"))
    print(render("free scorer", agreement(pairs, ans, {p["id"]: p["scorer_prefers"] for p in pairs})))
    if args.judge:
        verdicts = json.load(open(args.judge)).get("pair", {}).get("verdicts", {})
        print(render("audio-LLM judge (both orders agree)", agreement(pairs, ans, verdicts)))
