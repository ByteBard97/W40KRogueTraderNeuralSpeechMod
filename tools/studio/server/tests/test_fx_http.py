import json
import sys
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


def test_fx_diff_usage_backups_and_restore_over_http(api, pcfg):
    api("POST", "/api/pools/rebuild", {"min_slot_lines": 3})
    api("POST", "/api/fx/labels", {"machine": ["Clean"]})
    st, d = api("GET", "/api/fx/assignments/diff")
    assert st == 200 and d["changed"] >= 1 and d["rows"][0]["after"] == ["Clean"] and d["rows"][0]["now"] == []
    st, u = api("GET", "/api/fx/labels/usage")
    assert st == 200 and u["labels"]["machine"]["lines"] == 2
    assert api("GET", "/api/fx/backups") == (200, [])
    first = api("POST", "/api/fx/assignments")[1]
    assert first["backup"] is None and first["affected_speakers"] >= 1
    api("POST", "/api/fx/labels", {"machine": ["Mine"]})
    second = api("POST", "/api/fx/assignments")[1]
    assert [b["kind"] for b in api("GET", "/api/fx/backups")[1]].count("assignments") == 1
    st, r = api("POST", "/api/fx/restore", {"backup": second["backup"]})
    assert st == 200 and r["kind"] == "assignments"
    assert api("POST", "/api/fx/restore", {"backup": "../../etc/passwd"})[0] == 404
    assert api("GET", "/api/fx/library")[1][0]["family"] == "Clean"


def test_fx_render_validates_and_says_501_without_the_fx_environment(api, pcfg):
    st, body = api("GET", "/fx-render?presets=Nope", raw=True)
    assert st == 400
    st, body = api("GET", "/fx-render", raw=True)
    assert st == 400
    st, body = api("GET", "/fx-render?preset=Clean&p=data/voices/wav/Pasqal/E1.wav", raw=True)
    assert st == 501 and b".venv-fx" in body
    assert api("GET", "/fx-render?preset=Clean&p=data/voices/nothing.wav", raw=True)[0] == 404


def test_fx_render_runs_the_chain_and_caches(api, pcfg):
    py = pcfg.root / "tools/fx_lab/.venv-fx/bin/python"          # a stand-in for the FX environment: copies --in to --out
    py.parent.mkdir(parents=True)
    py.write_text(f"#!{sys.executable}\nimport shutil, sys\na = sys.argv\nshutil.copyfile(a[a.index('--in') + 1], a[a.index('--out') + 1])\n"
                  f"open({str(pcfg.root / 'calls.log')!r}, 'a').write(' '.join(a[a.index('--preset'):]) + '\\n')\n")
    py.chmod(0o755)
    url = "/fx-render?presets=Clean|Mine&p=data/voices/wav/Pasqal/E1.wav"
    st, wav = api("GET", url, raw=True)
    assert st == 200 and wav[:4] == b"RIFF"
    assert api("GET", url, raw=True)[1] == wav
    assert (pcfg.root / "calls.log").read_text().splitlines() == ["--preset Clean --preset Mine"]    # second call was cached
    st, default = api("GET", "/fx-render?preset=Clean", raw=True)                                    # default Pasqal sample
    assert st == 200 and default[:4] == b"RIFF"
