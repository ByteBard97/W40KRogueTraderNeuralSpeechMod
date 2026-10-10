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


def test_pools_flow_over_http(api):
    assert api("GET", "/api/pools")[0] == 404
    st, s = api("POST", "/api/pools/rebuild", {"min_slot_lines": 3})
    assert st == 200 and s["total"] == 15 and s["queue_entries"] == 2
    assert api("GET", "/api/pools")[1]["destinations"]["slot"] == 11
    st, page = api("GET", "/api/pools/routes?to=slot&slot=female_human&limit=2")
    assert st == 200 and page["total"] == 3 and len(page["items"]) == 2
    assert api("GET", "/api/pools/routes?queued=1")[1]["total"] == 3
    st, q = api("GET", "/api/pools/queue")
    assert st == 200 and len(q) == 2
    assert api("POST", "/api/pools/routes", {"entry": q[0]["entry"] or "", "guids": ["u13"], "to": "slot", "slot": "female_human"})[0] == 200
    assert api("POST", "/api/pools/routes", {"guids": ["u5"], "to": "slot", "slot": "nope"})[0] == 400
    assert api("POST", "/api/pools/slots/female_human/rename", {"name": "Women"})[1]["name"] == "Women"
    assert api("POST", "/api/pools/slots/female_human/merge", {"into": "male_human"})[1]["changed"] >= 3
    st, sample = api("GET", "/api/pools/spot-check/male_human?seed=3")
    assert st == 200 and sample["items"]
    guid = sample["items"][0]["guid"]
    assert api("POST", "/api/pools/spot-check/male_human", {"results": {guid: True}})[1] == {"checked": 1, "wrong": 0}
    assert api("GET", "/api/pools/spot-check/nope")[0] == 404


def test_slot_voice_is_reachable_through_the_speaker_routes(api):
    api("POST", "/api/pools/rebuild", {"min_slot_lines": 3})
    st, d = api("GET", "/api/speakers/pool_male_human")
    assert st == 200 and d["design"]["candidates"] == [] and d["summary"]["origin"] == "designed"
    lines = api("GET", "/api/speakers/pool_male_human/lines")[1]
    assert lines == []       # until plan.py reroutes the lines to pool_male_human, the speaker has no lines of its own


def test_undo_unmerge_new_slot_and_filters_over_http(api):
    api("POST", "/api/pools/rebuild", {"min_slot_lines": 3})
    st, res = api("POST", "/api/pools/routes", {"guids": ["u5"], "to": "narrator"})
    assert st == 200 and res["undo"]["previous"]["u5"]["to"] == "slot"
    assert api("GET", "/api/pools")[1]["overrides"] == 1
    assert api("POST", "/api/pools/routes/restore", {"previous": res["undo"]["previous"]}) == (200, {"changed": 1})
    assert api("POST", "/api/pools/routes/restore", {"previous": {}})[0] == 400
    st, slot = api("POST", "/api/pools/slots", {"name": "Herald", "gender": "female"})
    assert st == 200 and slot["id"] == "custom_herald"
    assert api("POST", "/api/pools/slots", {"name": "Herald", "gender": "female"})[0] == 409
    assert api("POST", "/api/pools/slots/female_human/merge", {"into": "male_human"})[1]["changed"] == 3
    st, back = api("POST", "/api/pools/slots/female_human/unmerge")
    assert st == 200 and back["changed"] == 3
    assert api("POST", "/api/pools/slots/female_human/unmerge")[0] == 404
    page = api("GET", "/api/pools/routes?q=heinrix&bank=1&conf_lt=2&entry_name=hein")[1]
    assert page["total"] == 2 and "wav" in page["items"][0] and page["items"][0]["entry_name"] == "Heinrix"
    assert api("GET", "/api/pools/routes?conf_lt=x")[0] == 400
