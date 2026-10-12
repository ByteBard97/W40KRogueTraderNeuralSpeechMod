import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools/bnk_patch"))

from stitch import stitch  # noqa: E402
from wem import TP_CEILING, linear_gain_db  # noqa: E402

SR = 24000


def tone(amp):
    return (amp * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)


def test_gain_reaches_target_when_peak_allows():
    assert linear_gain_db(-25.0, -12.0, -22.0) == 3.0


def test_gain_is_capped_by_the_true_peak_ceiling():
    assert linear_gain_db(-25.0, -3.0, -22.0) == TP_CEILING + 3.0


def test_trim_shifts_the_target_but_not_the_ceiling():
    assert linear_gain_db(-25.0, -20.0, -22.0, trim=1.0) == 4.0
    assert linear_gain_db(-25.0, -3.0, -22.0, trim=5.0) == TP_CEILING + 3.0


def test_preset_level_never_boosts_and_only_guards_the_peak():
    assert linear_gain_db(-30.0, -10.0, None) == 0.0
    assert linear_gain_db(-20.0, -0.5, None) == TP_CEILING + 0.5


def test_stitch_keeps_segment_levels_when_matching_is_off():
    quiet, loud = tone(0.05), tone(0.4)
    matched = stitch([quiet, loud], SR)
    kept = stitch([quiet, loud], SR, match_levels=False)
    n = len(quiet) // 2
    assert abs(np.sqrt(np.mean(matched[:n] ** 2)) / np.sqrt(np.mean(matched[-n:] ** 2)) - 1) < 0.2
    assert np.sqrt(np.mean(kept[-n:] ** 2)) > 4 * np.sqrt(np.mean(kept[:n] ** 2))
