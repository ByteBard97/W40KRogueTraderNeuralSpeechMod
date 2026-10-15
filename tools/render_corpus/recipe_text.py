"""Text preparation for recipe renders (the Render Lab in tools/studio and the render workers share this file): what the model actually receives, stage by stage, with every stage adjustable.

  prepare(text, recipe) -> {"stages": [...], "pieces": [{"text", "display", "gap_ms", "kind"}]}

Stages, in order: clean (the game's markup), punctuation (what each mark becomes), pronunciation (lab overrides, then the shared
lexicon as braced ARPAbet), split (whole / sentence / clause / max length). The result carries each stage's text so the page can show
what changed. Pure functions, no model and no files except the lexicon the render pipeline already reads.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("tools/render_corpus", "src/TtsSidecar"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))

from clean_text import clean_for_tts  # noqa: E402

# What a punctuation mark can become. "pause:<ms>" cuts the text there and plays that much silence between the two renders.
MARKS = {
    "em_dash": r"\s*—\s*",
    "en_dash": r"\s*–\s*",
    "spaced_hyphen": r"\s+-\s+",
    "ellipsis": r"\s*(?:…|\.{3,})\s*",
    "semicolon": r"\s*;\s*",
    "colon": r"\s*:\s+",
    "parens": r"\s*[()]\s*",
}
# What each mark is replaced with, as a template for the text on each side. {pause} cuts and adds silence.
ACTIONS = ("keep", "comma", "period", "ellipsis", "space", "pause")
DEFAULT_PUNCT = {"em_dash": "keep", "en_dash": "keep", "spaced_hyphen": "keep", "ellipsis": "keep", "semicolon": "keep",
                 "colon": "keep", "parens": "keep"}
DEFAULT_GAPS_MS = {"sentence": 350, "clause": 160, "dash": 260, "ellipsis": 300, "paragraph": 600}
DEFAULT_PAUSE_MS = 250
CUT = "␞"                      # private marker for "cut here" while stages run (never reaches a model)
SPLIT_MODES = ("whole", "sentence", "clause", "max")
DEFAULT_SPLIT = {"mode": "sentence", "max_chars": 140, "min_chars": 24}
MAX_PIECE_CHARS = 1200

_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]*[A-Z0-9{])")
_CLAUSE_END = re.compile(r"(?<=[,;:])\s+")
_ABBREV = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|St|Lt|Cmdr|Cpt|Capt|Sgt|Gen|Prof|Fr|Mt|vs|etc)\.$", re.I)


def instruct_for(recipe: dict, annotation: dict | None) -> str | None:
    """The style description sent in front of the text. "annotation" is exactly what the production renders sent (including the pace phrase)."""
    mode = recipe.get("instruct", "annotation")
    if mode == "none":
        return None
    if mode == "custom":
        return (recipe.get("instruct_text") or "").strip() or None
    from annotation_bridge import for_instruct_engine
    return for_instruct_engine("", annotation)[1]


def punct_options() -> dict:
    return {"marks": list(MARKS), "actions": list(ACTIONS), "splits": list(SPLIT_MODES),
            "defaults": {"punctuation": DEFAULT_PUNCT, "gaps_ms": DEFAULT_GAPS_MS, "split": DEFAULT_SPLIT, "pause_ms": DEFAULT_PAUSE_MS}}


def apply_punctuation(text: str, rules: dict | None, pause_ms: int = DEFAULT_PAUSE_MS) -> tuple[str, list[tuple[str, int]]]:
    """(text with CUT markers where a mark became a pause, [(mark, ms), ...] in order). Unknown or "keep" marks are left alone."""
    rules = {**DEFAULT_PUNCT, **(rules or {})}
    out, pauses = text, []
    for mark, pattern in MARKS.items():
        action = rules.get(mark, "keep")
        if action == "keep":
            continue
        repl = {"comma": ", ", "ellipsis": "... ", "space": " "}.get(action)
        if action == "pause":
            def cut(_m, mark=mark):
                pauses.append((mark, pause_ms))
                return CUT
            out = re.sub(pattern, cut, out)
        elif action == "period":                        # a sentence end: the next word starts a sentence, so it gets a capital
            out = re.sub(pattern + r"([A-Za-z])?", lambda m: ". " + (m.group(1) or "").upper(), out)
        else:
            out = re.sub(pattern, lambda _m, r=repl: r, out)
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    out = re.sub(r",\s*,", ",", out)                         # a mark turned into ", " next to an existing ","
    return re.sub(r"[ \t]+", " ", out).strip(), pauses


def apply_pronunciation(text: str, overrides: list[dict] | None, lexicon: bool = True) -> str:
    """Lab overrides first ({"word": "von Valancius", "mode": "arpabet"|"plain"|"literal", "value": "..."}), then the shared lexicon.

    An override's text is wrapped so the lexicon pass cannot touch it again: arpabet becomes {PHONEMES}, literal is used as written."""
    shelf: dict[str, str] = {}
    for i, o in enumerate(sorted(overrides or [], key=lambda o: -len(o.get("word", "")))):
        word, mode, value = (o.get("word") or "").strip(), o.get("mode", "arpabet"), (o.get("value") or "").strip()
        if not word or (mode != "plain" and not value):
            continue
        out = word if mode == "plain" else ("{" + value.strip("{}") + "}" if mode == "arpabet" else value)
        key = f"⁠{i}⁠"
        text, n = re.subn(r"(?<![\w{])" + re.escape(word) + r"(?![\w}])", key, text, flags=re.I)
        if n:
            shelf[key] = out
    if lexicon:
        from phonemes import phonemize
        text = phonemize(text)
    for key, out in shelf.items():
        text = text.replace(key, out)
    return text


