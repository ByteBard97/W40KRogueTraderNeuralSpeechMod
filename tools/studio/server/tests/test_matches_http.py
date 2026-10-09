import json
import threading
import urllib.error
import urllib.request

import pytest

from studio_server.app import make_server
from studio_server.model import ModelClient


@pytest.fixture
def api(pcfg, tmp_path):
    srv = make_server(pcfg, ModelClient("http://127.0.0.1:9"), port=0, web_dist=tmp_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, path, body=None):
        req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    yield call
    srv.shutdown()
    srv.server_close()


def test_matches_flow_over_http(api, pcfg):
    st, p = api("GET", "/api/matches")
    assert st == 200 and p["total"] == 2 and p["counts"]["bank"] == 1 and p["counts"]["nobank"] == 1
    assert api("GET", "/api/matches?group=bank")[1]["items"][0]["speaker"] == "Heinrix"
    assert api("POST", "/api/matches/decision", {"id": "C1|a", "value": "maybe"})[0] == 400
    assert api("POST", "/api/matches/decision", {"id": "zzz", "value": "accept"})[0] == 404
    assert api("POST", "/api/matches/decision", {"id": "C1|a", "value": "reject"}) == (200, {"pools_rebuilt": False})
    assert api("GET", "/api/matches?state=reject")[1]["total"] == 1
    assert api("POST", "/api/matches/decision", {"id": "C1|a", "value": ""})[0] == 200
    assert api("GET", "/api/matches?state=reject")[1]["total"] == 0
