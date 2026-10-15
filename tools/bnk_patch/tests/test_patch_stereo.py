"""patch.py: stereo-aware convert jobs and cache names; mono output must stay byte-identical to the pre-change code."""
import hashlib, math, subprocess, sys, wave
from pathlib import Path
import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import patch, wem  # noqa: E402
import tone_test_stereo as tts  # noqa: E402

VGMSTREAM = HERE.parents[1] / "bin" / "vgmstream-cli"
needs_tools = pytest.mark.skipif(not Path(wem.FFMPEG).exists() or not VGMSTREAM.exists(),
                                 reason="needs ffmpeg (wem.FFMPEG) and tools/bin/vgmstream-cli")

# sha256 of the old convert() output for mono_wav() (1 s of 440 Hz at 24 kHz), taken before patch.py was changed
OLD_SHA = {("pcm", -20.0): "c43a23548618ecdf70f3bde63f1aff5b195ba0ff6030350b88ad6dadcbc9b0d9",
           ("pcm", None): "753110b94d15ada57ed5e2990506188a506fb053fc390a20ae52ab805648d400",
           ("opus24k", -20.0): "21dd7f77bd27de00374750129c0e1bc1083d4715f451f3a8360a66c555e8990e",
           ("opus24k", None): "6ecc229f7f8d16db428ac2a9b2b352c5939d3466065b580dc39d667fa2965c4c"}
RATE = 24000


def _tone(freq, amp=8000):
    return np.array([int(amp * math.sin(2 * math.pi * freq * i / RATE)) for i in range(RATE)])


def _write(path, cols):
    data = np.stack(cols, axis=1).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(len(cols)); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(data.tobytes())
    return str(path)


@pytest.fixture(scope="module")
def wavs(tmp_path_factory):
    d = tmp_path_factory.mktemp("w")
    return {"mono": _write(d / "mono.wav", [_tone(440)]), "stereo": _write(d / "stereo.wav", [_tone(440), _tone(660)]),
            "same": _write(d / "same.wav", [_tone(440), _tone(440)])}


def _job(src, tmp_path, codec, target=-20.0, trim=0.0):
    ch = patch.clip_channels(src)
    dst = str(tmp_path / patch.cache_name(5, src, target, trim, codec, ch))
    return (src, dst, target, trim, codec, ch), ch


def _decode(path, tmp_path):
    out = tmp_path / "d.wav"
    r = subprocess.run([str(VGMSTREAM), "-o", str(out), str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    with wave.open(str(out)) as w:
        n, rate = w.getnchannels(), w.getframerate()
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, n), rate


def _dominant(sig, rate):
    spec = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
    return np.fft.rfftfreq(len(sig), 1 / rate)[int(spec.argmax())]


def test_stereo_bitrate():
    assert patch.stereo_bitrate("24k") == "48k"
    assert patch.stereo_bitrate("32000") == "64000"


@needs_tools
@pytest.mark.parametrize("codec,target", list(OLD_SHA))
def test_mono_name_and_bytes_unchanged(wavs, tmp_path, codec, target):
    job, ch = _job(wavs["mono"], tmp_path, codec, target)
    st = Path(wavs["mono"]).stat()
    old_name = "5_%d_%d_L%d_%s_+0.0_%s.wem" % (st.st_mtime, st.st_size, wem.LOUDNESS_VERSION,
                                               "preset" if target is None else "%+.1f" % target, codec)
    assert ch == 1 and Path(job[1]).name == old_name
    assert hashlib.sha256(Path(patch.convert(job)).read_bytes()).hexdigest() == OLD_SHA[(codec, target)]
    assert patch.convert(job[:5]) == job[1]          # the old five-field job still works


@needs_tools
def test_stereo_pcm_name_and_decode(wavs, tmp_path):
    job, ch = _job(wavs["stereo"], tmp_path, "pcm")
    assert ch == 2 and job[1].endswith("_pcm_ch2.wem")
    x, rate = _decode(patch.convert(job), tmp_path)
    assert x.shape[1] == 2
    assert abs(_dominant(x[:, 0].astype(float), rate) - 440) < 5
    assert abs(_dominant(x[:, 1].astype(float), rate) - 660) < 5


@needs_tools
def test_identical_sides_written_mono(wavs, tmp_path):
    job, ch = _job(wavs["same"], tmp_path, "pcm")
    assert ch == 1 and "_ch2" not in job[1]
    x, _ = _decode(patch.convert(job), tmp_path)
    assert x.shape[1] == 1


@needs_tools
def test_stereo_opus_doubled_bitrate(wavs, tmp_path):
    sjob, _ = _job(wavs["stereo"], tmp_path, "opus24k")
    assert sjob[1].endswith("_opus48k_ch2.wem")
    mjob, _ = _job(wavs["mono"], tmp_path, "opus24k")
    stereo, mono = Path(patch.convert(sjob)), Path(patch.convert(mjob))
    assert stereo.stat().st_size > 1.3 * mono.stat().st_size
    x, rate = _decode(stereo, tmp_path)
    assert x.shape[1] == 2
    assert abs(_dominant(x[:, 0].astype(float), rate) - 440) < 5
    assert abs(_dominant(x[:, 1].astype(float), rate) - 660) < 5


@needs_tools
def test_stereo_same_gain_both_sides(wavs, tmp_path, ):
    job, _ = _job(wavs["stereo"], tmp_path, "pcm")
    x, _ = _decode(patch.convert(job), tmp_path)
    src = np.stack([_tone(440), _tone(660)], axis=1).astype(float)
    ratio = np.abs(x).max(axis=0) / np.abs(src).max(axis=0)
    assert abs(ratio[0] - ratio[1]) < 0.01 * ratio[0]


def test_tone_test_signals_shapes_and_differences():
    sweep, pair, noise, mono = (f() for f in (tts.sweep_signal, tts.pair_signal, tts.noise_signal, tts.mono_signal))
    n = tts.RATE * tts.SECONDS
    assert sweep.shape == pair.shape == noise.shape == (n, 2) and mono.shape == (n, 1)
    assert all(np.abs(s).max() <= 1.0 for s in (sweep, pair, noise, mono))
    q = n // 4                                    # left at the start, right at the half way point
    assert np.abs(sweep[:q // 8, 0]).max() > np.abs(sweep[:q // 8, 1]).max()
    mid = slice(n // 2 - 2400, n // 2 + 2400)
    assert np.abs(sweep[mid, 1]).max() > 5 * np.abs(sweep[mid, 0]).max()
    assert abs(_dominant(pair[:, 0], tts.RATE) - 440) < 2 and abs(_dominant(pair[:, 1], tts.RATE) - 660) < 2
    diff = np.abs(np.fft.rfft(noise[:, 0] - noise[:, 1]))     # what differs between the ears sits in the bass band
    sec = tts.SECONDS
    assert diff[60 * sec:200 * sec].sum() > 5 * diff[400 * sec:3000 * sec].sum()
    assert np.array_equal(tts.noise_signal(7), noise)    # seeded
