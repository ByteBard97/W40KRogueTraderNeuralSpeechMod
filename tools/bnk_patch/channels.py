"""Channel facts about a WAV, used to decide whether a clip is written as a mono or a stereo wem."""
import struct, subprocess
import numpy as np
from wem import FFMPEG

SIDES_TOL = 1e-4     # of peak; below this a stereo file counts as mono


def wav_channel_count(path):
    """1 or 2: the channel count from the RIFF fmt chunk (anything above two is reported as 2, the encoders downmix it)."""
    with open(path, "rb") as f:
        head = f.read(12)
        if head[:4] not in (b"RIFF", b"RF64") or head[8:12] != b"WAVE":
            raise ValueError("not a WAV file: %s" % path)
        while True:
            ck = f.read(8)
            if len(ck) < 8:
                raise ValueError("no fmt chunk: %s" % path)
            cid, size = ck[:4], struct.unpack("<I", ck[4:])[0]
            if cid == b"fmt ":
                return 1 if struct.unpack("<H", f.read(4)[2:4])[0] <= 1 else 2
            f.seek(size + (size & 1), 1)


def sides_differ(path, tol=SIDES_TOL):
    """True when the file is stereo and left and right differ by more than tol relative to the peak."""
    if wav_channel_count(path) == 1:
        return False
    raw = subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-i", path, "-ac", "2", "-f", "f32le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw[:len(raw) // 8 * 8], dtype="<f4").reshape(-1, 2)
    peak = float(np.abs(x).max()) if x.size else 0.0
    return peak > 0 and float(np.abs(x[:, 0] - x[:, 1]).max()) > tol * peak
