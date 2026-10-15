"""Stereo support in the wem writers. Mono output must stay byte-identical to the pre-change writers."""
import hashlib, math, shutil, struct, subprocess, sys, wave
from pathlib import Path
import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import wem, opus_wem, channels  # noqa: E402

VGMSTREAM = HERE.parents[1] / "bin" / "vgmstream-cli"
pytestmark = pytest.mark.skipif(not Path(wem.FFMPEG).exists() or not VGMSTREAM.exists(),
                                reason="needs ffmpeg (wem.FFMPEG) and tools/bin/vgmstream-cli")

# sha256 of the output of the unmodified writers for mono_wav() below, taken before the channels argument existed
MONO_PCM_SHA = "c43a23548618ecdf70f3bde63f1aff5b195ba0ff6030350b88ad6dadcbc9b0d9"
MONO_OPUS_SHA = "6ecc229f7f8d16db428ac2a9b2b352c5939d3466065b580dc39d667fa2965c4c"
RATE_IN = 24000
SECONDS = 1.0


def _write(path, cols):
    data = np.stack(cols, axis=1).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(len(cols)); w.setsampwidth(2); w.setframerate(RATE_IN)
        w.writeframes(data.tobytes())
    return str(path)


def _tone(freq, n=int(RATE_IN * SECONDS)):
    return np.array([int(8000 * math.sin(2 * math.pi * freq * i / RATE_IN)) for i in range(n)])


@pytest.fixture(scope="module")
def mono_wav(tmp_path_factory):
    return _write(tmp_path_factory.mktemp("w") / "mono.wav", [_tone(440)])


@pytest.fixture(scope="module")
def stereo_wav(tmp_path_factory):
    return _write(tmp_path_factory.mktemp("w") / "stereo.wav", [_tone(440), _tone(660)])


@pytest.fixture(scope="module")
def same_wav(tmp_path_factory):
    return _write(tmp_path_factory.mktemp("w") / "same.wav", [_tone(440), _tone(440)])


def _fmt(blob):
    assert blob[12:16] == b"fmt "
    return blob[20:20 + struct.unpack_from("<I", blob, 16)[0]]


def _decode(blob, tmp_path):
    src, out = tmp_path / "t.wem", tmp_path / "t.wav"
    src.write_bytes(blob)
    r = subprocess.run([str(VGMSTREAM), "-o", str(out), str(src)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    with wave.open(str(out)) as w:
        n, rate = w.getnchannels(), w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, n)
    return x, rate


def _dominant(sig, rate):
    spec = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
    return np.fft.rfftfreq(len(sig), 1 / rate)[int(spec.argmax())]


def test_mono_pcm_unchanged(mono_wav):
    assert hashlib.sha256(wem.pcm_wem(mono_wav)).hexdigest() == MONO_PCM_SHA
    assert hashlib.sha256(wem.pcm_wem(mono_wav, channels=1)).hexdigest() == MONO_PCM_SHA


def test_mono_opus_unchanged(mono_wav):
    assert hashlib.sha256(opus_wem.opus_wem(mono_wav)).hexdigest() == MONO_OPUS_SHA


def test_pcm_stereo_header(stereo_wav):
    f = _fmt(wem.pcm_wem(stereo_wav, channels=2))
    tag, ch, rate, byte_rate, block, bits, cb, valid, mask = struct.unpack_from("<HHIIHHHHI", f)
    assert (tag, ch, rate, byte_rate, block, bits, mask) == (0xFFFE, 2, 24000, 24000 * 4, 4, 16, 0x3)
    assert f[24:] == wem.PCM_SUBFORMAT


def test_opus_stereo_header(stereo_wav):
    f = _fmt(opus_wem.opus_wem(stereo_wav, bitrate="48k", channels=2))
    tag, ch, rate = struct.unpack_from("<HHI", f)
    frame, mask, total, table, skip, version, mapping = struct.unpack_from("<HIiIHBB", f, 0x12)
    assert (tag, ch, rate, frame, mask, version, mapping) == (0x3041, 2, 48000, 960, 0x3, 1, 0)
    assert abs(total - 48000 * SECONDS) <= 960 and table > 0


def _check_roundtrip(blob, tmp_path, tol_samples):
    x, rate = _decode(blob, tmp_path)
    assert x.shape[1] == 2
    assert abs(len(x) - rate * SECONDS) <= tol_samples
    assert abs(_dominant(x[:, 0].astype(float), rate) - 440) < 5
    assert abs(_dominant(x[:, 1].astype(float), rate) - 660) < 5


def test_pcm_stereo_roundtrip(stereo_wav, tmp_path):
    _check_roundtrip(wem.pcm_wem(stereo_wav, channels=2), tmp_path, 1)


def test_opus_stereo_roundtrip(stereo_wav, tmp_path):
    _check_roundtrip(opus_wem.opus_wem(stereo_wav, bitrate="48k", channels=2), tmp_path, opus_wem.FRAME_SAMPLES)


def test_pcm_stereo_same_gain_both_sides(stereo_wav, tmp_path):
    x, _ = _decode(wem.pcm_wem(stereo_wav, channels=2), tmp_path)
    src = np.stack([_tone(440), _tone(660)], axis=1).astype(float)
    ratio = np.abs(x).max(axis=0) / np.abs(src).max(axis=0)
    assert abs(ratio[0] - ratio[1]) < 0.01 * ratio[0]


def test_wav_channel_count(mono_wav, stereo_wav):
    assert channels.wav_channel_count(mono_wav) == 1
    assert channels.wav_channel_count(stereo_wav) == 2


def test_sides_differ(mono_wav, stereo_wav, same_wav):
    assert channels.sides_differ(stereo_wav) is True
    assert channels.sides_differ(same_wav) is False
    assert channels.sides_differ(mono_wav) is False


def test_game_stereo_wem_is_vorbis_not_comparable():
    """The game's own stereo wems (Pasqal, Ulfar, Trazyn) are Wwise Vorbis (tag 0xFFFF), not PCM or Opus, so their
    codec-specific fields cannot be compared; only the common head (channels, rate) is. Skipped when not unpacked."""
    work = HERE.parents[2] / "data" / "voices" / "_work"
    found = None
    for p in sorted(work.glob("*/sfx/*.wem"))[:2000]:
        h = p.read_bytes()[:40]
        if h[8:12] == b"WAVE" and struct.unpack_from("<H", h, 22)[0] == 2:
            found = h
            break
    if found is None:
        pytest.skip("no unpacked stereo game wem under data/voices/_work")
    tag, ch, rate = struct.unpack_from("<HHI", found, 20)
    assert (tag, ch, rate) == (0xFFFF, 2, 48000)
