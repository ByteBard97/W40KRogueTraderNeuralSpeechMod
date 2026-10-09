#!/usr/bin/env python3
"""Live VoxCPM2 design backend for the audition page. Holds the model in memory so a new voice takes
a few seconds. Run in the VoxCPM2 env, only when the GPU is free:

  /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/voice_design/live_backend.py [--port 8909]

POST /generate {description, text, seed?, cfg?, timesteps?} -> {file, seed, cfg, timesteps, seconds}
  Clone mode (Pasqal page): {text, reference_wav, instruct?, retry_badcase?, normalize?, prompt_text?}. reference_wav
  must be under data/. Without prompt_text it is "controllable cloning" (reference only, what the render pipeline
  uses); with prompt_text the clip is also passed as the continuation prompt (the engine README warns it can echo
  the reference audio at the start of the output).
  writes data/voice_design/live_tmp/t<n>.wav; a blank seed picks a random one and reports it.
GET /health -> {"ok": bool, "busy": bool}   (busy while a generation holds the GPU lock)
The audit server (audit_server.py) proxies to this; nothing is kept until you press "Keep" there.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from design import OUT, ROOT, seed_all, vox_prompt

TMP = OUT / "live_tmp"
LOCK = threading.Lock()   # one generation at a time on the GPU
STATE = {"model": None, "n": 0}


def generate(body: dict) -> dict:
    import numpy as np
    import soundfile as sf
    seed = body.get("seed")
    seed = random.SystemRandom().randrange(2**31) if seed in (None, "") else int(seed)
    cfg, steps = float(body.get("cfg", 2.0)), int(body.get("timesteps", 10))
    kw: dict = {}
    if body.get("reference_b64"):   # remote studio: the clip travels with the request (this machine has no game audio)
        raw = base64.b64decode(body["reference_b64"])
        ref = TMP / "refs" / f"{hashlib.sha1(raw).hexdigest()[:16]}.wav"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_bytes(raw)
        body = {**body, "reference_wav": "(sent)"}
    elif body.get("reference_wav"):
        ref = (ROOT / body["reference_wav"]).resolve()
        if (ROOT / "data").resolve() not in ref.parents or not ref.is_file():
            raise ValueError(f"reference_wav must be an existing file under data/: {body['reference_wav']}")
    if body.get("reference_wav"):
        kw = {"reference_wav_path": str(ref), "retry_badcase": bool(body.get("retry_badcase", False)),
              "normalize": bool(body.get("normalize", False))}
        if body.get("prompt_text"):
            kw.update(prompt_wav_path=str(ref), prompt_text=body["prompt_text"])
        text = f"({body['instruct']}){body['text']}" if body.get("instruct") else body["text"]
    else:
        text = f"({vox_prompt(body['description'])}){body['text']}"
    with LOCK:
        t0 = time.time()
        seed_all(seed)
        model = STATE["model"]
        w = model.generate(text=text, cfg_value=cfg, inference_timesteps=steps, **kw)
        TMP.mkdir(parents=True, exist_ok=True)
        STATE["n"] += 1
        name = f"t{int(time.time())}_{STATE['n']}.wav"
        sf.write(str(TMP / name), np.asarray(w, dtype=np.float32).reshape(-1), model.tts_model.sample_rate)
    out = {"file": f"live_tmp/{name}", "seed": seed, "cfg": cfg, "timesteps": steps,
           "seconds": round(time.time() - t0, 1), "audio_s": round(len(w) / model.tts_model.sample_rate, 2)}
    if body.get("return_audio"):    # remote studio: send the wav back instead of relying on a shared disk
        out["audio_b64"] = base64.b64encode((TMP / name).read_bytes()).decode()
    return out


class H(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/health":
            self._send({"ok": STATE["model"] is not None, "busy": LOCK.locked()})
        else:
            self._send({}, 404)

    def do_POST(self):
        if self.path != "/generate":
            return self._send({}, 404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            self._send(generate(body))
        except Exception as e:  # report to the page instead of dropping the connection
            self._send({"error": f"{type(e).__name__}: {e}"}, 500)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8909)
    ap.add_argument("--host", default="127.0.0.1", help="bind address; use the machine's LAN IP to serve the studio remotely")
    args = ap.parse_args()
    from voxcpm import VoxCPM
    t0 = time.time()
    STATE["model"] = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    print(f"model loaded in {time.time() - t0:.0f}s; live design backend on http://{args.host}:{args.port}", flush=True)
    ThreadingHTTPServer((args.host, args.port), H).serve_forever()
