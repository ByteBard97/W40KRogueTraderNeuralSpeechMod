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


def test_fx_flow_over_http(api, pcfg):
    assert [p["name"] for p in api("GET", "/api/fx/library")[1]] == ["Clean", "Mine"]
    assert api("POST", "/api/fx/labels", {"machine": ["Nope"]})[0] == 400
    assert api("POST", "/api/fx/labels", {"machine": ["Clean"], "vox_channel": ["Mine"]})[1]["machine"] == ["Clean"]
    assert api("GET", "/api/fx/labels")[1]["vox_channel"] == ["Mine"]
    api("POST", "/api/pools/rebuild", {"min_slot_lines": 3})
    st, p = api("GET", "/api/fx/assignments/preview")
    assert st == 200 and p["lines"] == 3 and not (pcfg.data / "fx_lab/assignments.json").exists()
    st, w = api("POST", "/api/fx/assignments")
    assert st == 200 and w["path"] == "data/fx_lab/assignments.json" and (pcfg.data / "fx_lab/assignments.json").is_file()
