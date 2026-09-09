"""Fish Audio S2-Pro via reference/s2.cpp (a from-scratch GGML/CUDA port of the DualAR inference
pipeline - the bare PyTorch path in fish_s2.py OOMs on a 16GB card; Fish's own docs cite a 24GB
minimum, see PROJECT_PLAN.md/memory for how that was found, 2026-09-05). Comparison/reference
candidate only - Fish Audio Research License is non-commercial, and generation is still ~2-7x RTF
even with CUDA, so this isn't a public-mod-shippable engine either way (see
docs/superpowers/plans/2026-09-04-emotional-expressiveness-fix.md discussion and
[[private-team-build-scenario]] for where this might still be used).

Requires reference/s2.cpp built with CUDA (cmake -B build-cuda -DS2_CUDA=ON && cmake --build
build-cuda), and the F16 GGUF + tokenizer downloaded from rodrigomt/s2-pro-gguf into
reference/s2.cpp/models/. Shells out per line rather than keeping a server process - simple, and
matches the other adapters' load()/synth() interface; ~30-90s/line at time of writing.
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent.parent
S2CPP_DIR = ROOT / "reference/s2.cpp"
BINARY = S2CPP_DIR / "build-cuda/s2"
MODEL = S2CPP_DIR / "models/s2-pro-f16.gguf"
TOKENIZER = S2CPP_DIR / "models/tokenizer.json"


def load():
    for p in (BINARY, MODEL, TOKENIZER):
        if not p.is_file():
            raise FileNotFoundError(f"fish_s2cpp: required file missing: {p}")
    return None


def synth(ctx, text, prompt_wav=None, prompt_text=None, instruct=None):
    # See fish_s2.py: S2 supports free-form delivery tags embedded inline in the text.
    if instruct:
        text = f"[{instruct}] {text}"

    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "out.wav"
        cmd = [
            str(BINARY), "-m", str(MODEL), "-t", str(TOKENIZER), "-text", text,
            "-c", "0", "--codec-cpu",  # the F16 GGUF's codec buffer alloc reliably OOMs on CUDA
                                       # (see memory/smoke-test findings) - CPU codec works fine
                                       # and skips the failed-alloc-then-fallback log noise.
            "-o", str(out_path), "--log-level", "warn",
        ]
        if prompt_wav:
            cmd += ["-pa", str(prompt_wav), "-pt", prompt_text or ""]
        subprocess.run(cmd, cwd=S2CPP_DIR, check=True, capture_output=True, text=True)
        wav, sr = sf.read(str(out_path), dtype="float32")

    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    return np.asarray(wav, dtype=np.float32).reshape(-1), sr