def _split_regex(text: str, rx: re.Pattern) -> list[str]:
    parts, last = [], 0
    for m in rx.finditer(text):
        if _ABBREV.search(text[last:m.start()]):
            continue
        parts.append(text[last:m.start()])
        last = m.end()
    parts.append(text[last:])
    return [p for p in (s.strip() for s in parts) if p]


def _glue(parts: list[str], min_chars: int, max_chars: int) -> list[str]:
    """Merge a too-short part into its neighbour, never past max_chars."""
    out: list[str] = []
    for p in parts:
        if out and (len(out[-1]) < min_chars or len(p) < min_chars) and len(out[-1]) + 1 + len(p) <= max_chars:
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return out


def _cut_long(part: str, max_chars: int) -> list[str]:
    """Break a part longer than max_chars at its last comma / space before the limit."""
    out = []
    while len(part) > max_chars:
        # prefer the last clause break (comma, semicolon, colon) in the window; only fall back to a bare space
        cut = max((part.rfind(m, 0, max_chars) for m in (", ", "; ", ": ")), default=-1)
        if cut < max_chars // 3:
            cut = part.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        out.append(part[:cut + 1].strip() if part[cut] in ",;:" else part[:cut].strip())
        part = part[cut + 1:].strip() if part[cut] in ",;: " else part[cut:].strip()
    return out + ([part] if part else [])


def split_text(text: str, split: dict | None) -> list[tuple[str, str]]:
    """[(piece, kind)] where kind is what ended the piece: sentence, clause or max."""
    s = {**DEFAULT_SPLIT, **(split or {})}
    mode, mx, mn = s["mode"], min(int(s["max_chars"]), MAX_PIECE_CHARS), int(s["min_chars"])
    if mode == "whole":
        return [(text, "sentence")]
    sentences = _split_regex(text, _SENTENCE_END)
    parts: list[tuple[str, str]] = []
    for sent in sentences:
        if mode == "sentence":
            pieces = [(sent, "sentence")]
        else:
            clauses = _split_regex(sent, _CLAUSE_END) if mode == "clause" else [sent]
            glued = _glue(clauses, mn, mx)
            pieces = [(c, "clause") for c in glued]
            if pieces:
                pieces[-1] = (pieces[-1][0], "sentence")
        for p, kind in pieces:
            if mode in ("max", "clause", "sentence") and len(p) > mx:
                cut = _cut_long(p, mx)
                parts += [(c, "max") for c in cut[:-1]] + [(cut[-1], kind)]
            else:
                parts.append((p, kind))
    if mode == "sentence":
        glued = _glue([p for p, _ in parts], mn, mx if mx else MAX_PIECE_CHARS)
        parts = [(g, "sentence") for g in glued]
    return parts or [(text, "sentence")]


def prepare(text: str, recipe: dict | None = None) -> dict:
    r = recipe or {}
    gaps = {**DEFAULT_GAPS_MS, **(r.get("gaps_ms") or {})}
    stages = [{"name": "source", "text": text}]
    cleaned = clean_for_tts(text) if r.get("clean", True) else text
    stages.append({"name": "clean", "text": cleaned})
    punct, pauses = apply_punctuation(cleaned, r.get("punctuation"), int(r.get("pause_ms", DEFAULT_PAUSE_MS)))
    stages.append({"name": "punctuation", "text": punct.replace(CUT, " | ")})
    spoken = apply_pronunciation(punct, r.get("pronunciation"), bool(r.get("lexicon", True)))
    stages.append({"name": "pronunciation", "text": spoken.replace(CUT, " | ")})
    pieces: list[dict] = []
    pause_iter = iter(pauses)
    for block in spoken.split(CUT):
        block = block.strip()
        if not block:
            continue
        sub = split_text(block, r.get("split"))
        for i, (p, kind) in enumerate(sub):
            last = i == len(sub) - 1
            pieces.append({"text": p, "kind": kind if not last else "block_end", "gap_ms": gaps.get(kind, gaps["clause"]) if not last else None})
        # the gap after a block that ended at a pause mark is that mark's pause; the final block has none
        mark = next(pause_iter, None)
        pieces[-1]["gap_ms"] = mark[1] if mark else 0
        pieces[-1]["kind"] = "dash" if mark and mark[0] in ("em_dash", "en_dash", "spaced_hyphen") else "pause" if mark else "end"
    # the gap after a sentence-ending piece inside a block is the sentence gap, after a clause the clause gap
    for p in pieces:
        if p["kind"] == "sentence":
            p["gap_ms"] = gaps["sentence"]
    if pieces:
        pieces[-1]["gap_ms"] = 0
    stages.append({"name": "split", "text": " | ".join(p["text"] for p in pieces)})
    return {"stages": stages, "pieces": [{**p, "display": p["text"]} for p in pieces]}
