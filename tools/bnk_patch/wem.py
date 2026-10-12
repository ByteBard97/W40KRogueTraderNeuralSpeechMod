"""Turn a WAV into a Wwise PCM .wem: 24 kHz mono 16-bit, loudness matched to the old pack."""
import re, struct, subprocess

FFMPEG = "/home/geoff/anaconda3/bin/ffmpeg"
RATE = 24000
# Wwise's PCM codec only plays WAVE_FORMAT_EXTENSIBLE wems (a plain tag-1 fmt chunk is silent, tested in game 2026-10-11).
PCM_SUBFORMAT = bytes.fromhex("0100000000001000800000aa00389b71")
MASK_FRONT_CENTER = 0x4
TARGET_LUFS = -20.0
TP_CEILING = -1.5          # dBTP; the real game VO peaks near -6 (p95 -4.4), the old pack touched 0
LOUDNESS_VERSION = 3       # bump when the normalisation changes so cached wems are rebuilt


def _ff(args, **kw):
    return subprocess.run([FFMPEG, "-nostdin", "-hide_banner", *args], capture_output=True, **kw)


def measure_lufs(path):
    err = _ff(["-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"]).stderr.decode()
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    return float(m[-1]) if m else None


def measure_levels(path):
    """(integrated LUFS, true peak dBTP) of a file, or (None, None) when ffmpeg finds nothing to measure."""
    # measure what the wem will contain: 24 kHz mono (the resample shifts inter-sample peaks by up to about 0.7 dB)
    chain = "aresample=%d,aformat=channel_layouts=mono,ebur128=peak=true" % RATE
    err = _ff(["-nostats", "-i", path, "-af", chain, "-f", "null", "-"]).stderr.decode()
    tail = err[err.rfind("Summary:"):]
    i, p = re.search(r"I:\s+(-?[\d.]+) LUFS", tail), re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    return (float(i.group(1)), float(p.group(1))) if i and p else (None, None)


def linear_gain_db(lufs, true_peak, target, trim=0.0, ceiling=TP_CEILING):
    """Gain that moves the clip to the target loudness (plus trim) but never past the true-peak ceiling.
    Purely linear: no limiter, no compression, so the clip's dynamics are untouched."""
    if lufs is None:
        return 0.0
    if target is None:   # level already set (stitched mixed cues): only guard the peak, never boost
        return min(0.0, ceiling - true_peak) if true_peak is not None else 0.0
    gain = max(-12.0, min(12.0, target + trim - lufs))
    return min(gain, ceiling - true_peak) if true_peak is not None else gain


def pcm_wem(path, target=TARGET_LUFS, trim=0.0):
    lufs, true_peak = measure_levels(path)
    gain = linear_gain_db(lufs, true_peak, target, trim)
    af = "volume=%.2fdB" % gain
    pcm = _ff(["-i", path, "-af", af, "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"]).stdout
    fmt = struct.pack("<HHIIHHHHI", 0xFFFE, 1, RATE, RATE * 2, 2, 16, 22, 16, MASK_FRONT_CENTER) + PCM_SUBFORMAT
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body
