import json
import sys
import threading
import urllib.request
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import audit_server as a  # noqa: E402


def test_auto_flags():
    assert "cap_hit" in a.auto_flags(29.8, 400, [])
    assert "slow" in a.auto_flags(20.0, 60, [])
    assert "fast" in a.auto_flags(2.0, 80, [])
    assert "short" in a.auto_flags(0.5, 5, [])
    assert a.auto_flags(10.0, 150, ["too_long"]) == ["too_long"]


def _wav(p: Path, secs=1.0):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(b"\x00\x00" * int(8000 * secs))


def test_server_serves_clips_range_and_saves_verdicts(tmp_path):
    (tmp_path / "wav").mkdir()
    _wav(tmp_path / "wav/g1.wav")
    a.Handler.clips = [{"guid": "g1", "wav": "wav/g1.wav", "text": "hi", "flags": []}]
    a.Handler.wavdir = tmp_path / "wav"
    a.Handler.verdicts_path = tmp_path / "v.json"
    a.Handler.verdicts = {}
    srv = a.Server(("127.0.0.1", 0), a.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        d = json.load(urllib.request.urlopen(base + "/api/clips"))
        assert d["clips"][0]["guid"] == "g1"
        r = urllib.request.urlopen(urllib.request.Request(base + "/wav/g1.wav", headers={"Range": "bytes=0-9"}))
        assert r.status == 206 and len(r.read()) == 10
        post = lambda body: urllib.request.urlopen(urllib.request.Request(base + "/api/verdict", data=json.dumps(body).encode()))
        post({"guid": "g1", "verdict": "bad", "tags": ["robotic"], "note": "x"})
        assert json.loads((tmp_path / "v.json").read_text())["g1"]["tags"] == ["robotic"]
        post({"guid": "g1", "verdict": None})
        assert json.loads((tmp_path / "v.json").read_text()) == {}
        try:
            urllib.request.urlopen(base + "/wav/..%2f..%2fetc%2fpasswd")
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.shutdown()


def test_concurrent_verdict_posts_all_succeed(tmp_path):
    a.Handler.clips = []
    a.Handler.verdicts_path = tmp_path / "v.json"
    a.Handler.verdicts = {}
    srv = a.Server(("127.0.0.1", 0), a.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/api/verdict"
    errs = []

    def post(i):
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=json.dumps({"guid": f"g{i}", "verdict": "good"}).encode())).read()
        except Exception as e:  # noqa: BLE001
            errs.append(e)

    ts = [threading.Thread(target=post, args=(i,)) for i in range(40)]
    [t.start() for t in ts]; [t.join() for t in ts]
    srv.shutdown()
    assert not errs and len(json.loads((tmp_path / "v.json").read_text())) == 40


def test_fx_param_returns_processed_wav_of_same_length(tmp_path):
    import numpy as np
    sr = 24000
    t = np.arange(sr * 2) / sr
    x = 0.1 * np.sin(2 * np.pi * 200 * t)
    x[sr:sr + 50] += 0.8 * np.random.default_rng(0).standard_normal(50) * 0.5   # a click
    (tmp_path / "wav").mkdir()
    with wave.open(str(tmp_path / "wav/g.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    a.Handler.clips = []; a.Handler.wavdir = tmp_path / "wav"; a.Handler.fx_cache = {}
    srv = a.Server(("127.0.0.1", 0), a.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/wav/g.wav"
    try:
        orig = urllib.request.urlopen(base).read()
        proc = urllib.request.urlopen(base + "?fx=strong").read()
        assert proc != orig and proc[:4] == b"RIFF"
        with wave.open(__import__("io").BytesIO(proc)) as w:
            assert w.getnframes() == len(x) and w.getframerate() == sr
    finally:
        srv.shutdown()
