"""Per-line delivery stage: re-label a line's emotion and, for long speech, propose where to split it.

One model call per line. The model sees the speaker, a little surrounding conversation and the line cut into
numbered sentences, and returns one or more segments (each ends at a sentence boundary) with a closed-set emotion,
intensity and pace plus a short instruct sentence for the renderer. Most lines come back as a single segment.
Pure logic only (no network); run_segment.py does the I/O.
"""
from __future__ import annotations

import json
import math
import re

import confidence as C

EMOTIONS = ["neutral", "angry", "sad", "dramatic", "commanding", "sarcastic", "amused", "fear", "happy", "pleading", "surprised", "whisper"]
PACES = ["slow", "normal", "fast"]
INTENSITIES = [1, 2, 3, 4, 5]
INTENSITY_VALUE = {1: 0.15, 2: 0.3, 3: 0.5, 4: 0.7, 5: 0.9}
MIN_SEGMENT_CHARS = 120   # VoxCPM2 is unstable on very short inputs; shorter segments are merged into a neighbour
MIN_SENTENCE_CHARS = 25   # "I..." or "decisively." on their own are fragments of the sentence next to them
MIN_LINE_CHARS = 450      # only lines at least this long are offered for splitting (shorter ones are always one segment)
MAX_SEGMENTS = 5

SCHEMA = {
    "type": "object",
    "properties": {"segments": {"type": "array", "minItems": 1, "maxItems": MAX_SEGMENTS, "items": {
        "type": "object",
        "properties": {
            "end_sentence": {"type": "integer"},
            "emotion": {"enum": EMOTIONS},
            "intensity": {"enum": INTENSITIES},
            "pace": {"enum": PACES},
            "instruct": {"type": "string"},
        },
        "required": ["end_sentence", "emotion", "intensity", "pace", "instruct"],
    }}},
    "required": ["segments"],
}

SYSTEM = """You direct voice actors for a video game (Warhammer 40,000: Rogue Trader). You are shown one line of dialogue \
split into numbered sentences, with the speaker and a little of the conversation around it. Decide how it should be delivered.

Return the line as one or more segments in order. Each segment ends at a sentence number (end_sentence); the last must be the final sentence.
- A line under about 450 characters has ONE delivery: return a single segment ending at the last sentence.
- For a longer line, read it as a performance. Find the turning points where the speaker's feeling changes (calm to terror, wry to \
furious, defiant to broken, a build-up to a reveal) and start a new segment there. A long speech that goes somewhere emotionally \
should usually have 2 or 3 segments. A long speech that stays in one mood the whole way (a steady explanation, a sustained rant, \
a solemn recollection) stays as one segment.
- Do not split just to vary the emotion label, and do not cut a rhetorical build ("Once... Twice... And thrice..."), a list, a pause or an ellipsis in half.
- emotion is one of: """ + ", ".join(EMOTIONS) + """. neutral is only for flat reporting; pick the real feeling when there is one.
- intensity is 1 (barely) to 5 (extreme). pace is slow, normal or fast.
- instruct is one short sentence (under 20 words) telling a voice actor how to say that segment, specific to this speaker and moment \
(e.g. "Hushed and shaken, as if afraid to say it aloud"). Do not describe the setting or quote the line."""


def split_sentences(text: str) -> list[str]:
    """Sentences for choosing split points. Ellipses and tiny fragments never form a boundary by themselves."""
    text = re.sub(r"\s+", " ", text.strip())
    pieces, start = [], 0
    for m in re.finditer(r"(\.\.\.|…|[.!?])[\"”']?\s+(?=[\"“'A-Z0-9])", text):
        pieces.append(text[start:m.end()].strip())
        start = m.end()
    pieces.append(text[start:].strip())
    out: list[str] = []
    for p in pieces:
        if not p:
            continue
        if out and (len(out[-1]) < MIN_SENTENCE_CHARS):
            out[-1] = out[-1] + " " + p  # previous piece was a fragment: join it forward
        else:
            out.append(p)
    if len(out) > 1 and len(out[-1]) < MIN_SENTENCE_CHARS:
        tail = out.pop()  # a trailing fragment ("decisively.") belongs to the sentence before
        out[-1] = out[-1] + " " + tail
    return out


