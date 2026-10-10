"""Core API: summary, enriched speaker list, pick/rank/accent_score, durations, and the job queue."""
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from studio_server import design, jobs, speakers, summary
from studio_server.app import make_server
from studio_server.errors import ApiError
from studio_server.jsonio import read_json
from studio_server.model import ModelClient
from conftest import make_pool_repo, put, write_wav
from mock_backend import MockBackend


def by_name(cfg):
    return {s["name"]: s for s in speakers.list_speakers(cfg)}


# ---- speakers list fields ---------------------------------------------------------------------------------------
def test_list_designed_fields_follow_audit(cfg):
    m = by_name(cfg)["Muaran"]
    assert (m["kind"], m["pick"], m["ranked"], m["candidates"], m["registered"]) == ("named", None, 0, 2, False)
    assert m["sample"] == "data/voice_design/clips/muaran/c0.wav"
    put(cfg.voice_design / "audit.json", {"Muaran": {"cands": {"c0.wav": {"fit": 4}, "c1.wav": {"accent": "x"}},
                                                     "pick": "c1.wav", "order": ["c0.wav", "c1.wav"]}})
    m = by_name(cfg)["Muaran"]
    assert m["pick"] == "c1.wav" and m["has_pick"] is True and m["ranked"] == 1
    assert m["sample"] == "data/voice_design/clips/muaran/c1.wav"


def test_sample_without_pick_is_rank_one(cfg):
    put(cfg.voice_design / "audit.json", {"Muaran": {"cands": {}, "order": ["c1.wav", "c0.wav"], "pick": None}})
    assert by_name(cfg)["Muaran"]["sample"].endswith("/c1.wav")


def test_registered_and_slot_kind(cfg):
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    design.register_pick(cfg, "muaran")
    assert by_name(cfg)["Muaran"]["registered"] is True
    man = read_json(cfg.voice_design / "design_manifest.json", {})
    man["pool_x"] = {**man["Muaran"], "slug": "pool_x", "role": "pool slot"}
    man["pool_y"] = {**man["Muaran"], "slug": "pool_y", "role": "officer"}
    put(cfg.voice_design / "design_manifest.json", man)
    s = by_name(cfg)
    assert s["pool_x"]["kind"] == "slot" and s["pool_y"]["kind"] == "slot" and s["Muaran"]["kind"] == "named"


def test_real_speaker_fields(cfg):
    p = by_name(cfg)["Pasqal"]
    assert (p["kind"], p["pick"], p["ranked"], p["candidates"], p["registered"]) == ("real", None, 0, 0, False)
    assert p["sample"] == "data/voices/wav/Pasqal/E1.wav"          # rank-1 curated clip, as the clip list resolves it


# ---- pick independent of rank, accent_score ---------------------------------------------------------------------
def audit(cfg):
    return read_json(cfg.voice_design / "audit.json", {})["Muaran"]


def test_reorder_keeps_the_pick(cfg):
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    design.post_order(cfg, "muaran", ["c1.wav", "c0.wav"])
    assert audit(cfg)["pick"] == "c0.wav" and audit(cfg)["order"] == ["c1.wav", "c0.wav"]
    design.post_order(cfg, "muaran", ["c1.wav"])                    # the pick may be unranked
    assert audit(cfg)["pick"] == "c0.wav"


def test_reorder_with_no_pick_stays_unpicked(cfg):
    design.post_order(cfg, "muaran", ["c1.wav", "c0.wav"])
    assert audit(cfg)["pick"] is None


def test_accent_score_saved_validated_and_cleared(cfg):
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "accent_score": 4})
    assert audit(cfg)["cands"]["c0.wav"] == {"accent_score": 4}
    d = speakers.speaker_detail(cfg, "muaran")["design"]
    assert next(c for c in d["candidates"] if c["id"] == "c0.wav")["verdict"]["accent_score"] == 4
    for bad in (0, 6, "3", 2.5, True):
        with pytest.raises(ApiError) as e:
            design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "accent_score": bad})
        assert e.value.status == 400
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "accent_score": None, "fit": 3})
    assert audit(cfg)["cands"]["c0.wav"] == {"fit": 3}


# ---- durations --------------------------------------------------------------------------------------------------
def test_line_dur_from_wav_header(cfg):
    write_wav(cfg.render / "export/wav/g1.wav", seconds=1.5)
    lines = {l["guid"]: l for l in speakers.speaker_lines(cfg, "Pasqal")}
    assert lines["g1"]["dur"] == 1.5 and lines["g2"]["dur"] is None


