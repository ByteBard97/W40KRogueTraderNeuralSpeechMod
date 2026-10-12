"""Pure logic for working out who speaks the unattributed (default_speaker) lines.

One LLM call per conversation chunk: the model sees the conversation with the unnamed lines numbered and
returns a roster of the characters it can identify plus a speaker for every numbered line. No network or
torch here, so it unit-tests offline; run_roster.py does the I/O.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from gather_evidence import clean

NARRATOR = "NARRATOR"
GENDERS = ["male", "female", "none", "unknown"]
SPECIES = ["human", "astartes", "ork", "eldar", "drukhari", "tyranid", "daemon", "machine", "xenos_other", "unknown"]
AGES = ["child", "young", "adult", "middle", "old", "unknown"]
# Post-processing labels the model may pick from. Only the labels live here; the DSP behind each one is tuned later
# in tools/voice_design (fx.py / dsp.js). Keep this list in step with the audition presets when they exist.
FX_CATEGORIES = {
    "none": "ordinary voice, no processing (the default)",
    "machine": "servitors, terminals, cogitators, anything mechanical or 'hissing, robotic'",
    "vox_channel": "heard over a vox, radio or comm channel ('the vox crackles', 'static')",
    "helmet": "speaking from inside a helmet or sealed suit (astartes, voidsuit, rebreather)",
    "ethereal": "psykers, warp entities, ghosts, 'otherworldly', 'cold and enveloping', voice in the mind",
    "monstrous": "daemons, huge or inhuman creatures, 'guttural', 'inhuman growl'",
    "cavernous": "speaking in a vast hall, cathedral or void so the room itself rings",
}
FX_NAMES = [k for k in FX_CATEGORIES if k != "none"]
MAX_FX = 2  # more than two stacked effects turns speech to mush
# Fixed stacking order regardless of the order the model lists them: what the voice is first, then how it is heard.
FX_ORDER = ["machine", "monstrous", "ethereal", "helmet", "vox_channel", "cavernous"]


def clean_fx(value) -> list[str]:
    """Model fx answer -> ordered list of at most MAX_FX valid categories ([] = no processing). Accepts a bare string."""
    items = [value] if isinstance(value, str) else (value if isinstance(value, list) else [])
    keep = {v for v in items if v in FX_NAMES}
    return [f for f in FX_ORDER if f in keep][:MAX_FX]
CHUNK_LINES = 40  # text lines per call
CONTEXT_LINES = 6  # lines of lead-in carried into the next chunk
MAX_LINE_CHARS = 420

SCHEMA = {
    "type": "object",
    "properties": {
        "roster": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"},
            "name": {"type": ["string", "null"]},
            "label": {"type": "string"},
            "gender": {"enum": GENDERS},
            "species": {"enum": SPECIES},
            "age": {"enum": AGES},
            "role": {"type": "string"},
            "baseline_voice": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
            "fx": {"type": "array", "items": {"enum": FX_NAMES}, "maxItems": MAX_FX, "uniqueItems": True},
        }, "required": ["id", "name", "label", "gender", "species", "age", "role", "baseline_voice", "evidence", "confidence", "fx"]}},
        "lines": {"type": "array", "items": {"type": "object", "properties": {
            "n": {"type": "integer"},
            "speaker": {"type": "string"},
            "delivery": {"type": "string"},
            "fx": {"type": "array", "items": {"enum": FX_NAMES}, "maxItems": MAX_FX, "uniqueItems": True},
        }, "required": ["n", "speaker", "delivery", "fx"]}},
    },
    "required": ["roster", "lines"],
}

SYSTEM = """You help cast voices for a video game. You are shown a conversation from Warhammer 40,000: Rogue Trader. \
Some lines are numbered with #n and a speaker of ??: the game does not say who speaks them. Lines may mix narration \
and quoted speech; the quoted words are what the character says, the rest is narration.

