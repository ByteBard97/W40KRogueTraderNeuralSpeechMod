"""Render a Faust .dsp over a mono signal with DawDreamer (the batch-side runtime of the FX Lab).

Run under tools/fx_lab/.venv-fx/bin/python (dawdreamer, numpy, soundfile). Parameters are keyed by control key (key_of: the
full address with the root stripped, in shortname form), the same keys the page and data/fx_lab/presets.json use. Checkboxes (the per-stage on/off stomps) default to on, as in
the page; every other control defaults to its Faust init value and is reset to it before each render.

Compiling the Faust code costs about 1.5 s, so engines are cached per (code, sample rate) and only the input signal and
the parameters change between clips (about 30 ms per clip). Re-rendering a clip on a reused engine gives bit-identical
output to a fresh one (checked), so the effect tails do not leak between clips.
"""
from __future__ import annotations

import re

import numpy as np
import dawdreamer as daw

BLOCK = 128
_ENGINES: dict[tuple[str, int], "_Engine"] = {}


def short(label: str) -> str:
    """Control label -> the shortname the page uses ('Highpass Hz (0 off)' -> 'Highpass_Hz_0_off')."""
    return re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")


def key_of(d: dict) -> str:
    """The parameter key: the control's full address with the root segment stripped, in shortname form.

    DawDreamer names a control '/<root>/n1/Ring_Hz' and its 'label' is only the last segment, so two blocks holding the same label
    collide if keyed by label. A flat control ('/<root>/Highpass Hz (0 off)') gets the same key as before. Matches the browser engine's key
    (tools/fx_lab/render_wasm.mjs keyOf), never its 'shortname' field, which Faust shortens to the shortest unique suffix."""
    path = d["name"].split("/", 2)[2] if d["name"].startswith("/") and d["name"].count("/") >= 2 else d["label"]
    return short(path)


def list_params(dsp_code: str, sr: int) -> list[str]:
    """Every control key of a program, in DawDreamer's order."""
    key = (dsp_code, sr)
    if key not in _ENGINES:
        _ENGINES[key] = _Engine(dsp_code, sr)
    return [p[1] for p in _ENGINES[key].params]


def is_checkbox(d: dict) -> bool:
    return d["min"] == 0 and d["max"] == 1 and d["numSteps"] == 2


class _Engine:
    def __init__(self, code: str, sr: int):
        self.sr = sr
        self.engine = daw.RenderEngine(sr, BLOCK)
        self.src = self.engine.make_playback_processor("in", np.zeros((1, sr), dtype=np.float32))
        self.fx = self.engine.make_faust_processor("fx")
        self.fx.set_dsp_string(code)
        self.engine.load_graph([(self.src, []), (self.fx, ["in"])])
        self.params = [(d["index"], key_of(d), is_checkbox(d), float(d["value"])) for d in self.fx.get_parameters_description()]

    def render(self, x: np.ndarray, params: dict, tail_s: float) -> np.ndarray:
        n = len(x) + int(round(tail_s * self.sr))
        buf = np.zeros((1, n), dtype=np.float32)
        buf[0, : len(x)] = x
        self.src.set_data(buf)
        for idx, key, is_box, default in self.params:
            self.fx.set_parameter(idx, float(params[key]) if key in params else (1.0 if is_box else default))
        self.engine.render(n / self.sr)
        return self.engine.get_audio().astype(np.float32)[:, :n]


def render(dsp_code: str, x: np.ndarray, sr: int, params: dict | None = None, tail_s: float = 0.0, stereo: bool = False) -> np.ndarray:
    """Process x (mono float32) through dsp_code. Output length is len(x) + tail_s seconds.

    The chain has two output channels (left = right while the stereo blocks are off). By default the left channel is returned as a 1-D
    array, as before; with stereo=True the result is shape (2, n)."""
    key = (dsp_code, sr)
    if key not in _ENGINES:
        _ENGINES[key] = _Engine(dsp_code, sr)
    y = _ENGINES[key].render(np.asarray(x, dtype=np.float32), params or {}, tail_s)
    return y if stereo else y[0]
