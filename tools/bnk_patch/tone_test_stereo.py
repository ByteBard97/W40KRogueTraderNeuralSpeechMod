"""Stereo test bank: four Footfall lines replaced with stereo test signals, one small bank per codec. Stage only; nothing
here touches the game folder. The bank is the tone_test3.py kind (every other line in the bank stays original).

  A  440 Hz tone panning left -> right -> left over 4 s (constant power)
  B  left ear 440 Hz, right ear 660 Hz
  C  speech-like noise (200-3500 Hz, syllable-rate pulsing) identical in both ears, plus a 60-200 Hz bass band that differs per ear
  D  control: a plain mono 440 Hz tone

  python3 tone_test_stereo.py --bank PRISTINE.bnk --codec pcm [--out-dir DIR]
  python3 tone_test_stereo.py --bank PRISTINE.bnk --codec opus [--out-dir DIR]

PRISTINE.bnk is the untouched original AIVO charvogen bank, the same file tone_test3.py takes. --out-dir defaults to
/tmp/stereo_tone_test; the bank lands in DIR/<codec>/w40krt_avio_charvogen.bnk (plus the generated .wav files in DIR/signals).

Install by hand, one codec at a time (PCM first; stereo PCM is the safer one):
  1. In the game's soundbanks folder (inside the W40KRT_AIVOMod folder), move the installed w40krt_avio_charvogen.bnk and
     its _pcmN side banks into soundbanks_disabled/ with a suffix such as .before-stereo-test (move, do not delete).
  2. Copy DIR/<codec>/w40krt_avio_charvogen.bnk into soundbanks/. It is small and needs no side banks.
  3. Start the game with headphones, load a save, open the Footfall conversation with Vladaym and play the four test lines
     (the same lines as tone_test3.py: A, B, C, D in that order, event ev_<guid> as listed in LINES below).
  4. Listen: A should travel from the left ear to the right and back; B should be a lower tone on the left and a higher one
     on the right; C should show a different rumble in each ear over the same hiss; D is the same tone in both ears.
     Silence means that codec/channel layout is not playable. Note which lines were heard for each codec.
Roll back: delete nothing; move the test bank out of soundbanks/ and the files you set aside in step 1 back in.
Mixed mono and stereo Opus in one bank is unproven; this test puts a mono control (D) next to three stereo lines.
"""
import argparse, os, struct, sys, wave
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from bank import Bank, PLUGIN_OPUS_WEM, PLUGIN_PCM
from tone_test import MAIN_NAME, write_bank
from tone_test3 import LINES
from opus_wem import opus_wem
from wem import linear_gain_db, measure_levels, pcm_wem

RATE = 24000
SECONDS = 4
AMP = 0.4
TONE_HZ, RIGHT_HZ = 440, 660
FADE_S = 0.05
SPEECH_BAND = (200, 3500)
BASS_BAND = (60, 200)
SYLLABLE_HZ = 4
BASS_GAIN = 0.8
TARGET_LUFS = -20.0
OPUS_STEREO_BITRATE = "48k"
DEFAULT_OUT = "/tmp/stereo_tone_test"


def _t():
    return np.arange(RATE * SECONDS) / RATE


def _fade(x):
    n = int(RATE * FADE_S)
    env = np.ones(len(x))
    env[:n] = np.linspace(0, 1, n)
    env[-n:] = np.linspace(1, 0, n)
    return x * (env if x.ndim == 1 else env[:, None])


def _band_noise(rng, lo, hi, n):
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / RATE)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / np.abs(x).max()


def sweep_signal():
    """(n, 2) float: 440 Hz panned left -> right -> left, constant power."""
    t = _t()
    pan = 0.5 - 0.5 * np.cos(2 * np.pi * t / SECONDS)         # 0 left, 1 right
    tone = np.sin(2 * np.pi * TONE_HZ * t)
    return _fade(AMP * np.stack([np.cos(pan * np.pi / 2) * tone, np.sin(pan * np.pi / 2) * tone], axis=1))


def pair_signal():
    """(n, 2) float: left 440 Hz, right 660 Hz."""
    t = _t()
    return _fade(AMP * np.stack([np.sin(2 * np.pi * TONE_HZ * t), np.sin(2 * np.pi * RIGHT_HZ * t)], axis=1))


def noise_signal(seed=7):
    """(n, 2) float: the same pulsing speech-band noise in both ears, an independent bass band in each."""
    rng, t = np.random.default_rng(seed), _t()
    n = len(t)
    speech = _band_noise(rng, *SPEECH_BAND, n) * (0.5 + 0.5 * np.sin(2 * np.pi * SYLLABLE_HZ * t)) ** 2
    bass = [_band_noise(rng, *BASS_BAND, n) * BASS_GAIN for _ in range(2)]
    x = np.stack([speech + bass[0], speech + bass[1]], axis=1)
    return _fade(AMP * x / np.abs(x).max())


def mono_signal():
    return _fade(AMP * np.sin(2 * np.pi * TONE_HZ * _t()))[:, None]


SIGNALS = {"A": sweep_signal, "B": pair_signal, "C": noise_signal, "D": mono_signal}


def write_wav(path, x):
    data = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(data.shape[1]); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(data.tobytes())


def build_wem(wav, channels, codec):
    if codec == "pcm":
        return pcm_wem(wav, TARGET_LUFS, 0.0, channels), PLUGIN_PCM
    lufs, tp = measure_levels(wav, channels)
    gain = linear_gain_db(lufs, tp, TARGET_LUFS)
    bitrate = OPUS_STEREO_BITRATE if channels == 2 else "24k"
    return opus_wem(wav, bitrate=bitrate, gain_db=gain, channels=channels), PLUGIN_OPUS_WEM


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--codec", choices=["pcm", "opus"], required=True)
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    a = ap.parse_args()
    sig_dir = os.path.join(a.out_dir, "signals")
    out = os.path.join(a.out_dir, a.codec)
    os.makedirs(sig_dir, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    bank = Bank(a.bank)
    hirc, new = bytearray(bank.hirc), {}
    for k, guid in LINES.items():
        x = SIGNALS[k]()
        wav = os.path.join(sig_dir, k + ".wav")
        write_wav(wav, x)
        data, plugin = build_wem(wav, x.shape[1], a.codec)
        snd, med = bank.media_for_guid(guid)
        struct.pack_into("<I", hirc, bank.sounds[snd] + 4, plugin)
        struct.pack_into("<I", hirc, bank.sounds[snd] + 13, len(data))
        new[med] = data
        print(k, guid[:8], "ch", x.shape[1], hex(plugin), len(data), "bytes")
    keep = [(m, len(d), (lambda d=d: d)) for m, d in new.items()]     # only the test clips, like tone_test3.py --only-new
    write_bank(os.path.join(out, MAIN_NAME), bank.bkhd, struct.unpack_from("<I", bank.bkhd, 4)[0], keep, hirc)
    print("wrote", os.path.join(out, MAIN_NAME))


if __name__ == "__main__":
    main()
