r"""Robust extraction of the {"labels": [...], "notes": ...} JSON object a 7B model was
asked to emit, tolerating prose wrapping and dropping individually malformed entries.

Uses brace-depth tracking rather than a greedy regex: a naive r"\{.*\}" span from the
first "{" to the last "}" breaks the moment the model echoes any brace-containing prose
(e.g. part of its own instructions) before or after the real JSON object, or emits more
than one brace pair — the combined span is not valid JSON and a greedy match reports a
parse failure on output that actually contained a perfectly good answer."""
from __future__ import annotations

import json


def _iter_json_candidates(raw_text: str):
    """Yields each top-level, brace-balanced {...} substring of raw_text, in the order
    they appear."""
    depth = 0
    start = None
    for i, ch in enumerate(raw_text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    yield raw_text[start:i + 1]
                    start = None


def parse_model_response(raw_text: str) -> dict | None:
    # Try the whole response as-is first (the common case), then each balanced-brace
    # candidate found within it, most-recent-first — if the model echoed an example
    # before giving its real answer, the real answer comes later in the text.
    candidates = [raw_text] + list(reversed(list(_iter_json_candidates(raw_text))))
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or "labels" not in obj or not isinstance(obj["labels"], list):
            continue

        labels = []
        for item in obj["labels"]:
            if not isinstance(item, dict):
                continue
            word = item.get("word")
            confidence = item.get("confidence")
            if not isinstance(word, str) or not isinstance(confidence, (int, float)):
                continue
            labels.append({"word": word, "confidence": max(0.0, min(1.0, float(confidence)))})
        if not labels:
            continue

        notes = obj.get("notes", "")
        return {"labels": labels, "notes": notes if isinstance(notes, str) else ""}
    return None