def test_fx_records_duration(cfg):
    from studio_server import fx, store
    py = cfg.root / "tools/fx_lab/.venv-fx/bin/python"
    py.parent.mkdir(parents=True)
    py.write_text('#!/bin/sh\ncp "$3" "$5"\n')           # stands in for fx_apply.py: --in $3 --out $5
    py.chmod(0o755)
    write_wav(cfg.studio / "pasqal/raw/t1.wav", seconds=0.5)
    store.add_take(cfg, "pasqal", {"id": "t1", "raw": "data/studio/pasqal/raw/t1.wav", "fx": None})
    t = fx.apply_to_take(cfg, "pasqal", "t1", ["Clean"])
    assert t["fx"]["dur"] == 0.5 and t["fx"]["presets"] == ["Clean"]


# ---- summary ----------------------------------------------------------------------------------------------------
def test_summary_minimal_repo(cfg):
    s = summary.summary(cfg, ModelClient("http://127.0.0.1:9"))
    assert s["speakers_left"] == 1
    assert s["speakers"] == {"total": 2, "needs_voice": 1, "picked": 0, "registered": 0}
    assert s["pools"] is None and s["matches"] is None
    assert s["model"] == {"state": "down"}
    assert s["qa_clips"] is None or set(s["qa_clips"]) >= {"total", "unjudged", "good", "bad"}


def test_summary_counts_picks_registered_and_qa(cfg):
    put(cfg.render / "export/index.json", {"g1": {"wav": "wav/g1.wav", "text": "Greetings, Rogue Trader.", "speaker": "Pasqal", "engine": "vox"}})
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    s = summary.summary(cfg, ModelClient("http://127.0.0.1:9"))
    assert s["speakers_left"] == 0 and s["speakers"]["picked"] == 1
    design.register_pick(cfg, "muaran")
    assert summary.summary(cfg, ModelClient("http://127.0.0.1:9"))["speakers"]["registered"] == 1
    q = s["qa_clips"]
    assert q["total"] == 1 and q["unjudged"] == 1 and q["good"] == 0


def test_summary_pools_and_matches(pcfg):
    from studio_server import pools
    pools.rebuild(pcfg, None, None)
    s = summary.summary(pcfg, ModelClient("http://127.0.0.1:9"))
    assert s["pools"]["total"] > 0 and "queue_entries" in s["pools"] and "built" in s["pools"]
    m = s["matches"]
    assert m["total"] >= 1 and m["reviewed"] == 0 and m["total"] >= m["flagged"] >= m["flagged_unreviewed"]


# ---- jobs -------------------------------------------------------------------------------------------------------
class FakeModel:
    """call() blocks on `gate` when set; writes a short wav like the real backend."""

    def __init__(self, cfg, gate=None, fail_with=None):
        self.cfg, self.gate, self.fail_with, self.n, self.bodies = cfg, gate, fail_with, 0, []
        self.entered = threading.Event()

    def health(self):
        return "ready"

    def call(self, path, body):
        self.bodies.append(body)
        self.entered.set()
        if self.gate is not None:
            self.gate.wait(10)
        if self.fail_with:
            raise self.fail_with
        self.n += 1
        write_wav(self.cfg.voice_design / f"live_tmp/f{self.n}.wav")
        return {"file": f"live_tmp/f{self.n}.wav", "seed": int(body["seed"]), "cfg": body.get("cfg", 2.0),
                "timesteps": body.get("timesteps", 10), "seconds": 0.5, "audio_s": 0.1}


def wait_for(fn, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.02)
    raise AssertionError("timed out")


CLONE_ITEM = {"guid": "g1", "text": "Hi.", "reference": {"wav": "data/voices/wav/Pasqal/E1.wav", "text": "Hello."},
              "options": {"cfg": 2.0, "timesteps": 10, "seed": ""}}


def clone_job(n=2, **extra):
    return {"kind": "clone", "slug": "pasqal", "items": [dict(CLONE_ITEM, text=f"Line {i}.") for i in range(n)], **extra}


def test_submit_draws_seeds_before_the_model_runs(cfg):
    gate = threading.Event()
    model = FakeModel(cfg, gate)
    q = jobs.JobQueue(cfg, model)
    j = q.submit(clone_job(2))
    assert j["state"] in ("queued", "running") and j["total"] == 2
    seeds = [i["seed"] for i in j["items"]]
    assert all(isinstance(s, int) and 0 <= s < 2 ** 31 for s in seeds)
    model.entered.wait(5)
    live = q.get(j["id"])
    assert live["state"] == "running" and live["index"] == 1 and live["current"]["seed"] == seeds[0]
    assert live["current"]["text"] == "Line 0." and live["current"]["elapsed_s"] >= 0
    gate.set()
    done = wait_for(lambda: q.get(j["id"])["state"] == "done" and q.get(j["id"]))
    assert model.bodies[0]["seed"] == seeds[0] and model.bodies[1]["seed"] == seeds[1]
    assert done["done"] == 2 and len(done["takes"]) == 2 and done["items"][0]["result"]["seed"] == seeds[0]
    assert all("body" not in i for i in done["items"])
    assert [t["id"] for t in speakers_takes(cfg)] == sorted(done["takes"], reverse=True)


