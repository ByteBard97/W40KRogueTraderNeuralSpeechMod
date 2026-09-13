#!/usr/bin/env python3
"""Emotion reference-clip review: one server, two pages.

/            - coverage dashboard: every (character, emotion) combo the unvoiced corpus needs,
               ranked by how many lines depend on it, with done/needs-review/unrepresented status
/curate      - per-speaker clip listen-and-decide page (linked from the dashboard)

Both pages work off the same data, loaded once: the voiced-clip catalog, the LLM's text-based
emotion annotations, emotion2vec+'s audio-based predictions (tools/score_catalog_emotions.py),
and any human accept/reject decisions already recorded. See the two former standalone tools this
replaces (git history) for the per-page design notes - merged here because they were duplicating
the same data loading across two processes/ports for no reason.

Usage: python3 serve.py [--port 8900] [--target-duration 8.0]
Decisions -> data/voices/emotion_banks/curation.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build_prompt_banks import load_wav, score_clip  # noqa: E402

VOICES = ROOT / "data/voices"
STATIC_DIR = Path(__file__).resolve().parent

CONVERSATIONS = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
CATALOG = json.loads((VOICES / "catalog.json").read_text(encoding="utf-8"))
ANNOTATIONS = json.loads((ROOT / "data/annotations/annotations.enGB.json").read_text(encoding="utf-8"))
SER_PATH = VOICES / "emotion_banks/ser_scores.json"
SER_SCORES = json.loads(SER_PATH.read_text(encoding="utf-8")) if SER_PATH.exists() else {}
AUDIO_LLM_PATH = VOICES / "emotion_banks/audio_llm_labels.json"
AUDIO_LLM_LABELS = json.loads(AUDIO_LLM_PATH.read_text(encoding="utf-8")) if AUDIO_LLM_PATH.exists() else {}
CURATION_PATH = VOICES / "emotion_banks/curation.json"
CUSTOM_EMOTIONS_PATH = VOICES / "emotion_banks/custom_emotions.json"

CATALOG_SPEAKERS = {c["speaker"] for c in CATALOG.values() if c.get("speaker")}
EMOTION_ORDER = ["angry", "commanding", "fear", "surprised", "pleading", "sad", "whisper",
                 "sarcastic", "dramatic", "happy", "amused", "neutral"]
# Only emotions emotion2vec+ can actually recognize get an automatic agreement check; the rest
# have no SER equivalent, so agreement is always "n/a" for them - a human ear is the only signal.
EMOTION_TO_SER = {"angry": "angry", "sad": "sad", "fear": "fearful", "happy": "happy",
                  "surprised": "surprised", "neutral": "neutral"}


def load_custom_emotions() -> list[dict]:
    """[{"tier": name, "words": [...]}, ...] - read fresh every call (not cached at import time)
    so words added via /add_emotion show up immediately, no server restart needed."""
    if not CUSTOM_EMOTIONS_PATH.exists():
        return []
    return json.loads(CUSTOM_EMOTIONS_PATH.read_text(encoding="utf-8")).get("tiers", [])


def save_custom_emotions(tiers: list[dict]) -> None:
    CUSTOM_EMOTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CUSTOM_EMOTIONS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"tiers": tiers}, indent=1), encoding="utf-8")
    os.replace(tmp, CUSTOM_EMOTIONS_PATH)


def emotion_tiers() -> list[dict]:
    """The full set of assignable emotion labels, grouped for dropdown display: the original
    12-category enum first (still what most annotations use today), then the energy-tiered
    vocabulary and any further ad hoc additions."""
    return [{"tier": "Original", "words": EMOTION_ORDER}] + load_custom_emotions()


def all_emotion_words() -> set[str]:
    words: set[str] = set()
    for group in emotion_tiers():
        if group["tier"] == "Register modifiers":
            continue  # a separate axis (see register_words) - not a valid emotion value itself
        words.update(group["words"])
    return words


def register_words() -> set[str]:
    """Register modifiers (delivery quality: quiet, breathless, ...) are a separate axis from
    emotion, not an alternative emotion - a clip can be both "angry" and "hushed" at once."""
    for group in emotion_tiers():
        if group["tier"] == "Register modifiers":
            return set(group["words"])
    return set()

_lock = threading.Lock()


def load_curation() -> dict:
    if not CURATION_PATH.exists():
        return {}
    data = json.loads(CURATION_PATH.read_text(encoding="utf-8"))
    # Older records were a bare "accept"/"reject" string, predating the relabel feature - normalize
    # to the current {"decision", "emotion"} shape so callers never have to special-case both.
    for bucket in data.values():
        for event, record in bucket.items():
            if isinstance(record, str):
                bucket[event] = {"decision": record, "emotion": None}
    return data


def audio_llm_prediction(event: str, mode: str) -> dict | None:
    """The stored tools/audio_emotion_labeling prediction for this event/mode, regardless of
    prompt_hash - only one prompt version has ever been run, so there's at most one entry."""
    by_mode = AUDIO_LLM_LABELS.get(event, {}).get("ultravox", {}).get(mode, {})
    return next(iter(by_mode.values()), None)