For each ?? line decide who speaks the quoted words. Use only the text: names the character gives or is given, \
pronouns, descriptions of their body, clothing, implants, voice or manner, how others address them, and the \
conversation name. Rules:
- A line with no quoted speech at all is narration: speaker "NARRATOR".
- Identify each distinct character once in the roster, with a short id (lowercase, no spaces). "name" is a personal name the text gives them (Vir, Leads-Ahead, Alva-9), else null. A title or description such as "the elder", "Tech-Priest" or "Pirate Vendor" is NOT a name: put it in "label" and leave name null.
- gender: read the pronouns and nouns in the narration around their lines (he/his/him/man/sir/father = male; she/her/woman/lady/mother = female). Pronouns are enough; you do not need a name. Use "unknown" only if the text really gives nothing. Never guess from a name alone.
- species is "human" unless the text says otherwise; use "machine" for servitors, terminals and other mechanical voices, "ork"/"eldar"/"drukhari"/etc. when named. age comes from the text (grizzled, elderly, youth, boy); "unknown" if the text is silent.
- evidence is 1-3 short exact quotes from the conversation that support what you decided. No quote means lower confidence.
- baseline_voice is one sentence on how this character sounds (age, timbre, pace, manner), drawn from the text. Do not invent an accent.
- delivery is a few words describing HOW the line is spoken, taken from the narration (e.g. "voice hardens, aloof"), else "". Never copy the spoken words into delivery.
- If a character listed as identified earlier gives their name or is named in these lines (e.g. "The name of this ruler is Leads-Ahead"), include them again in the roster with the same id and the name filled in.
- Characters already named in brackets (like [Cassia]) are known; do not put them in the roster.
- confidence is 0 to 1 for the roster entry as a whole.
- fx is a list (empty for none, at most two) of post-processing for the character's normal voice, from this list only:
""" + "\n".join(f"    {k}: {v}" for k, v in FX_CATEGORIES.items() if k != "none") + """
  Use [] unless the text clearly says the voice is processed, mechanical, transmitted or unearthly; most people are []. Two together is for
  things like a helmeted speaker heard over a vox ["helmet","vox_channel"].
- Each line also has an fx list. Use the character's own fx, except when that line is heard differently (e.g. an ordinary person heard over a vox channel gets ["vox_channel"] on that line only)."""


def is_pure_narration(text: str) -> bool:
    return '"' not in text and "“" not in text


def conversation_lines(conv: dict, targets: set[str]) -> list[dict]:
    """Numbered text lines of a conversation; `target` marks the lines we must attribute."""
    out = []
    for ln in conv["lines"]:
        text = ln.get("text")
        if not text or ln.get("kind") not in ("cue", "answer"):
            continue
        sp = ln.get("speaker") or {}
        kind = sp.get("kind")
        if kind == "player":
            who = "PLAYER"
        elif kind == "narrator":
            who = NARRATOR
        elif kind in ("unit", "unit_guess"):
            who = sp.get("name") or "?"
        else:
            who = "??"
        out.append({"n": len(out) + 1, "who": who, "text": clean(text)[:MAX_LINE_CHARS],
                    "key": ln.get("text_key"), "target": ln.get("text_key") in targets and kind == "default_speaker"})
    return out


def chunks(lines: list[dict], size: int = CHUNK_LINES, context: int = CONTEXT_LINES):
    """Yield (lead_in, body) windows; only `body` lines are attributed in that call."""
    for start in range(0, len(lines), size):
        body = lines[start:start + size]
        if any(l["target"] for l in body):
            yield lines[max(0, start - context):start], body


def render_line(l: dict, number: bool) -> str:
    who = f"[{l['who']}]" if l["who"] != "??" else "[??]"
    tag = f"#{l['n']} " if number and l["target"] else ""
    return f"{tag}{who} {l['text']}"


def build_prompt(conv_name: str, lead_in: list[dict], body: list[dict], known: list[dict] | None = None) -> str:
    parts = [f"Conversation: {conv_name}"]
    if known:
        parts.append("Characters identified earlier in this conversation (reuse their id when it is the same person):\n"
                     + "\n".join(f"- {k['id']}: {k.get('name') or 'unnamed'}, {k['gender']}, {k['species']}, {k['role']}" for k in known))
    if lead_in:
        parts.append("Earlier lines (context only, do not attribute):\n" + "\n".join(render_line(l, False) for l in lead_in))
    parts.append("Lines:\n" + "\n".join(render_line(l, True) for l in body))
    targets = [l["n"] for l in body if l["target"]]
    parts.append("Attribute these line numbers: " + ", ".join(f"#{n}" for n in targets))
    return "\n\n".join(parts)