def speakers_takes(cfg):
    from studio_server import store
    return sorted(store.read_takes(cfg, "pasqal").values(), key=lambda t: t["id"], reverse=True)


def test_a_typed_seed_is_kept(cfg):
    q = jobs.JobQueue(cfg, FakeModel(cfg))
    body = clone_job(1)
    body["items"][0]["options"]["seed"] = "123"
    assert q.submit(body)["items"][0]["seed"] == 123


def test_design_job_returns_live_results(cfg):
    model = FakeModel(cfg)
    q = jobs.JobQueue(cfg, model)
    j = q.submit({"kind": "design", "slug": "muaran", "items": [{}, {"seed": 5}]})
    done = wait_for(lambda: q.get(j["id"])["state"] == "done" and q.get(j["id"]))
    assert done["items"][1]["seed"] == 5 and done["items"][0]["result"]["file"].startswith("live_tmp/")
    assert done["items"][0]["result"]["description"] == "A calm woman." and done["takes"] == []


def test_submit_validation(cfg):
    q = jobs.JobQueue(cfg, FakeModel(cfg))
    bad = [dict(clone_job(1), kind="nope"), dict(clone_job(1), slug="nobody"), dict(clone_job(1), items=[]),
           dict(clone_job(1), slug="muaran", kind="design", fx=["Clean"]),
           {"kind": "design", "slug": "pasqal", "items": [{}]},
           dict(clone_job(1), fx="Clean")]
    codes = []
    for b in bad:
        with pytest.raises(ApiError) as e:
            q.submit(b)
        codes.append(e.value.status)
    assert codes == [400, 404, 400, 400, 404, 400]
    for patch in ({"text": ""}, {"reference": {"wav": "../x.wav"}}, {"options": {"seed": "abc"}}, {"options": {"cfg": 0}}):
        b = clone_job(1)
        b["items"][0].update(patch)
        with pytest.raises(ApiError) as e:
            q.submit(b)
        assert e.value.status == 400
    assert q.list() == []


def test_cancel_running_job_drops_the_in_flight_take_and_cancels_the_rest(cfg):
    gate = threading.Event()
    model = FakeModel(cfg, gate)
    q = jobs.JobQueue(cfg, model)
    j = q.submit(clone_job(3))
    model.entered.wait(5)
    c = q.cancel(j["id"])
    assert c["cancel_requested"] is True and [i["state"] for i in c["items"]] == ["running", "cancelled", "cancelled"]
    gate.set()
    done = wait_for(lambda: q.get(j["id"])["state"] == "cancelled" and q.get(j["id"]))
    assert done["takes"] == [] and speakers_takes(cfg) == [] and done["items"][0]["state"] == "cancelled"
    assert len(model.bodies) == 1
    with pytest.raises(ApiError) as e:
        q.cancel(j["id"])
    assert e.value.status == 409


def test_cancel_a_queued_job_and_queue_order(cfg):
    gate = threading.Event()
    model = FakeModel(cfg, gate)
    q = jobs.JobQueue(cfg, model)
    first, second = q.submit(clone_job(1)), q.submit(clone_job(1))
    model.entered.wait(5)
    assert q.get(second["id"])["state"] == "queued"
    assert q.cancel(second["id"])["state"] == "cancelled"
    assert [j["id"] for j in q.list(active=True)] == [first["id"]]
    gate.set()
    wait_for(lambda: q.get(first["id"])["state"] == "done")
    assert len(model.bodies) == 1
    assert [j["id"] for j in q.list()] == [second["id"], first["id"]]       # newest first without active=1
    assert q.list(slug="muaran") == []
    with pytest.raises(ApiError) as e:
        q.cancel("nope")
    assert e.value.status == 404


def test_model_down_fails_the_job_and_skips_the_rest(cfg):
    model = FakeModel(cfg, fail_with=ApiError(503, "model backend is not running"))
    q = jobs.JobQueue(cfg, model)
    j = q.submit(clone_job(3))
    done = wait_for(lambda: q.get(j["id"])["state"] == "failed" and q.get(j["id"]))
    assert "not running" in done["error"] and len(model.bodies) == 1
    assert [i["state"] for i in done["items"]] == ["failed", "cancelled", "cancelled"]


