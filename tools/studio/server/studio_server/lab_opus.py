"""Hear what the bank's Opus compression does to a clip: encode it exactly as patch.py --codec opus does, decode it again, play that.

The encode is tools/bnk_patch/opus_wem.encode_ogg_opus (mono, 48 kHz, 20 ms frames, VBR), so the size shown is the size the clip would
have in the bank (plus a few dozen bytes of wem header). Results are cached under data/studio/lab/opus/.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from .config import Config
from .errors import ApiError

_BNK = str(Path(__file__).resolve().parents[4] / "tools/bnk_patch")
if _BNK not in sys.path:
    sys.path.insert(0, _BNK)

BITRATES = (12, 16, 24, 32, 48)
DECODE_TIMEOUT_S = 60
BANK_PCM_BYTES_PER_S = 24000 * 2


def preview(cfg: Config, wav_rel: str, kbps: int) -> dict:
    src = cfg.under_data(wav_rel)
    if src is None:
        raise ApiError(400, f"not a file under data/: {wav_rel!r}")
    if kbps not in BITRATES:
        raise ApiError(400, f"kbps must be one of {BITRATES}")
    from opus_wem import encode_ogg_opus
    from wem import FFMPEG
    key = hashlib.sha1(f"{src}|{src.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    out_dir = cfg.studio / "lab" / "opus"
    out_dir.mkdir(parents=True, exist_ok=True)
    ogg, dec = out_dir / f"{key}_{kbps}.opus", out_dir / f"{key}_{kbps}.wav"
    if not dec.is_file():
        data = encode_ogg_opus(str(src), f"{kbps}k")
        if not data:
            raise ApiError(500, "ffmpeg produced no Opus data (is libopus available?)")
        ogg.write_bytes(data)
        r = subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-y", "-i", str(ogg), "-ac", "1", "-c:a", "pcm_s16le", str(dec)],
                           capture_output=True, timeout=DECODE_TIMEOUT_S)
        if r.returncode != 0 or not dec.is_file():
            raise ApiError(500, "ffmpeg could not decode the Opus file")
    import wave
    with wave.open(str(dec)) as w:
        seconds = w.getnframes() / w.getframerate()
    pcm = int(seconds * BANK_PCM_BYTES_PER_S)               # what the same clip costs in the bank today (24 kHz, 16-bit, mono)
    return {"kbps": kbps, "wav": str(dec.relative_to(cfg.root)), "opus_bytes": ogg.stat().st_size, "source_bytes": pcm,
            "ratio": round(pcm / max(1, ogg.stat().st_size), 1)}
