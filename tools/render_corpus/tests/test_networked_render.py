import json
import sys
import threading
from pathlib import Path

import pytest

pytest.importorskip("soundfile")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))

import queue_server as qs  # noqa: E402
import worker as w  # noqa: E402
from jobqueue import JobQueue  # noqa: E402

REF = "data/voices/prompts/narrator/01_designed_narrator.wav"


def job(g, text="The servitor stood in the doorway."):
    return {"guid": g, "speaker": "narrator", "speaker_kind": "narrator", "text": text, "src_text": text, "annotation": None,
            "engine": "voxcpm2", "priority": 1, "voice_source": "narrator", "ref": {"wav": REF, "text": "x", "emotion": None}}


def test_worker_renders_jobs_through_the_server(tmp_path, monkeypatch):
    if not (ROOT / REF).exists():
        pytest.skip("reference clip not on this machine")
    (tmp_path / "wav").mkdir()
    qs.Handler.queue = JobQueue([job("g1"), job("g2"), job("g3")])
    qs.Handler.run_dir, qs.Handler.token = tmp_path, "tok"
    srv = qs.Server(("127.0.0.1", 0), qs.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(w, "REF_CACHE", tmp_path / "refs")
    c = w.Client(f"http://127.0.0.1:{srv.server_address[1]}", "tok", "testbox")
    try:
        got = []
        while True:
            jobs = c.lease("voxcpm2", 2)
            if not jobs:
                break
            for j in jobs:
                from render import render_take
                import io
                import soundfile as sf
                row, wav, sr = render_take(w.fake_synth, j, "voxcpm2", str(c.ref(j["ref"]["wav"])))
                bio = io.BytesIO()
                sf.write(bio, wav, sr, format="WAV", subtype="PCM_16")
                c.result(row, bio.getvalue())
                got.append(j["guid"])
        assert sorted(got) == ["g1", "g2", "g3"]
        rows = [json.loads(ln) for ln in (tmp_path / "manifest.jsonl").read_text().splitlines()]
        assert {r["guid"] for r in rows} == {"g1", "g2", "g3"} and all(r["worker"] == "testbox" and r["status"] == "ok" for r in rows)
        assert all((tmp_path / "wav" / f"{g}.wav").stat().st_size > 1000 for g in got)
        assert qs.read_manifest(tmp_path / "manifest.jsonl")[0] == {"g1", "g2", "g3"}
        import urllib.request
        st = json.load(urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/status"))
        assert st["done"] == 3 and st["workers"]["testbox"]["jobs"] == 3
    finally:
        srv.shutdown()


def test_bad_token_is_refused(tmp_path):
    qs.Handler.queue = JobQueue([])
    qs.Handler.run_dir, qs.Handler.token = tmp_path, "tok"
    srv = qs.Server(("127.0.0.1", 0), qs.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = w.Client(f"http://127.0.0.1:{srv.server_address[1]}", "wrong", "x")
        with pytest.raises(Exception):
            c._req("/lease", b"{}", retries=1)
    finally:
        srv.shutdown()
