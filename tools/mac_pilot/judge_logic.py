"""Pure logic for the audio-LLM judge pilot (stdlib only, so it runs anywhere and is unit-tested).

Prompts, strict-JSON parsing, prior correction for a model that collapses onto one class,
classification metrics, and pairwise verdict aggregation over both presentation orders.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict

FAMILY_PREFIX = '{"family": "'
PAIR_PREFIX = '{"closer": "'


def family_block(families: list[str], descriptions: dict[str, str]) -> str:
    return "\n".join(f'- "{f}": {descriptions[f]}' for f in families)


def single_prompt(families: list[str], descriptions: dict[str, str], transcript: str | None = None) -> str:
    s = ("You hear one line spoken by Abelard, an older, formal ship's seneschal in a sci-fi RPG. "
         "Judge only HOW it is delivered (tone of voice, pace, energy), not what is said.\n")
    if transcript:
        s += f'Transcript of the line: "{transcript}"\n'
    return s + ("Choose the single best delivery family:\n" + family_block(families, descriptions) +
                '\nAnswer with strict JSON only, exactly: {"family": "<one of the names above>"}')


def pair_prompt(axis: str, emotion: str | None = None, instruct: str | None = None) -> str:
    """Three clips in order: REFERENCE, CLIP A, CLIP B. axis is 'voice' or 'emotion'."""
    head = ("You will hear three clips of the same character. First the REFERENCE clip, then "
            "CLIP A, then CLIP B.\n")
    if axis == "voice":
        q = ("Which of A or B sounds more like the SAME PERSON as the reference and is cleaner "
             "(no gravel, whisper, garble, glitches)? Ignore differences in emotion.")
    else:
        target = f'"{emotion}"' + (f" ({instruct})" if instruct else "")
        q = (f"The intended delivery is {target}. Which of A or B better conveys that emotion "
             "(tone, energy, pace)? Ignore small differences in voice quality.")
    return head + q + ' Answer strict JSON only: {"closer": "A"} or {"closer": "B"}'


def parse_choice(raw: str, options: list[str], key: str = "family") -> str | None:
    m = re.search(r'"' + re.escape(key) + r'"\s*:\s*"([^"]+)"', raw or "")
    if m and m.group(1).strip() in options:
        return m.group(1).strip()
    return None


def prior_correct(logprobs: dict[str, float], prior: dict[str, float]) -> dict[str, float]:
    """Subtract each class's mean log-prob over the whole set so a model that says 'stern' for
    everything is compared on how much MORE than usual it favours a class."""
    return {k: v - prior[k] for k, v in logprobs.items()}


def mean_logprobs(rows: list[dict[str, float]]) -> dict[str, float]:
    keys = rows[0].keys()
    return {k: sum(r[k] for r in rows) / len(rows) for k in keys}


def argmax(d: dict[str, float]) -> str:
    return max(d, key=d.get)


def classification_metrics(truth: list[str], pred: list[str | None], families: list[str]) -> dict:
    n = len(truth)
    correct = sum(t == p for t, p in zip(truth, pred))
    recall, support = {}, Counter(truth)
    for f in families:
        if support[f]:
            recall[f] = sum(t == p == f for t, p in zip(truth, pred)) / support[f]
    macro = sum(recall.values()) / len(recall) if recall else 0.0
    return {"n": n, "top1": correct / n if n else 0.0, "macro_recall": macro, "recall": recall,
            "families_recall_over_0.3": sum(r > 0.3 for r in recall.values()),
            "majority_baseline": max(support.values()) / n if n else 0.0,
            "parse_failures": sum(p is None for p in pred),
            "pred_distribution": dict(Counter(p for p in pred if p))}


def consistent_verdict(ab: str | None, ba: str | None) -> str | None:
    """ab = answer with (A,B) shown in original order; ba = answer with the clips swapped.
    Returns 'a' or 'b' (original identity) only when both orders name the same clip."""
    if ab not in ("A", "B") or ba not in ("A", "B"):
        return None
    first = "a" if ab == "A" else "b"
    second = "b" if ba == "A" else "a"
    return first if first == second else None


def position_bias(answers: list[str | None]) -> float:
    """Share of the most common slot answer among all valid answers (0.5 = unbiased)."""
    valid = [a for a in answers if a in ("A", "B")]
    if not valid:
        return 0.0
    return max(Counter(valid).values()) / len(valid)


def pair_agreement(verdicts: dict[str, str | None], human: dict[str, str], axes: dict[str, str]) -> dict:
    """Agreement of judge verdicts with the human's decisive answers, per axis."""
    out = {}
    for axis in sorted(set(axes.values())):
        ids = [i for i in verdicts if axes.get(i) == axis and human.get(i) in ("a", "b")]
        decided = [i for i in ids if verdicts[i] is not None]
        agree = sum(verdicts[i] == human[i] for i in decided)
        out[axis] = {"human_decisive": len(ids), "judge_consistent": len(decided), "agree": agree,
                     "agreement": agree / len(decided) if decided else None,
                     "consistent_fraction": len(decided) / len(ids) if ids else None}
    return out


def choice_logprobs(content: list[dict], options: list[str], marker: str) -> dict[str, float] | None:
    """From an OpenAI-style `logprobs.content` list (token, logprob, top_logprobs), find the token
    right after `marker` (e.g. '{"family": "') and return each option's first-token log-prob, or
    None if the marker or any option is not visible in the top candidates."""
    text = ""
    for tok in content:
        if text.endswith(marker):
            top = {t["token"].strip(): t["logprob"] for t in tok.get("top_logprobs", [])}
            top[tok["token"].strip()] = max(tok["logprob"], top.get(tok["token"].strip(), -1e9))
            out = {}
            for o in options:
                cands = [lp for t, lp in top.items() if t and o.startswith(t)]
                if not cands:
                    return None
                out[o] = max(cands)
            return out
        text += tok["token"]
    return None


def read_jsonl(path) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return [json.loads(x) for x in f if x.strip()]
    except FileNotFoundError:
        return []


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def group_by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    return g
