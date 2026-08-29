"""Translate the engine-neutral annotation schema (tools/annotate/schema.py) into whatever a
specific TTS engine understands. One function per engine family; add a case here, not in the
engine adapters, so the mapping stays in one place as new annotation fields are added.
"""
from __future__ import annotations

# Chatterbox-Turbo's 19 trained paralinguistic tokens (see data/lexicon or the model card).
_CHATTERBOX_TAGS = {
    "happy": "happy", "sad": "crying", "angry": "angry", "fear": "fear",
    "surprised": "surprised", "sarcastic": "sarcastic", "dramatic": "dramatic",
    "whisper": "whispering", "amused": "chuckle",
}
_CHATTERBOX_NONVERBAL = {"laugh": "laugh", "chuckle": "chuckle", "sigh": "sigh", "gasp": "gasp",
                         "groan": "groan", "sniff": "sniff", "cough": "cough",
                         "clear_throat": "clear throat", "shush": "shush"}


def for_chatterbox(text: str, annotation: dict | None) -> tuple[str, float]:
    """Returns (text_with_tags, exaggeration). No annotation -> pass-through, exaggeration=0.5."""
    if not annotation:
        return text, 0.5
    tags = []
    tag = _CHATTERBOX_TAGS.get(annotation.get("emotion"))
    if tag:
        tags.append(f"[{tag}]")
    for nv in annotation.get("nonverbal", []):
        mapped = _CHATTERBOX_NONVERBAL.get(nv)
        if mapped:
            tags.append(f"[{mapped}]")
    prefix = " ".join(tags) + " " if tags else ""
    exaggeration = 0.3 + 0.5 * float(annotation.get("intensity", 0.3))
    return prefix + text, min(1.0, exaggeration)


def for_instruct_engine(text: str, annotation: dict | None) -> tuple[str, str | None]:
    """Qwen3-TTS / Fish S2 style: (text, instruct). instruct=None -> engine default delivery."""
    if not annotation:
        return text, None
    instruct = annotation.get("instruct")
    pace = annotation.get("pace")
    if pace and pace != "normal" and instruct:
        instruct = f"{instruct} Speak at a {pace} pace."
    return text, instruct


def for_pace_only_engine(text: str, annotation: dict | None) -> tuple[str, float]:
    """Piper/Kokoro style: (text, speed_multiplier). No tag/instruct support."""
    if not annotation:
        return text, 1.0
    speed = {"slow": 0.85, "normal": 1.0, "fast": 1.15}.get(annotation.get("pace", "normal"), 1.0)
    return text, speed