def build_prompt(conv_name: str, speaker: str, sentences: list[str], before: list[str], after: list[str], voice: str = "") -> str:
    parts = [f"Conversation: {conv_name}", f"Speaker: {speaker}" + (f" ({voice})" if voice else "")]
    if before:
        parts.append("Just before:\n" + "\n".join(f"- {b[:260]}" for b in before))
    parts.append("The line to direct:\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, 1)))
    if after:
        parts.append("Just after:\n" + "\n".join(f"- {a[:260]}" for a in after))
    parts.append(f"The line has {len(sentences)} sentence(s).")
    return "\n\n".join(parts)


def validate(result: dict, sentences: list[str], min_chars: int = MIN_SEGMENT_CHARS) -> list[dict]:
    """Model answer -> clean segments covering every sentence exactly once, each at least `min_chars` long."""
    n = len(sentences)
    raw = []
    last = 0
    for s in result.get("segments", []):
        end = s.get("end_sentence")
        if not isinstance(end, int) or end <= last or end > n:
            continue
        raw.append({"end": end, "emotion": s.get("emotion") if s.get("emotion") in EMOTIONS else "neutral",
                    "intensity": s.get("intensity") if s.get("intensity") in INTENSITIES else 2,
                    "pace": s.get("pace") if s.get("pace") in PACES else "normal",
                    "instruct": str(s.get("instruct", "")).strip(), "conf": dict(s.get("conf", {}))})
        last = end
    if not raw:
        raw = [{"end": n, "emotion": "neutral", "intensity": 2, "pace": "normal", "instruct": "", "conf": {}}]
    raw[-1]["end"] = n  # the last segment always runs to the end
    segs, start = [], 0
    for r in raw:
        segs.append({**r, "start": start, "text": " ".join(sentences[start:r["end"]])})
        start = r["end"]
    # merge segments that are too short into the longer neighbour, keeping that neighbour's delivery
    i = 0
    while len(segs) > 1 and i < len(segs):
        if len(segs[i]["text"]) >= min_chars:
            i += 1
            continue
        j = i - 1 if i == len(segs) - 1 else (i + 1 if i == 0 else (i - 1 if len(segs[i - 1]["text"]) >= len(segs[i + 1]["text"]) else i + 1))
        a, b = sorted((i, j))
        keep = segs[j]
        merged = {**keep, "start": segs[a]["start"], "end": segs[b]["end"], "text": segs[a]["text"] + " " + segs[b]["text"]}
        segs[a:b + 1] = [merged]
        i = 0
    for s in segs:
        s["intensity_value"] = INTENSITY_VALUE[s["intensity"]]
    return segs


_FIELD = re.compile(r'"(end_sentence|emotion|intensity|pace)"\s*:\s*("(?:[^"\\]|\\.)*"|-?\d+)')


def segment_confidence(tokens: list[dict], n_sentences: int) -> list[dict]:
    """Per-segment probabilities (renormalised over the allowed values) for end_sentence, emotion, intensity, pace."""
    text = "".join(t["token"] for t in tokens)
    spans, pos = [], 0
    for t in tokens:
        spans.append((pos, pos + len(t["token"])))
        pos += len(t["token"])
    allowed = {"emotion": EMOTIONS, "pace": PACES, "intensity": [str(i) for i in INTENSITIES],
               "end_sentence": [str(i) for i in range(1, n_sentences + 1)]}
    out: list[dict] = []
    for m in _FIELD.finditer(text):
        key, val = m.group(1), m.group(2)
        if key == "end_sentence":
            out.append({})
        quoted = val.startswith('"')
        lo, hi = (m.start(2) + 1, m.end(2) - 1) if quoted else (m.start(2), m.end(2))
        if out:
            out[-1][key] = round(C._prob(tokens, spans, lo, hi, allowed[key], val.strip('"')), 4)
    return out


def attach_confidence(result: dict, conf: list[dict]) -> dict:
    for seg, c in zip(result.get("segments", []), conf):
        seg["conf"] = c
    return result


def review_reasons(segs: list[dict], emotion_p: float = 0.3, split_p: float = 0.6, torn: float = 0.5) -> list[str]:
    """Why a human should look at this line: a split the model was unsure about, a shaky emotion, or a line it nearly split."""
    out = []
    for i, s in enumerate(segs):
        c = s.get("conf", {})
        if c.get("emotion", 1.0) < emotion_p:  # emotion labels are fuzzy, so only real doubt counts
            out.append(f"segment {i + 1}: emotion={s['emotion']} p={c['emotion']:.2f}")
        if len(segs) > 1 and i < len(segs) - 1 and c.get("end_sentence", 1.0) < split_p:
            out.append(f"split after sentence {s['end']} p={c['end_sentence']:.2f}")
    if len(segs) > 1:
        out.append(f"split into {len(segs)} segments")
    elif segs and segs[0].get("conf", {}).get("end_sentence", 1.0) < torn:
        out.append(f"torn about splitting (p(no split)={segs[0]['conf']['end_sentence']:.2f})")
    return out
