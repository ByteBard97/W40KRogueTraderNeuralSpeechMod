"""The reference side of the FX Lab monitor: average spectrum and stereo stats of a game speaker's clips (reference.py)."""
import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reference as R  # noqa: E402

SR = 24000


def write(path: Path, left, right=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    chans = [left] if right is None else [left, right]
    data = np.stack(chans, axis=1).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(len(chans)); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data.tobytes())


def noise(sec, seed, amp=8000):
    return (np.random.default_rng(seed).standard_normal(int(SR * sec)) * amp).astype(np.int16)


def repo(tmp_path):
    cat = {}
    for i in range(4):
        write(tmp_path / f"data/voices/wav/Mono/{i}.wav", noise(3, i))
        cat[f"m{i}"] = {"event": f"Mono_{i}", "speaker": "Mono", "wav": f"wav/Mono/{i}.wav", "duration": 3.0}
    for i in range(4):
        a = noise(3, 10 + i)
        write(tmp_path / f"data/voices/wav/Wide/{i}.wav", a, noise(3, 20 + i))        # independent channels
        cat[f"w{i}"] = {"event": f"Wide_{i}", "speaker": "Wide", "wav": f"wav/Wide/{i}.wav", "duration": 3.0}
    write(tmp_path / "data/voices/wav/_unattributed/0.wav", noise(3, 40))
    cat["u0"] = {"event": "Companions_Techpriest_1", "speaker": "_unattributed", "wav": "wav/_unattributed/0.wav", "duration": 3.0}
    (tmp_path / "data/voices/catalog.json").write_text(json.dumps(cat))
    (tmp_path / "data/voices/attribution.json").write_text(json.dumps({"u0": {"speaker": "Mono", "basis": "x"}}))
    return tmp_path


def test_the_band_centres_run_in_thirds_of_an_octave_from_50_hz_to_12_5_khz():
    assert abs(R.BAND_CENTRES[0] - 50) < 3 and abs(R.BAND_CENTRES[-1] - 12700) < 500 and len(R.BAND_CENTRES) == 25
    ratio = R.BAND_CENTRES[1] / R.BAND_CENTRES[0]
    assert abs(ratio - 2 ** (1 / 3)) < 1e-6


def test_speakers_lists_those_with_audio_using_the_attribution_overlay(tmp_path):
    root = repo(tmp_path)
    got = {s["speaker"]: s["clips"] for s in R.speakers(root)}
    assert got == {"Mono": 5, "Wide": 4}                      # the unattributed clip counts for the speaker it was assigned to


def test_white_noise_gives_a_flat_average_spectrum_with_the_level_removed(tmp_path):
    r = R.ltas(repo(tmp_path), "Mono")
    db = np.array([np.nan if d is None else d for d in r["db"]])
    assert len(db) == len(R.BAND_CENTRES) and abs(np.nanmean(db)) < 3     # level removed
    assert np.nanstd(db[3:-3]) < 3                                             # white noise is flat in these bands up to the band-width tilt
    assert r["clips_used"] >= 4


def test_stereo_stats_tell_a_mono_clip_from_one_with_independent_channels(tmp_path):
    root = repo(tmp_path)
    mono, wide = R.ltas(root, "Mono")["stereo"], R.ltas(root, "Wide")["stereo"]
    assert mono is None or mono["clips"] == 0                             # mono files have no stereo stats
    assert wide["clips"] == 4 and abs(wide["corr"]) < 0.2 and wide["side_mid_db"] > -3


def test_an_unknown_speaker_is_an_error(tmp_path):
    try:
        R.ltas(repo(tmp_path), "Nobody")
    except KeyError:
        return
    raise AssertionError("expected KeyError")