def validate(result: dict, body: list[dict]) -> dict:
    """Make a model answer safe to use: drop unknown line numbers, fill gaps, fix enums and dangling speakers."""
    want = {l["n"]: l for l in body if l["target"]}
    conf = result.get("_conf") or {"roster": {}, "lines": {}}
    roster = []
    seen = set()
    for r in result.get("roster", []):
        rid = re.sub(r"[^a-z0-9_]+", "", str(r.get("id", "")).lower())
        if not rid or rid in seen or rid == NARRATOR.lower():
            continue
        seen.add(rid)
        roster.append({
            "conf": dict(conf["roster"].get(str(r.get("id")), {})),
            "id": rid, "name": r.get("name") or None,
            "gender": r.get("gender") if r.get("gender") in GENDERS else "unknown",
            "species": r.get("species") if r.get("species") in SPECIES else "unknown",
            "age": r.get("age") if r.get("age") in AGES else "unknown",
            "label": str(r.get("label", "")), "role": str(r.get("role", "")), "baseline_voice": str(r.get("baseline_voice", "")),
            "evidence": [str(e) for e in r.get("evidence", [])][:3],
            "confidence": min(1.0, max(0.0, float(r.get("confidence", 0) or 0))),
            "fx": clean_fx(r.get("fx")),
        })
    lines = {}
    for a in result.get("lines", []):
        n = a.get("n")
        if n not in want or n in lines:
            continue
        sp = str(a.get("speaker", "")).strip()
        sp = NARRATOR if sp.upper() == NARRATOR else re.sub(r"[^a-z0-9_]+", "", sp.lower())
        if sp != NARRATOR and sp not in seen:
            sp = "unknown"
        delivery = str(a.get("delivery", "")).strip()
        if '"' in delivery or delivery.lower() in want[n]["text"].lower():  # the model copied the quote instead of a delivery cue
            delivery = ""
        fx = clean_fx(a.get("fx"))
        lines[n] = {"n": n, "key": want[n]["key"], "speaker": sp, "delivery": delivery, "fx": fx,
                    "conf": dict(conf["lines"].get(str(n), {}))}
    for n, l in want.items():
        if n not in lines:  # model skipped it; pure narration is safe to infer, the rest is unknown
            lines[n] = {"n": n, "key": l["key"], "speaker": NARRATOR if is_pure_narration(l["text"]) else "unknown", "delivery": "", "fx": []}
        elif lines[n]["speaker"] != NARRATOR and is_pure_narration(l["text"]):
            lines[n]["speaker"], lines[n]["fx"] = NARRATOR, []  # a line with no quoted speech is narration whatever the model said
    return {"roster": roster, "lines": [lines[n] for n in sorted(lines)]}


_MALE = re.compile(r"\b(he|him|his|himself|man|men|sir|father|brother|lord|king|boy|male)\b", re.I)
_FEMALE = re.compile(r"\b(she|her|hers|herself|woman|women|madam|lady|mother|sister|queen|girl|female)\b", re.I)
_QUOTED = re.compile(r'"[^"]*"|\u201c[^\u201d]*\u201d')


def narration_gender(texts: list[str]) -> str:
    """Gender from pronouns in the narration (quoted speech removed) of lines a speaker owns; unknown unless clear."""
    m = f = 0
    for t in texts:
        outside = _QUOTED.sub(" ", t)
        m += len(_MALE.findall(outside))
        f += len(_FEMALE.findall(outside))
    if m >= 2 and m >= 2 * f:
        return "male"
    if f >= 2 and f >= 2 * m:
        return "female"
    return "unknown"


def fill_gender(result: dict, lines: list[dict]) -> None:
    """Replace an 'unknown' roster gender with the pronoun count over that speaker's own lines."""
    text_by_key = {l["key"]: l["text"] for l in lines}
    for r in result["roster"]:
        if r["gender"] == "unknown":
            owned = [text_by_key[a["key"]] for a in result["lines"] if a["speaker"] == r["id"] and a["key"] in text_by_key]
            g = narration_gender(owned)
            if g != "unknown":
                r["gender"], r["gender_source"] = g, "pronouns"
                r.get("conf", {}).pop("gender", None)


