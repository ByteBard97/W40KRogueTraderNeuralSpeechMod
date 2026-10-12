#!/usr/bin/env python3
"""Audio-LLM judge pilot. Run on the machine hosting the model server (see backends.py).

  python run_pilot.py smoke                     # one clip, then three clips in one request
  python run_pilot.py single [--transcript]     # 136 ear-labelled clips -> family metrics
  python run_pilot.py pair                      # both orders for every A/B pair -> verdicts.json
  python run_pilot.py report                    # metrics from results/, plus agreement if answers.json exists

Results are appended per clip to results/*.jsonl, so a crash or reboot loses nothing (re-run resumes).
Needs only the standard library; the model server does the heavy lifting.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from backends import ChatBackend  # noqa: E402
from families import DESCRIPTIONS, FAMILIES  # noqa: E402
from judge_logic import (FAMILY_PREFIX, PAIR_PREFIX, argmax, choice_logprobs, classification_metrics,  # noqa: E402
                         consistent_verdict, mean_logprobs, pair_agreement, pair_prompt, parse_choice,
                         position_bias, prior_correct, read_jsonl, single_prompt)

FAMS = list(FAMILIES)
DATA, RES = HERE / "data", HERE / "results"


def cmd_smoke(be: ChatBackend, a) -> None:
    gt = json.loads((DATA / "gt.json").read_text())
    r = be.ask("Describe in one short sentence how this person sounds.", [HERE / gt[0]["wav"]], 40, logprobs=False)
    print("1 clip:", r["text"], f'({r["seconds"]}s)')
    r = be.ask("How many separate audio clips did you hear? Answer with a number.",
               [HERE / gt[i]["wav"] for i in range(3)], 8, logprobs=False)
    print("3 clips in one request:", r["text"], f'({r["seconds"]}s)  (expect 3)')


def cmd_single(be: ChatBackend, a) -> None:
    gt = json.loads((DATA / "gt.json").read_text())
    RES.mkdir(exist_ok=True)
    out = RES / f"single_{'text' if a.transcript else 'audio'}.jsonl"
    done = {r["event"] for r in read_jsonl(out)}
    for i, g in enumerate(gt):
        if g["event"] in done:
            continue
        prompt = single_prompt(FAMS, DESCRIPTIONS, g["text"] if a.transcript else None)
        r = be.ask(prompt, [HERE / g["wav"]], 24)
        lp = choice_logprobs(r["logprobs"], FAMS, FAMILY_PREFIX) if r["logprobs"] else None
        row = {"event": g["event"], "human_family": g["family"], "raw": r["text"],
               "parsed": parse_choice(r["text"], FAMS), "logprobs": lp, "seconds": r["seconds"]}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        print(i, g["family"], row["parsed"], flush=True)


def single_report(path: Path) -> dict | None:
    rows = read_jsonl(path)
    if not rows:
        return None
    truth = [r["human_family"] for r in rows]
    res = {"raw": classification_metrics(truth, [r["parsed"] for r in rows], FAMS)}
    with_lp = [r for r in rows if r["logprobs"]]
    if len(with_lp) == len(rows):
        prior = mean_logprobs([r["logprobs"] for r in rows])
        pred = [argmax(prior_correct(r["logprobs"], prior)) for r in rows]
        res["prior_corrected"] = classification_metrics(truth, pred, FAMS)
    return res


def cmd_pair(be: ChatBackend, a) -> None:
    pairs = json.loads((DATA / "pairs.json").read_text())
    RES.mkdir(exist_ok=True)
    out = RES / "pair.jsonl"
    done = {(r["id"], r["order"]) for r in read_jsonl(out)}
    for p in pairs:
        for order in ("ab", "ba"):
            if (p["id"], order) in done:
                continue
            x, y = (p["a"], p["b"]) if order == "ab" else (p["b"], p["a"])
            prompt = pair_prompt(p["axis"], p.get("emotion"), p.get("instruct"))
            r = be.ask(prompt, [HERE / p["reference_wav"], HERE / x, HERE / y], 16, logprobs=False)
            row = {"id": p["id"], "axis": p["axis"], "order": order, "raw": r["text"],
                   "answer": parse_choice(r["text"], ["A", "B"], "closer"), "seconds": r["seconds"]}
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(p["id"][:8], p["axis"], order, row["answer"], flush=True)


def pair_verdicts() -> dict:
    rows = read_jsonl(RES / "pair.jsonl")
    by = {}
    for r in rows:
        by.setdefault(r["id"], {})[r["order"]] = r["answer"]
    return {i: consistent_verdict(o.get("ab"), o.get("ba")) for i, o in by.items() if len(o) == 2}


def cmd_report(be, a) -> None:
    report = {}
    for name in ("single_audio", "single_text"):
        r = single_report(RES / f"{name}.jsonl")
        if r:
            report[name] = r
    rows = read_jsonl(RES / "pair.jsonl")
    if rows:
        v = pair_verdicts()
        report["pair"] = {"n_pairs": len(v), "consistent": sum(x is not None for x in v.values()),
                          "position_bias": position_bias([r["answer"] for r in rows]), "verdicts": v}
        ans_path = DATA / "answers.json"
        if ans_path.exists():
            human = {k: x for k, x in json.loads(ans_path.read_text()).items()}
            axes = {p["id"]: p["axis"] for p in json.loads((DATA / "pairs.json").read_text())}
            report["pair"]["agreement_with_human"] = pair_agreement(v, human, axes)
    RES.mkdir(exist_ok=True)
    (RES / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["smoke", "single", "pair", "report"])
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--model", default="default")
    ap.add_argument("--transcript", action="store_true")
    a = ap.parse_args()
    {"smoke": cmd_smoke, "single": cmd_single, "pair": cmd_pair, "report": cmd_report}[a.cmd](
        ChatBackend(a.url, a.model), a)
