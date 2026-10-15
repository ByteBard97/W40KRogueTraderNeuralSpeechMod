#!/usr/bin/env python3
"""Render a slice of data/render/jobs.jsonl with one engine. Resumable; run one per machine/engine.

  voxcpm2:   /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/render_corpus/render.py --engine voxcpm2 --buckets 0-69 --name linux
  qwen3_tts: tools/tts_bakeoff/.venv-qwen/bin/python        tools/render_corpus/render.py --engine qwen3_tts --buckets 0-99 --name linux

Output (under data/render/<name>/): wav/<guid>.wav and manifest.jsonl (one row per finished or failed job).
A worker skips every guid already in its manifest as ok, so it can be stopped and restarted freely.
A take that fails take_problem() is retried once; if it still fails it is kept and flagged.
Buckets are md5(guid) % 100, so two machines given disjoint bucket ranges never overlap.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))

from annotation_bridge import route  # noqa: E402
from jobs import parse_buckets, select_jobs, take_problem  # noqa: E402
from lexicon import respell  # noqa: E402
from phonemes import phonemize  # noqa: E402

CFG = 3.0           # VoxCPM2: higher was better across the sweep range (HANDOFF-2026-09-23)
TIMESTEPS = 15


def pronounce(text: str, engine: str) -> str:
    """Lexicon pronunciations in the form the engine reads correctly: braced phonemes for VoxCPM2, respellings otherwise."""
    return phonemize(text) if engine == "voxcpm2" else respell(text)


def load_engine(name: str):
    if name == "voxcpm2":
        from voxcpm import VoxCPM
        model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)

        def synth(text, ref, annotation):
            text, kw = route("voxcpm2", text, annotation)
            if kw.get("instruct"):
                text = f"({kw['instruct']}){text}"
            wav = model.generate(text=text, reference_wav_path=ref["wav"], cfg_value=CFG,
                                 inference_timesteps=TIMESTEPS, retry_badcase=False)
            return np.asarray(wav, dtype=np.float32).reshape(-1), model.tts_model.sample_rate

        def raw(text, ref_wav, instruct=None, cfg=CFG, timesteps=TIMESTEPS, normalize=False, seed=None):
            """One generation with every knob explicit (recipe jobs, see recipe_render.py). Text is sent as given: no lexicon pass here."""
            import random
            import torch
            if seed is not None:
                random.seed(seed)
                np.random.seed(seed % (2 ** 32))
                torch.manual_seed(seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(seed)
            if normalize:                                   # the model's own normalizer, but never inside a {PHONEME} guide
                import re
                if model.text_normalizer is None:
                    from voxcpm.utils.text_normalize import TextNormalizer
                    model.text_normalizer = TextNormalizer()
                text = "".join(p if i % 2 else (model.text_normalizer.normalize(p) if p.strip() else p)
                               for i, p in enumerate(re.split(r"(\{[^{}]*\})", text)))
            if instruct:
                text = f"({instruct}){text}"
            wav = model.generate(text=text, reference_wav_path=ref_wav, cfg_value=cfg, inference_timesteps=timesteps,
                                 retry_badcase=False, normalize=False)
            return np.asarray(wav, dtype=np.float32).reshape(-1), model.tts_model.sample_rate
        synth.raw = raw
        return synth
    if name == "qwen3_tts":
        import tts_engines.qwen3_tts as q
        ctx = q.load()

        def synth(text, ref, annotation):
            return q.synth(ctx, text, ref["wav"], ref["text"])
        return synth
    raise SystemExit(f"unknown engine {name}")


def render_take(synth, job: dict, engine: str, ref_wav: str):
    """One job -> (manifest row, wav, sample rate); wav is None when the engine raised. A take that fails
    take_problem() is retried once and then kept with the problem in its flags."""
    ref = {"wav": ref_wav, "text": job["ref"]["text"]}
    row = {"guid": job["guid"], "speaker": job["speaker"], "engine": engine, "text": job["text"],
           "src_text": job["src_text"], "voice_source": job["voice_source"]}
    wav = sr = problem = None
    try:
        for _attempt in range(2):
            # a job can set "respell": false to send its text to the engine exactly as written
            wav, sr = synth(job["text"] if job.get("respell") is False else pronounce(job["text"], engine), ref, job["annotation"])
            problem = take_problem(job["text"], len(wav) / sr)
            if problem is None:
                break
    except Exception as e:  # keep the queue moving; failures are retried next run
        traceback.print_exc()
        row.update(status="failed", error=str(e)[:200])
        return row, None, None
    row.update(status="ok", seconds=round(len(wav) / sr, 2), flags=[problem] if problem else [])
    return row, wav, sr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, choices=["voxcpm2", "qwen3_tts"])
    ap.add_argument("--buckets", default="0-99")
    ap.add_argument("--name", required=True, help="output dir name under data/render, e.g. linux or mac")
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-priority", type=int, default=9, help="0 emotion bank .. 3 fallback voice")
    args = ap.parse_args()

    out = ROOT / "data/render" / args.name
    (out / "wav").mkdir(parents=True, exist_ok=True)
    mpath = out / "manifest.jsonl"
    done = set()
    if mpath.exists():
        for ln in mpath.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            if r["status"] == "ok":
                done.add(r["guid"])

    jobs = [json.loads(ln) for ln in Path(args.jobs).read_text(encoding="utf-8").splitlines()]
    jobs = [j for j in jobs if j["priority"] <= args.max_priority]
    todo = select_jobs(jobs, args.engine, parse_buckets(args.buckets), done)
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} jobs to render ({len(done)} already done)", flush=True)
    if not todo:
        return

    synth = load_engine(args.engine)
    t0, n, audio_s = time.time(), 0, 0.0
    for job in todo:
        row, wav, sr = render_take(synth, job, args.engine, str(ROOT / job["ref"]["wav"]))
        if wav is not None:
            sf.write(str(out / "wav" / f"{job['guid']}.wav"), wav, sr)
            audio_s += len(wav) / sr
        with open(mpath, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        n += 1
        if n % 20 == 0:
            el = time.time() - t0
            print(f"{n}/{len(todo)}  {el:.0f}s  {audio_s:.0f}s audio  RTF {el/max(audio_s,1):.2f}", flush=True)
    print(f"done {n} jobs in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