def test_one_bad_item_does_not_stop_the_job(cfg):
    model = FakeModel(cfg, fail_with=ApiError(502, "boom"))
    q = jobs.JobQueue(cfg, model)
    j = q.submit(clone_job(2))
    done = wait_for(lambda: q.get(j["id"])["state"] == "failed" and q.get(j["id"]))      # all items failed
    assert [i["error"] for i in done["items"]] == ["boom", "boom"] and len(model.bodies) == 2
    model.fail_with = None
    ok = q.submit(clone_job(1))
    assert wait_for(lambda: q.get(ok["id"])["state"] == "done")


def test_history_survives_a_restart_and_unfinished_jobs_are_marked_failed(cfg):
    q = jobs.JobQueue(cfg, FakeModel(cfg))
    j = q.submit(clone_job(1))
    wait_for(lambda: q.get(j["id"])["state"] == "done")
    saved = read_json(cfg.studio / "_jobs.json", [])
    saved.append({**saved[0], "id": "jX", "state": "running", "items": [dict(saved[0]["items"][0], state="running")]})
    put(cfg.studio / "_jobs.json", saved)
    q2 = jobs.JobQueue(cfg, FakeModel(cfg))
    assert q2.get(j["id"])["state"] == "done"
    x = q2.get("jX")
    assert x["state"] == "failed" and "restarted" in x["error"] and x["items"][0]["state"] == "cancelled"


def test_fx_failure_keeps_the_take(cfg):
    q = jobs.JobQueue(cfg, FakeModel(cfg))
    j = q.submit(clone_job(1, fx=["Clean"]))                 # no .venv-fx in the fixture repo
    done = wait_for(lambda: q.get(j["id"])["state"] == "done" and q.get(j["id"]))
    assert done["items"][0]["fx_error"] and len(done["takes"]) == 1


# ---- over HTTP --------------------------------------------------------------------------------------------------
@pytest.fixture
def http(cfg, tmp_path):
    gate = threading.Event()
    model = FakeModel(cfg, gate)
    srv = make_server(cfg, model, port=0, web_dist=tmp_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, path, body=None):
        req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    yield call, model, gate
    gate.set()
    srv.shutdown()
    srv.server_close()


def test_jobs_over_http_and_health_job_entry(http):
    call, model, gate = http
    assert call("GET", "/api/model/health") == (200, {"state": "ready"})
    st, j = call("POST", "/api/speakers/pasqal/clone/jobs", {"items": clone_job(2)["items"], "label": "Test run"})
    assert st == 200 and j["kind"] == "clone" and j["slug"] == "pasqal" and j["items"][0]["seed"] is not None
    model.entered.wait(5)
    st, h = call("GET", "/api/model/health")
    assert h["state"] == "busy" and h["job"]["label"] == "Test run"
    assert (h["job"]["index"], h["job"]["total"], h["job"]["done"]) == (1, 2, 0) and h["job"]["elapsed_s"] >= 0
    assert [x["id"] for x in call("GET", "/api/jobs?active=1")[1]] == [j["id"]]
    assert call("GET", "/api/jobs?active=1&slug=muaran")[1] == []
    assert call("POST", f"/api/jobs/{j['id']}/cancel")[1]["cancel_requested"] is True
    gate.set()
    wait_for(lambda: call("GET", f"/api/jobs/{j['id']}")[1]["state"] == "cancelled")
    assert call("GET", "/api/model/health") == (200, {"state": "ready"})
    assert call("GET", "/api/jobs/nope")[0] == 404 and call("POST", "/api/jobs/nope/cancel")[0] == 404
    assert call("POST", "/api/jobs", {"kind": "x"})[0] == 400


def test_design_jobs_route_and_summary_over_http(http):
    call, model, gate = http
    gate.set()
    st, j = call("POST", "/api/speakers/muaran/design/jobs", {"items": [{"seed": 3}]})
    assert st == 200 and j["kind"] == "design"
    wait_for(lambda: call("GET", f"/api/jobs/{j['id']}")[1]["state"] == "done")
    st, s = call("GET", "/api/summary")
    assert st == 200 and s["speakers_left"] == 1 and s["model"]["state"] == "ready"


def test_sync_routes_still_work_beside_jobs(cfg, tmp_path):
    mb = MockBackend(cfg.voice_design)
    srv = make_server(cfg, ModelClient(mb.url), port=0, web_dist=tmp_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/api/speakers/muaran/design/generate",
                                     method="POST", data=b'{"seed": "7"}')
        assert json.loads(urllib.request.urlopen(req).read())["seed"] == 7
    finally:
        srv.shutdown()
        srv.server_close()
        mb.close()
