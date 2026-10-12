"""Turn the token log-probabilities of a constrained JSON answer into per-field confidence.

llama-server returns, for every generated token, its log-probability. The answer is JSON in a fixed key order,
so the characters of each decided value ("gender": "male", "speaker": "vir", the fx list) can be located in the
text and the probability of the tokens that spell them multiplied together. That is the model's own probability of
having written that value, which is far better calibrated than the confidence number it reports about itself.
"""
from __future__ import annotations

import math
import re

_FIELD = re.compile(r'"(id|gender|species|age|n|speaker|fx)"\s*:\s*("(?:[^"\\]|\\.)*"|-?\d+|\[[^\]]*\])')
_ITEM = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _prob(tokens: list[dict], spans: list[tuple[int, int]], lo: int, hi: int,
          allowed: list[str] | None = None, value: str = "") -> float:
    """Product of probabilities of the tokens overlapping characters [lo, hi); with `allowed`, each token that
    starts inside the value is renormalised over the continuations the schema permits."""
    p = 1.0
    done = ""
    for (a, b), t in zip(spans, tokens):
        if a < hi and b > lo:
            if allowed is not None and a >= lo and value.startswith(done + t["token"].strip()):
                p *= _renorm(t, allowed, done)
            else:
                p *= math.exp(t["logprob"])
            done += t["token"].strip() if a >= lo else ""
    return p


def _renorm(tok: dict, valid_prefixes: list[str], chosen_prefix: str) -> float:
    """Probability of `tok` among only the alternatives the schema allows at this position.

    The grammar forces a value from the enum, but the logprobs are the model's raw preference: if it wanted to write
    "elderly" (0.92) and was forced to "old" (0.08), the raw 0.08 says nothing about whether "old" beat "young".
    Renormalising over the tokens that could still start an allowed value fixes that.
    """
    alts = {a["token"]: math.exp(a["logprob"]) for a in tok.get("top_logprobs") or []}
    alts[tok["token"]] = math.exp(tok["logprob"])
    ok = {t: p for t, p in alts.items() if t.strip() and any(v.startswith(chosen_prefix + t.lstrip()) for v in valid_prefixes)}
    total = sum(ok.values())
    return ok.get(tok["token"], 0.0) / total if total > 0 else math.exp(tok["logprob"])


def field_confidence(tokens: list[dict], enums: dict[str, list[str]] | None = None) -> dict:
    """tokens: [{"token": str, "logprob": float, "top_logprobs": [...]}, ...] for the whole answer.
    enums: allowed values per field ("gender", "species", "age", "fx"); "speaker" is derived from the roster ids.

    Returns {"roster": {id: {gender, species, age, fx}}, "lines": {n: {speaker, fx}}} with probabilities 0-1.
    An fx list is as confident as its least likely item; an empty list uses the probability of closing it straight away.
    """
    text = "".join(t["token"] for t in tokens)
    spans, pos = [], 0
    for t in tokens:
        spans.append((pos, pos + len(t["token"])))
        pos += len(t["token"])
    cut = text.find('"lines"')
    cut = len(text) if cut < 0 else cut
    roster: dict[str, dict] = {}
    lines: dict[str, dict] = {}
    cur_id = cur_n = None
    for m in _FIELD.finditer(text):
        key, val = m.group(1), m.group(2)
        in_roster = m.start() < cut
        if key == "id" and in_roster:
            cur_id = val.strip('"')
            roster[cur_id] = {}
            continue
        if key == "n" and not in_roster:
            cur_n = val
            lines[cur_n] = {}
            continue
        allowed = None
        if enums is not None:
            if key == "speaker":
                allowed = [i.lower() for i in roster] + ["narrator", "unknown"]
            elif key in enums:
                allowed = list(enums[key])
        if val.startswith("["):
            inner_lo = m.start(2) + 1
            items = list(_ITEM.finditer(val))
            if items:
                p = min(_prob(tokens, spans, inner_lo + i.start(1), inner_lo + i.end(1), allowed, i.group(1)) for i in items)
            else:
                p = _prob(tokens, spans, m.end(2) - 1, m.end(2))  # the closing bracket: "nothing" chosen
        else:
            p = _prob(tokens, spans, m.start(2) + 1, m.end(2) - 1, allowed, val.strip('"')) if val.startswith('"') \
                else _prob(tokens, spans, m.start(2), m.end(2))
        if in_roster and cur_id is not None and key in ("gender", "species", "age", "fx"):
            roster[cur_id][key] = round(p, 4)
        elif not in_roster and cur_n is not None and key in ("speaker", "fx"):
            lines[cur_n][key] = round(p, 4)
    return {"roster": roster, "lines": lines}
