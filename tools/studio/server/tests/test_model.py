import base64
import pytest

from studio_server.errors import ApiError
from studio_server.model import ModelClient
from mock_backend import MockBackend


def test_health_states(cfg):
    assert ModelClient("http://127.0.0.1:9").health() == "down"
    mb = MockBackend(cfg.voice_design)
    try:
        assert ModelClient(mb.url).health() == "ready"
        mb.busy = True
        assert ModelClient(mb.url).health() == "busy"
    finally:
        mb.close()


def test_call_unreachable_is_503_and_backend_error_is_502(cfg):
    with pytest.raises(ApiError) as e:
        ModelClient("http://127.0.0.1:9").call("/generate", {})
    assert e.value.status == 503 and "live_backend" in e.value.message
    mb = MockBackend(cfg.voice_design, fail=True)
    try:
        with pytest.raises(ApiError) as e2:
            ModelClient(mb.url).call("/generate", {})
        assert e2.value.status == 502 and "boom" in e2.value.message
    finally:
        mb.close()


def test_remote_mode_sends_the_reference_clip_and_saves_the_returned_audio(cfg, tmp_path):
    backend_side = tmp_path / "windows_box"        # the backend writes its own wavs here, not under the studio's repo
    mb = MockBackend(backend_side)
    try:
        client = ModelClient(mb.url, root=cfg.root, live_dir=cfg.voice_design, remote=True)
        out = client.call("/generate", {"text": "hi", "reference_wav": "data/voices/wav/Pasqal/E1.wav"})
        sent = mb.calls[0]
        assert "reference_wav" not in sent and sent["return_audio"] is True
        assert base64.b64decode(sent["reference_b64"]) == (cfg.root / "data/voices/wav/Pasqal/E1.wav").read_bytes()
        assert "audio_b64" not in out and (cfg.voice_design / out["file"]).read_bytes()[:4] == b"RIFF"
    finally:
        mb.close()


def test_local_mode_is_unchanged_and_localhost_is_not_remote(cfg):
    assert ModelClient("http://127.0.0.1:8909").remote is False
    assert ModelClient("http://192.168.0.211:8909").remote is True
    mb = MockBackend(cfg.voice_design)
    try:
        ModelClient(mb.url, root=cfg.root, live_dir=cfg.voice_design).call("/generate", {"reference_wav": "data/x.wav"})
        assert mb.calls[0]["reference_wav"] == "data/x.wav" and "return_audio" not in mb.calls[0]
    finally:
        mb.close()


def test_a_slow_generation_is_a_timeout_not_not_running(cfg, monkeypatch):
    import socket
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(socket.timeout("timed out")))
    with pytest.raises(ApiError) as e:
        ModelClient("http://127.0.0.1:9").call("/generate", {})
    assert e.value.status == 504 and "longer than" in e.value.message
