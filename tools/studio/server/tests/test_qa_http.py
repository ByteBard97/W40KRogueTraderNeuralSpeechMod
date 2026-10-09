import json
import threading
import urllib.error
import urllib.request

import pytest

from studio_server.app import make_server
from studio_server.model import ModelClient
from conftest import write_wav
from test_qa import qcfg  # noqa: F401  (fixture)


@pytest.fixture
def api(qcfg, tmp_path):
    srv = make_server(qcfg, ModelClient("http://127.0.0.1:9"), port=0, web_dist=tmp_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, path, body=None, raw=False):
        req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req) as r:
                data = r.read()
                return r.status, data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            return e.code, data if raw else json.loads(data)

    yield call
    srv.shutdown()
    srv.server_close()


def test_qa_flow_over_http(api, qcfg):
    assert [r["id"] for r in api("GET", "/api/qa/runs")[1]] == ["export", "runA"]
    assert "Pasqal" in api("GET", "/api/qa/facets")[1]["speakers"]
    st, p = api("GET", "/api/qa/clips?sort=longest&limit=2")
    assert st == 200 and p["total"] == 6 and [i["guid"] for i in p["items"]] == ["q6", "q2"]
    assert api("GET", "/api/qa/clips?run=runA")[1]["total"] == 2
    assert api("GET", "/api/qa/clips?run=nope")[0] == 404
    assert api("GET", "/api/qa/clips?sort=bogus")[0] == 400
    assert api("POST", "/api/qa/verdict", {"guid": "q1", "verdict": "good", "tags": ["x"], "note": "n"})[0] == 200
    p = api("GET", "/api/qa/clips?verdict=good")[1]
    assert [i["guid"] for i in p["items"]] == ["q1"] and p["stats"]["good"] == 1
    assert api("POST", "/api/qa/verdict", {"guid": "q1", "verdict": "meh"})[0] == 400
    assert api("POST", "/api/qa/verdict", {"run": "runA", "guid": "r1", "verdict": "bad"})[0] == 200
    assert (qcfg.render / "audit/verdicts_runA.json").is_file()
    assert api("POST", "/api/qa/verdict", {"guid": "q1", "verdict": None})[0] == 200
    assert api("GET", "/api/qa/clips?verdict=good")[1]["total"] == 0


def test_fx_file_rejects_bad_requests(api):
    assert api("GET", "/fx-file?p=../../etc/passwd&fx=mild", raw=True)[0] == 404
    assert api("GET", "/fx-file?p=data/render/export/wav/nope.wav&fx=mild", raw=True)[0] == 404
    assert api("GET", "/fx-file?p=data/render/export/wav/q1.wav&fx=loud", raw=True)[0] == 400


def test_fx_file_returns_compressed_wav(api, qcfg):
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    write_wav(qcfg.render / "export/wav/hi.wav", 0.5, 24000)       # the other fixtures use a 1 kHz toy rate
    st, body = api("GET", "/fx-file?p=data/render/export/wav/hi.wav&fx=mild", raw=True)
    assert st == 200 and body[:4] == b"RIFF"