def normalise_name(name: str | None) -> str | None:
    return re.sub(r"[^a-z]+", " ", name.lower()).strip() if name else None


def pick_fx(members) -> list[str]:
    """Categories listed in more than half of an identity's appearances (one odd conversation can't colour a character)."""
    n = len(members)
    keep = {f for f in FX_ORDER if sum(f in (r.get("fx") or []) for _, r in members) * 2 > n}
    return [f for f in FX_ORDER if f in keep][:MAX_FX]


def merge_rosters(per_conv: dict[str, list[dict]]) -> dict[str, dict]:
    """Collapse per-conversation roster entries into one identity per name (unnamed ones stay separate).

    Returns {identity key: {name, gender, species, age, roles, voices, evidence, conversations, confidence}}.
    The gender/species/age of an identity is the most common non-unknown value across its appearances.
    """
    groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for conv, roster in per_conv.items():
        for r in roster:
            key = normalise_name(r["name"]) or f"unnamed:{conv}:{r['id']}"
            groups[key].append((conv, r))
    merged = {}
    for key, members in groups.items():
        def pick(field):
            vals = [r[field] for _, r in members if r[field] != "unknown"]
            return max(set(vals), key=vals.count) if vals else "unknown"
        merged[key] = {
            "name": members[0][1]["name"], "gender": pick("gender"), "species": pick("species"), "age": pick("age"),
            "fx": pick_fx(members),
            "roles": sorted({r["role"] for _, r in members if r["role"]}),
            "voices": [r["baseline_voice"] for _, r in members if r["baseline_voice"]],
            "evidence": [e for _, r in members for e in r["evidence"]][:6],
            "conversations": sorted({c for c, _ in members}),
            "confidence": sum(r["confidence"] for _, r in members) / len(members),
        }
    return merged


def refine_roster(roster: list[dict], new: list[dict]) -> None:
    """Fold a chunk's roster into the running one. Later chunks can only add information: a name learnt late
    (e.g. a character who introduces herself in the second half), a gender/species/age that was unknown, more evidence."""
    by_id = {r["id"]: r for r in roster}
    for r in new:
        old = by_id.get(r["id"])
        if old is None:
            roster.append(r)
            by_id[r["id"]] = r
            continue
        if r["name"] and not old["name"]:
            old["name"] = r["name"]
        for f in ("gender", "species", "age"):
            if old[f] == "unknown" and r[f] != "unknown":
                old[f] = r[f]
                if f in r.get("conf", {}):
                    old.setdefault("conf", {})[f] = r["conf"][f]
        old["evidence"] = (old["evidence"] + [e for e in r["evidence"] if e not in old["evidence"]])[:3]
        old["fx"] = old["fx"] or r["fx"]
        if len(r["baseline_voice"]) > len(old["baseline_voice"]):
            old["baseline_voice"] = r["baseline_voice"]
        old["confidence"] = max(old["confidence"], r["confidence"])


def attribute(conv: dict, targets: set[str], complete) -> dict:
    """Run the whole conversation through `complete(system, user, schema) -> dict`; returns {roster, lines}."""
    lines = conversation_lines(conv, targets)
    roster: list[dict] = []
    out_lines: list[dict] = []
    for lead_in, body in chunks(lines):
        # pure-narration lines never need the model
        pending = [l for l in body if l["target"] and not is_pure_narration(l["text"])]
        if not pending:
            out_lines += [{"n": l["n"], "key": l["key"], "speaker": NARRATOR, "delivery": "", "fx": []} for l in body if l["target"]]
            continue
        res = validate(complete(SYSTEM, build_prompt(conv["name"], lead_in, body, roster), SCHEMA), body)
        refine_roster(roster, res["roster"])
        out_lines += res["lines"]
    used = {a["speaker"] for a in out_lines}
    out = {"conversation": conv["name"], "roster": [r for r in roster if r["id"] in used], "lines": out_lines}  # drop characters nobody speaks as
    fill_gender(out, lines)
    return out
