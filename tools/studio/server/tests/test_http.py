import json
import threading
import urllib.error
import urllib.request

import pytest

from studio_server.app import make_server
from studio_server.model import ModelClient
from mock_backend import MockBackend


@pytest.fixture
def api(cfg, tmp_path):
    mb = MockBackend(cfg.voice_design)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>studio</title>", encoding="utf-8")
    srv = make_server(cfg, ModelClient(mb.url), port=0, web_dist=dist)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, path, body=None):
        req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if r.headers["Content-Type"].startswith("application/json") else raw)
        except urllib.error.HTTPError as e:
            raw = e.read()
            return e.code, (json.loads(raw) if raw[:1] == b"{" else raw)

    yield call
    srv.shutdown()
    srv.server_close()
    mb.close()


def test_health_and_listing(api):
    assert api("GET", "/api/model/health") == (200, {"state": "ready"})
    st, speakers = api("GET", "/api/speakers")
    assert st == 200 and {s["name"] for s in speakers} == {"Pasqal", "Muaran"}


def test_full_designed_flow_over_http(api):
    st, take = api("POST", "/api/speakers/muaran/design/generate", {"seed": "7"})
    assert st == 200 and take["seed"] == 7
    st, kept = api("POST", "/api/speakers/muaran/design/keep", {"file": take["file"], "seed": 7, "cfg": 2.0, "timesteps": 10})
    assert kept == {"cand": "c2.wav"}
    assert api("POST", "/api/speakers/muaran/design/order", {"order": ["c2.wav", "c0.wav", "c1.wav"]})[0] == 200
    st, d = api("GET", "/api/speakers/muaran")
    assert d["design"]["pick"] == "c2.wav" and [c["id"] for c in d["design"]["candidates"]][0] == "c2.wav"


def test_clone_profile_rate_flow(api):
    body = {"guid": "g1", "text": "Hi.", "reference": {"wav": "data/voices/wav/Pasqal/E1.wav", "text": "Hello."},
            "options": {"cfg": 2.0, "timesteps": 10, "seed": "", "use_instruct": False, "retry_badcase": False,
                        "normalize": False, "continuation": False}}
    st, t = api("POST", "/api/speakers/pasqal/clone/generate", body)
    assert st == 200
    assert api("POST", f"/api/speakers/pasqal/takes/{t['id']}/rate", {"rating": 4})[1]["rating"] == 4
    st, takes = api("GET", "/api/speakers/pasqal/takes")
    assert [x["id"] for x in takes] == [t["id"]]
    assert api("GET", "/api/speakers/pasqal/profile")[0] == 404
    st, p = api("POST", "/api/speakers/pasqal/profile", {"source": {"wav": body["reference"]["wav"], "text": "Hello.", "origin": "real"}})
    assert st == 200 and api("GET", "/api/speakers/pasqal/profile")[1]["name"] == "Pasqal"
    assert api("POST", "/api/speakers/pasqal/active", {})[1] == {"active": "data/studio/pasqal/active.json"}


def test_file_route_serves_whitelisted_only(api):
    st, raw = api("GET", "/file?p=data/voices/wav/Pasqal/E1.wav")
    assert st == 200 and raw[:4] == b"RIFF"
    for bad in ("../README.md", "data/strings.enGB.json", "/etc/passwd", "data/voices/wav/Pasqal/nope.wav"):
        assert api("GET", "/file?p=" + bad)[0] == 404


def test_spa_fallback_and_unknown_api(api):
    st, raw = api("GET", "/speakers/pasqal")
    assert st == 200 and b"<title>studio</title>" in raw
    assert api("GET", "/api/nope")[0] == 404


def test_takes_of_unknown_speaker_is_404(api):
    assert api("GET", "/api/speakers/nobody/takes")[0] == 404


def test_missing_key_in_body_answers_500_json_not_a_dropped_connection(api):
    st, body = api("POST", "/api/speakers/pasqal/clone/generate", {"text": "Hi.", "reference": {"wav": "data/voices/wav/Pasqal/E1.wav"}})
    assert st == 500 and "error" in body


def test_register_over_http(api):
    assert api("POST", "/api/speakers/muaran/register", {})[0] == 400
    api("POST", "/api/speakers/muaran/design/verdict", {"cand": "c0.wav", "pick": True})
    st, r = api("POST", "/api/speakers/muaran/register", {})
    assert st == 200 and r == {"registered": ["Muaran"]}


def test_model_down_is_503_for_live_calls(cfg, tmp_path):
    srv = make_server(cfg, ModelClient("http://127.0.0.1:9"), port=0, web_dist=tmp_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/api/speakers/muaran/design/generate",
                                     method="POST", data=b"{}")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        assert e.value.code == 503
    finally:
        srv.shutdown()
        srv.server_close()


def test_register_all_over_http(api):
    assert api("POST", "/api/speakers/register-all", {}) == (200, {"registered": [], "skipped": []})
