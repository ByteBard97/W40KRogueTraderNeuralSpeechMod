#!/usr/bin/env python3
"""Local TTS sidecar for the Rogue Trader neural speech mod.

The runtime C# mod POSTs {text, speaker, cue_guid, annotation} to /synth and gets back a WAV.
Everything GPU/Python-heavy lives here so the mod itself stays a thin Harmony-patch client.

Run:  uvicorn server:app --host 127.0.0.1 --port 8765  (from this directory, with the engine's venv)
Config: TTS_ENGINE env var selects the backend (default: chatterbox_turbo).

Design points (see PROJECT_PLAN.md):
  - GUID-keyed disk cache: identical (cue_guid, speaker, annotation, engine) never re-synthesizes.
    Cache key includes the annotation content hash, not just the guid, so an annotation-pipeline
    re-run naturally invalidates stale cached lines without a version bump.
  - Lexicon respelling applied before synthesis (data/lexicon).
  - Voiced lines are never sent here: the C# mod checks Sound.json / GetVoiceOverSound itself and
    only calls this server for lines the game has no recording for. This server does not
    duplicate that check.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).parent))

from lexicon import respell  # noqa: E402
from annotation_bridge import for_chatterbox, for_instruct_engine, for_pace_only_engine  # noqa: E402

ENGINE_NAME = os.environ.get("TTS_ENGINE", "chatterbox_turbo")
ENGINE_KIND = {"chatterbox_turbo": "tags", "qwen3_tts": "instruct"}.get(ENGINE_NAME, "pace")
CACHE_DIR = ROOT / "data/tts_cache" / ENGINE_NAME
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PROMPTS_PATH = ROOT / "data/voices/prompts/prompts.json"

app = FastAPI(title="RT Neural Speech sidecar")
_engine = None
_prompts: dict = {}


class Annotation(BaseModel):
    emotion: str | None = None
    intensity: float | None = None
    pace: str | None = None
    nonverbal: list[str] = []
    instruct: str | None = None


class SynthRequest(BaseModel):
    text: str
    speaker: str = "narrator"          # character_name, or "narrator" / "protagonist"
    cue_guid: str | None = None        # for cache logging only; cache key is content-derived
    annotation: Annotation | None = None
    prompt_rank: int = 1               # which prompt-bank clip to use (1 = best-scored)


@app.on_event("startup")
def load_engine() -> None:
    global _engine, _prompts
    import importlib
    mod = importlib.import_module(f"tts_engines.{ENGINE_NAME}")
    t0 = time.time()
    _engine = mod.synth, mod.load()
    print(f"[sidecar] loaded {ENGINE_NAME} in {time.time() - t0:.1f}s", file=sys.stderr)
    if PROMPTS_PATH.exists():
        _prompts = json.load(open(PROMPTS_PATH, encoding="utf-8"))
    print(f"[sidecar] {len(_prompts)} speaker prompt banks loaded", file=sys.stderr)


def _pcm_wav_bytes(x: np.ndarray, sr: int) -> bytes:
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return buf.getvalue()


def _cache_key(req: SynthRequest, resolved_text: str) -> str:
    ann = req.annotation.model_dump() if req.annotation else None
    payload = json.dumps({"text": resolved_text, "speaker": req.speaker, "annotation": ann,
                          "prompt_rank": req.prompt_rank, "engine": ENGINE_NAME}, sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()


def _prompt_for(speaker: str, rank: int) -> tuple[str | None, str | None]:
    bank = _prompts.get(speaker) or []
    usable = [p for p in bank if p.get("duration", 0) >= 5.5] or bank
    if not usable:
        return None, None
    p = usable[min(rank, len(usable)) - 1]
    return str(ROOT / "data/voices" / p["wav"]), p["text"]


@app.get("/health")
def health():
    return {"engine": ENGINE_NAME, "speakers": len(_prompts)}


@app.get("/voices")
def voices():
    return {"speakers": sorted(_prompts)}


@app.post("/synth")
def synth(req: SynthRequest):
    if _engine is None:
        raise HTTPException(503, "engine not loaded")
    synth_fn, ctx = _engine

    text = respell(req.text)
    ann = req.annotation.model_dump() if req.annotation else None
    key = _cache_key(req, text)
    cache_path = CACHE_DIR / f"{key}.wav"
    if cache_path.exists():
        return Response(cache_path.read_bytes(), media_type="audio/wav",
                        headers={"X-Cache": "hit", "X-Cache-Key": key})

    prompt_wav, prompt_text = _prompt_for(req.speaker, req.prompt_rank)
    kwargs = {}
    if ENGINE_KIND == "tags":
        text, exaggeration = for_chatterbox(text, ann)
        kwargs["exaggeration"] = exaggeration
    elif ENGINE_KIND == "instruct":
        text, instruct = for_instruct_engine(text, ann)
        if instruct:
            kwargs["instruct"] = instruct
    else:
        text, speed = for_pace_only_engine(text, ann)
        kwargs["speed"] = speed

    try:
        audio, sr = synth_fn(ctx, text, prompt_wav, prompt_text, **kwargs)
    except TypeError:
        audio, sr = synth_fn(ctx, text, prompt_wav, prompt_text)  # engine doesn't take the extra kwarg
    wav_bytes = _pcm_wav_bytes(np.asarray(audio, dtype=np.float32).reshape(-1), sr)
    cache_path.write_bytes(wav_bytes)
    return Response(wav_bytes, media_type="audio/wav", headers={"X-Cache": "miss", "X-Cache-Key": key})