def audio_llm_emotion(event: str) -> str | None:
    """Best available audio-informed emotion for a voiced clip: prefers the audio+text pass
    (highest measured accuracy in the pilot - see docs/superpowers/specs/...), falls back to
    audio-only, else None (caller falls back further to the text-only annotation)."""
    for mode in ("audio+text", "audio"):
        pred = audio_llm_prediction(event, mode)
        if pred and pred.get("labels"):
            return pred["labels"][0]["word"]
    return None


def effective_emotion(event: str, record: dict | None, original: str) -> str:
    """A human relabel (this clip actually sounds like a different emotion than the automated
    guess) always wins - it never touches data/annotations/annotations.enGB.json, since these
    lines have real recorded audio and are never TTS-synthesized at runtime. Absent a human
    decision, prefer the audio-informed prediction (a model that actually listened to this take)
    over the text-only annotation `original` (written blind to the real performance, before this
    project's audio-based labeling existed)."""
    human = (record or {}).get("emotion")
    if human:
        return human
    return audio_llm_emotion(event) or original


def save_curation(data: dict) -> None:
    CURATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CURATION_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, CURATION_PATH)


# --- dashboard data -----------------------------------------------------------------------

def demand_counts() -> dict[tuple[str, str], int]:
    """{(speaker, emotion): count of unvoiced lines needing it}."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for conv in CONVERSATIONS:
        for line in conv.get("lines", []):
            if line.get("voiced"):
                continue  # has real recorded audio, never synthesized
            sp = line.get("speaker") or {}
            name = sp.get("name")
            if not name or name not in CATALOG_SPEAKERS:
                continue  # template/dynamic NPC (no fixed character) or no voiced material at all
            ann = ANNOTATIONS.get(line.get("text_key"))
            if not ann:
                continue
            counts[(name, ann.get("emotion", "neutral"))] += 1
    return counts


def clip_agreement(event: str, emotion: str, ser: dict | None) -> str:
    """Automated cross-check for combo_status's auto-pass gate. Prefers emotion2vec+ SER where
    it applies (the original 6-word mapping); for every other emotion word (the whole expanded
    per-speaker vocabulary this project now uses - see tools/audio_emotion_labeling/
    speaker_vocab.py) SER has no equivalent label at all, so fall back to the same Ultravox
    audio-vs-audio+text top-1 agreement curate.html already shows per clip as "AI heard: X / Y
    (dis)agree" - reusing that signal here instead of letting it default to "n/a" auto-pass,
    which is how ~70% of "done" combos were previously getting there with zero real check."""
    expected_ser_label = EMOTION_TO_SER.get(emotion)
    if ser and expected_ser_label:
        return "agree" if ser["label"] == expected_ser_label else "disagree"
    audio = audio_llm_prediction(event, "audio")
    audio_top1 = audio["labels"][0]["word"] if audio and audio.get("parse_ok") and audio.get("labels") else None
    if audio_top1 is None:
        return "n/a"
    return "agree" if audio_top1 == emotion else "disagree"


def supply_candidates() -> dict[tuple[str, str], list[dict]]:
    """{(speaker, emotion): [candidate, ...]} from the voiced catalog, LLM+SER cross-checked."""
    curation = load_curation()
    by_combo: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for event, c in CATALOG.items():
        speaker = c.get("speaker")
        if not speaker or not c.get("texts"):
            continue
        guid = c["texts"][0].get("guid")
        ann = ANNOTATIONS.get(guid)
        # A text annotation used to be the only way to classify a voiced clip at all; an
        # audio-informed prediction is just as good a signal now, so only skip a clip with
        # neither (no way to tell what emotion it might even be).
        if not ann and not audio_llm_emotion(event):
            continue
        record = curation.get(speaker, {}).get(event)
        emotion = effective_emotion(event, record, (ann or {}).get("emotion", "neutral"))
        ser = SER_SCORES.get(event)
        agreement = clip_agreement(event, emotion, ser)
        decision = (record or {}).get("decision")
        by_combo[(speaker, emotion)].append({
            "event": event, "duration": c.get("duration", 0), "agreement": agreement,
            "ser_label": ser["label"] if ser else None, "decision": decision,
        })
    return by_combo


def combo_status(candidates: list[dict], target_duration: float) -> dict:
    # "accept" always counts; an explicit "reject" never counts; absent a human decision, only
    # SER-agreeing (or SER-not-applicable) clips count automatically - a SER disagreement needs a
    # human look before it counts toward "done".
    usable = [c for c in candidates if c["decision"] == "accept"
              or (c["decision"] is None and c["agreement"] != "disagree")]
    total = sum(c["duration"] for c in usable)
    if not candidates:
        status = "unrepresented"
    elif total >= target_duration:
        status = "done"
    else:
        status = "needs_review"
    return {"status": status, "usable_duration": round(total, 1), "n_candidates": len(candidates),
            "n_disagree": sum(1 for c in candidates if c["agreement"] == "disagree" and c["decision"] is None)}


# --- clip curation data --------------------------------------------------------------------

def _candidates_for(speaker: str, decisions: dict) -> dict[str, list[dict]]:
    """{emotion: [candidate, ...]} for one speaker, scored and sorted best-first. Grouped by the
    human-relabeled emotion where one exists, else the audio-informed prediction, else the LLM's
    original text-based prediction."""
    by_emotion: dict[str, list[dict]] = {}
    for event, c in CATALOG.items():
        if c.get("speaker") != speaker or not c.get("texts"):
            continue
        guid = c["texts"][0].get("guid")
        ann = ANNOTATIONS.get(guid)
        # A text annotation used to be the only way to classify a voiced clip at all; an
        # audio-informed prediction is just as good a signal now, so only skip a clip with
        # neither (no way to tell what emotion it might even be).
        if not ann and not audio_llm_emotion(event):
            continue
        try:
            x, sr = load_wav(VOICES / c["wav"])
        except Exception:
            continue
        sc = score_clip(x, sr, c["texts"][0]["text"])
        if not sc.get("ok"):
            continue
        ser = SER_SCORES.get(event)
        original_emotion = (ann or {}).get("emotion", "neutral")  # text-only annotation, blind to audio
        record = decisions.get(event)
        emotion = effective_emotion(event, record, original_emotion)
        by_emotion.setdefault(emotion, []).append({
            "event": event, "text": c["texts"][0]["text"], "guid": guid,
            "intensity": (ann or {}).get("intensity"), "ser_label": ser["label"] if ser else None,
            "ser_confidence": ser["confidence"] if ser else None,
            "original_emotion": original_emotion, "audio_emotion": audio_llm_emotion(event),
            "audio_llm": {"audio": audio_llm_prediction(event, "audio"),
                          "audio+text": audio_llm_prediction(event, "audio+text")},
            # "relabeled" means a human explicitly overrode the automated pick - it is NOT set
            # just because the audio-informed guess disagrees with the text-only annotation,
            # which is expected and not something a human did.
            "relabeled": bool((record or {}).get("emotion")),
            "register": (record or {}).get("register"), **sc,
        })
    for clips in by_emotion.values():
        clips.sort(key=lambda c: -c["score"])
    return by_emotion


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, name, content_type):
        data = (STATIC_DIR / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")  # this file changes across dev iterations -
                                                          # a browser-cached stale copy must never win
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)
        if path == "/":
            return self._serve_static("dashboard.html", "text/html")
        if path == "/curate":
            return self._serve_static("curate.html", "text/html")
        if path == "/combos":
            return self._combos()
        if path == "/speakers":
            return self._send_json({"speakers": sorted(_speakers_with_data())})
        if path == "/items":
            return self._items(query.get("speaker", [None])[0])
        if path.startswith("/audio/"):
            return self._audio(path)
        self.send_error(404)

    def _combos(self):
        demand = demand_counts()
        supply = supply_candidates()
        rows = []
        for combo, n_needed in demand.items():
            speaker, emotion = combo
            candidates = supply.get(combo, [])
            status = combo_status(candidates, TARGET_DURATION)
            rows.append({"speaker": speaker, "emotion": emotion, "lines_needing_this": n_needed, **status})
        rows.sort(key=lambda r: -r["lines_needing_this"])
        summary = {"done": 0, "needs_review": 0, "unrepresented": 0}
        for r in rows:
            summary[r["status"]] += 1
        self._send_json({"rows": rows, "summary": summary, "target_duration": TARGET_DURATION})

    def _items(self, speaker):
        if not speaker or speaker not in CATALOG_SPEAKERS:
            return self.send_error(404)
        with _lock:
            decisions = load_curation().get(speaker, {})
        by_emotion = _candidates_for(speaker, decisions)
        tiers = emotion_tiers()
        # Stable display order: every known label in tier order, then (safety net) any emotion a
        # clip actually got relabeled to that isn't in the known list for some reason - a clip
        # must never silently vanish just because its label isn't in the canonical ordering.
        order = [w for group in tiers for w in group["words"]]
        order += [e for e in by_emotion if e not in order]
        groups = []
        for emotion in order:
            clips = by_emotion.get(emotion)
            if not clips:
                continue
            groups.append({
                "emotion": emotion,
                "clips": [{**c, "url": f"/audio/{speaker}/{c['event']}",
                           "decision": decisions.get(c["event"], {}).get("decision")} for c in clips],
            })
        self._send_json({"speaker": speaker, "groups": groups, "emotion_tiers": tiers})

    def _audio(self, path):
        parts = path.split("/", 3)  # '', 'audio', speaker, event
        if len(parts) != 4:
            return self.send_error(404)
        speaker, event = unquote(parts[2]), unquote(parts[3])
        c = CATALOG.get(event)
        if not c or c.get("speaker") != speaker:
            return self.send_error(404)
        fp = (VOICES / c["wav"]).resolve()
        if VOICES.resolve() not in fp.parents or not fp.is_file():
            return self.send_error(404)
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        # Requiring an application/json content type means a plain cross-origin HTML <form> post
        # (no fetch, no CORS preflight) can't hit these endpoints - defeats the simplest CSRF
        # against this localhost server from a page open in another tab.
        if "application/json" not in self.headers.get("Content-Type", ""):
            return self.send_error(415)
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self.send_error(400)
        if path == "/decide":
            return self._decide(body)
        if path == "/add_emotion":
            return self._add_emotion(body)
        self.send_error(404)

    def _decide(self, body):
        speaker, event = body.get("speaker"), body.get("event")
        decision, emotion = body.get("decision"), body.get("emotion")
        register = body.get("register")
        if not speaker or not event or decision not in ("accept", "reject", None):
            return self.send_error(400)
        if emotion is not None and emotion not in all_emotion_words():
            return self.send_error(400)
        if register is not None and register not in register_words():
            return self.send_error(400)
        with _lock:
            data = load_curation()
            bucket = data.setdefault(speaker, {})
            if decision is None and emotion is None and register is None:
                bucket.pop(event, None)
            else:
                bucket[event] = {"decision": decision, "emotion": emotion, "register": register}
            save_curation(data)
        self._send_json({"ok": True})

    def _add_emotion(self, body):
        word = (body.get("word") or "").strip().lower()
        tier = body.get("tier") or "Custom"
        # Both get echoed back unescaped into curate.html's <option>/badge markup - restrict to
        # plain words so a pasted label can't inject HTML/JS (stored XSS via the custom-label path).
        label = re.compile(r"[a-z][a-z0-9 _-]{0,40}").fullmatch
        if not word or not label(word) or not label(tier.lower()):
            return self.send_error(400)
        with _lock:
            tiers = load_custom_emotions()
            if word in EMOTION_ORDER or any(word in g["words"] for g in tiers):
                return self._send_json({"ok": True, "tiers": [{"tier": "Original", "words": EMOTION_ORDER}] + tiers})
            existing = next((g for g in tiers if g["tier"] == tier), None)
            if existing:
                existing["words"].append(word)
            else:
                tiers.append({"tier": tier, "words": [word]})
            save_custom_emotions(tiers)
        self._send_json({"ok": True, "tiers": [{"tier": "Original", "words": EMOTION_ORDER}] + tiers})


def _speakers_with_data() -> set[str]:
    have_data = set()
    for event, c in CATALOG.items():
        if not c.get("texts") or not c.get("speaker"):
            continue
        if ANNOTATIONS.get(c["texts"][0].get("guid")) or audio_llm_emotion(event):
            have_data.add(c["speaker"])
    return have_data


TARGET_DURATION = 8.0


def main() -> None:
    global TARGET_DURATION
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8900)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--target-duration", type=float, default=8.0,
                     help="seconds of accepted/agreed clip audio needed to mark a combo 'done'")
    args = ap.parse_args()
    TARGET_DURATION = args.target_duration

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Emotion review (dashboard + curation) at http://{args.host}:{args.port} (Ctrl+C to stop)")
    print(f"Decisions -> {CURATION_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
