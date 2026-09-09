"""Translate the engine-neutral annotation schema (tools/annotate/schema.py) into whatever a
specific TTS engine understands. One function per engine family; add a case here, not in the
engine adapters, so the mapping stays in one place as new annotation fields are added.

`route()` is the single source of truth for which engine gets which treatment - both the
production sidecar (server.py) and the offline bake-off tool (run_bakeoff.py) call it, so they
can't drift out of sync the way they once did (server.py had its own ENGINE_KIND dict that was
never updated when chatterbox/higgs/fish_s2cpp were added, and run_bakeoff.py never applied any
acting direction at all - see docs/research or PROJECT_PLAN.md for how that was found, 2026-09-05).
"""
from __future__ import annotations

# Only the 9 nonverbal tags Resemble AI's own engineers confirm are reliably trained (see
# added_tokens.json IDs 50257-50275: clear throat/sigh/shush/cough/groan/sniff/gasp/chuckle/
# laugh). The emotion-word tags this used to also emit (happy/crying/angry/fear/surprised/
# sarcastic/dramatic/whispering) exist as tokens but are NOT reliably trained - a live A/B test
# this session found happy/crying/angry acoustically near-indistinguishable. Emotion + intensity
# are expressed instead through exaggeration/cfg_weight below, which are genuinely responsive
# controls on the original (non-Turbo) checkpoint (verified: exaggeration 0.15->1.0 roughly
# doubles RMS loudness and pitch mean on an RTX 5080 A/B test).
_CHATTERBOX_NONVERBAL = {"laugh": "laugh", "chuckle": "chuckle", "sigh": "sigh", "gasp": "gasp",
                         "groan": "groan", "sniff": "sniff", "cough": "cough",
                         "clear_throat": "clear throat", "shush": "shush"}


def for_chatterbox(text: str, annotation: dict | None) -> tuple[str, float, float]:
    """Returns (text_with_tags, exaggeration, cfg_weight). No annotation -> pass-through, neutral
    defaults (0.5, 0.5)."""
    if not annotation:
        return text, 0.5, 0.5
    tags = [f"[{_CHATTERBOX_NONVERBAL[nv]}]" for nv in annotation.get("nonverbal", [])
            if nv in _CHATTERBOX_NONVERBAL]
    prefix = " ".join(tags) + " " if tags else ""
    intensity = float(annotation.get("intensity", 0.3))
    exaggeration = min(1.0, 0.4 + 0.6 * intensity)
    cfg_weight = max(0.2, 0.5 - 0.3 * intensity)
    return prefix + text, exaggeration, cfg_weight


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


# Which treatment each engine gets. "instruct" reaches qwen3_tts too, but its Base checkpoint has
# no instruction-following at all (see tools/tts_engines/qwen3_tts.py) so the kwarg is a documented
# no-op there, not a bug. indextts2's emotion control is a separate reference-clip/vector mechanism,
# not text-based - not wired up yet, so it stays on the "pace" fallback like an engine with no entry.
ENGINE_KIND = {
    "chatterbox": "tags", "chatterbox_turbo": "tags", "chatterbox_turbo_eq": "tags",
    "qwen3_tts": "instruct", "higgs": "instruct", "fish_s2cpp": "instruct", "voxcpm2": "instruct",
}


def route(engine_name: str, text: str, annotation: dict | None) -> tuple[str, dict]:
    """(text, kwargs) to pass to that engine's synth(). Shared by server.py and run_bakeoff.py."""
    kind = ENGINE_KIND.get(engine_name, "pace")
    if kind == "tags":
        text, exaggeration, cfg_weight = for_chatterbox(text, annotation)
        return text, {"exaggeration": exaggeration, "cfg_weight": cfg_weight}
    if kind == "instruct":
        text, instruct = for_instruct_engine(text, annotation)
        return text, ({"instruct": instruct} if instruct else {})
    text, speed = for_pace_only_engine(text, annotation)
    return text, {"speed": speed}
