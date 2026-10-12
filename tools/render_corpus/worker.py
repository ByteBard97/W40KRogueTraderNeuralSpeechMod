#!/usr/bin/env python3
"""Render worker: pulls jobs from queue_server.py over the network, renders them with the local GPU, uploads the audio.

  python tools/render_corpus/worker.py --server http://192.168.0.10:8920 --engine voxcpm2 --token TOKEN [--asr-model openai/whisper-small]

Needs the repo (tools/, src/TtsSidecar, data/lexicon) and the TTS engine installed on this machine; reference clips are
fetched from the server and cached in data/render/_refcache. Safe to stop and start; unfinished jobs go back to the queue.
--engine fake renders tones, for testing the plumbing without a GPU.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from render import load_engine, render_take  # noqa: E402

REF_CACHE = ROOT / "data/render/_refcache"


class Client:
    def __init__(self, server: str, token: str, worker: str):
        self.server, self.token, self.worker = server.rstrip("/"), token, worker

    def _req(self, path: str, data: bytes | None = None, headers: dict | None = None, retries: int = 5):
        for i in range(retries):
            try:
                req = urllib.request.Request(self.server + path, data=data, headers={"X-Token": self.token, **(headers or {})})
                return urllib.request.urlopen(req, timeout=120).read()
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if i == retries - 1:
                    raise
                time.sleep(min(5 * 2 ** i, 60))

    def lease(self, engine: str, n: int) -> list[dict]:
        body = json.dumps({"worker": self.worker, "engine": engine, "n": n}).encode()
        return json.loads(self._req("/lease", body))["jobs"]

    def ref(self, rel: str) -> Path:
        p = REF_CACHE / rel
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".part")
            tmp.write_bytes(self._req("/ref?path=" + urllib.request.quote(rel)))
            os.replace(tmp, p)
        return p

    def result(self, row: dict, wav_bytes: bytes) -> None:
        hdr = base64.urlsafe_b64encode(json.dumps(row, ensure_ascii=False).encode())
        self._req(f"/result?guid={row['guid']}&worker={self.worker}", wav_bytes, {"X-Row": hdr.decode()})


def fake_synth(text, ref, annotation):
    sr = 24000
    t = np.arange(int(sr * max(0.5, len(text) / 15))) / sr
    return (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), sr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--engine", required=True, choices=["voxcpm2", "qwen3_tts", "fake"])
    ap.add_argument("--token", default=os.environ.get("RT_QUEUE_TOKEN", ""))
    ap.add_argument("--name", default=socket.gethostname())
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--asr-model", help="transcribe each take with Whisper and send the comparison along")
    ap.add_argument("--asr-device", default="cuda:0")
    ap.add_argument("--exit-when-empty", action="store_true")
    a = ap.parse_args()
    c = Client(a.server, a.token, a.name)
    engine_name = "voxcpm2" if a.engine == "fake" else a.engine
    synth = fake_synth if a.engine == "fake" else load_engine(a.engine)
    asr = terms = None
    if a.asr_model:
        import asr_check
        import lexicon
        asr, terms = asr_check.make_asr(a.asr_model, a.asr_device), list(lexicon._load()[0])
    n, audio_s, t0 = 0, 0.0, time.time()
    while True:
        jobs = c.lease(engine_name, a.batch)
        if not jobs:
            if a.exit_when_empty:
                break
            time.sleep(30)
            continue
        for job in jobs:
            ref = c.ref(job["ref"]["wav"])
            row, wav, sr = render_take(synth, job, a.engine if a.engine != "fake" else "voxcpm2", str(ref))
            buf = b""
            if wav is not None:
                bio = io.BytesIO()
                sf.write(bio, wav, sr, format="WAV", subtype="PCM_16")
                buf = bio.getvalue()
                audio_s += len(wav) / sr
                if asr:
                    from asr_compare import compare
                    heard = asr({"raw": asr_check.resample_16k(wav, sr), "sampling_rate": 16000},
                                generate_kwargs={"language": "en", "task": "transcribe"})["text"].strip()
                    row["asr"] = {"heard": heard, **compare(job["text"], heard, terms)}
            c.result(row, buf)
            n += 1
        el = time.time() - t0
        print(f"{n} jobs  {audio_s:.0f}s audio in {el:.0f}s  ({audio_s/max(el,1):.2f}x realtime)", flush=True)
    print(f"queue empty; {n} jobs rendered", flush=True)


if __name__ == "__main__":
    main()
