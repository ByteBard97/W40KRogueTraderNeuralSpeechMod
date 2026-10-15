"""The Studio's preview and apply-to-take path (studio_server/fx_apply.py) writes one wav; a stereo preset must give a 2-channel file."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "studio/server/studio_server"))
import batch  # noqa: E402
import fx_apply  # noqa: E402

SR = 24000
WIDE = {"Stereo_chorus_mix_0_off": 1, "Stereo_chorus_depth_ms": 4}
PLAIN = {"Ring_Hz": 40, "Ring_mix": 0.3}


def clip(tmp_path):
    p = tmp_path / "in.wav"
    sf.write(str(p), (np.random.default_rng(1).laplace(0, 0.05, SR * 2)).astype(np.float32), SR)
    return p


def test_a_stereo_preset_gives_a_two_channel_file(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "load_presets", lambda: {"Wide": {"dsp": "chain.dsp", "params": WIDE}, "Plain": {"dsp": "chain.dsp", "params": PLAIN}})
    wide, plain = tmp_path / "wide.wav", tmp_path / "plain.wav"
    fx_apply.apply(clip(tmp_path), wide, ["Wide"])
    fx_apply.apply(clip(tmp_path), plain, ["Plain"])
    yw, srw = sf.read(str(wide))
    yp, _ = sf.read(str(plain))
    assert srw == SR and yw.ndim == 2 and yw.shape[1] == 2 and yw.shape[0] > SR     # frames first, then channels
    assert np.abs(yw[:, 0] - yw[:, 1]).max() > 0.01                                  # the sides really differ
    assert yp.ndim == 1                                                              # no stereo block: still a mono file, as before
