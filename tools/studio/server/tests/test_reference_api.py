import json
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio_server.config import Config  # noqa: E402
from studio_server.errors import ApiError  # noqa: E402
from studio_server.model import ModelClient  # noqa: E402
from studio_server.routes import build_router  # noqa: E402

SR = 24000
CLIPS = 3


def write(path: Path, seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    x = (np.random.default_rng(seed).standard_normal(SR * 3) * 8000).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(x.tobytes())


@pytest.fixture
def cfg(tmp_path):
    cat = {}
    for i in range(CLIPS):
        write(tmp_path / f"data/voices/wav/Mono/{i}.wav", i)
        cat[f"m{i}"] = {"event": f"Mono_{i}", "speaker": "Mono", "wav": f"wav/Mono/{i}.wav", "duration": 3.0}
    (tmp_path / "data/voices").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/voices/catalog.json").write_text(json.dumps(cat))
    return Config(root=tmp_path)


def get(cfg, path, query=None):
    return build_router().dispatch("GET", path, query or {}, {}, cfg, ModelClient("http://127.0.0.1:9"))


def test_speakers_lists_the_catalog_speakers_with_clip_counts(cfg):
    status, body = get(cfg, "/api/ref/speakers")
    assert status == 200 and body == [{"speaker": "Mono", "clips": CLIPS}]


def test_ltas_returns_the_spectrum_for_a_known_speaker(cfg):
    status, body = get(cfg, "/api/ref/ltas", {"speaker": "Mono"})
    assert status == 200 and body["speaker"] == "Mono" and len(body["freqs"]) == len(body["db"]) and body["clips_used"] == CLIPS


def test_ltas_without_a_speaker_is_a_400(cfg):
    assert get(cfg, "/api/ref/ltas")[0] == 400


def test_ltas_for_an_unknown_speaker_is_a_404(cfg):
    status, body = get(cfg, "/api/ref/ltas", {"speaker": "Nobody"})
    assert status == 404 and "Nobody" in json.dumps(body)
