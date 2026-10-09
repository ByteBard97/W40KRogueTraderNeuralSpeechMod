import pytest

from studio_server import store
from studio_server.errors import ApiError
from conftest import write_wav


def body(**kw):
    return {"source": {"wav": "data/voices/wav/Pasqal/E1.wav", "text": "Hello.", "origin": "real"}, **kw}


def test_save_profile_fills_defaults_and_drops_unknown_options(cfg):
    p = store.save_profile(cfg, "pasqal", body(options={"cfg": 3.0, "bogus": 1}, fx=["Clean"], test_lines=["g1"]))
    assert p["options"]["cfg"] == 3.0 and p["options"]["timesteps"] == 10 and "bogus" not in p["options"]
    assert p["name"] == "Pasqal" and p["slug"] == "pasqal" and p["fx"] == ["Clean"] and p["test_lines"] == ["g1"]
    assert store.get_profile(cfg, "pasqal") == p


@pytest.mark.parametrize("wav", ["data/voices/wav/Pasqal/missing.wav", "../x.wav", "tools/fx_lab/scenarios.json", ""])
def test_save_profile_rejects_bad_source_paths(cfg, wav):
    with pytest.raises(ApiError) as e:
        store.save_profile(cfg, "pasqal", {"source": {"wav": wav, "text": "t", "origin": "real"}})
    assert e.value.status == 400


def test_save_profile_rejects_unknown_origin_and_speaker(cfg):
    with pytest.raises(ApiError) as e:
        store.save_profile(cfg, "pasqal", {"source": {"wav": "data/voices/wav/Pasqal/E1.wav", "text": "", "origin": "x"}})
    assert e.value.status == 400
    with pytest.raises(ApiError) as e2:
        store.save_profile(cfg, "nobody", body())
    assert e2.value.status == 404


def test_set_active_copies_profile_and_requires_one(cfg):
    with pytest.raises(ApiError) as e:
        store.set_active(cfg, "pasqal")
    assert e.value.status == 404
    store.save_profile(cfg, "pasqal", body())
    assert store.set_active(cfg, "pasqal") == {"active": "data/studio/pasqal/active.json"}
    assert (cfg.studio / "pasqal/active.json").read_text(encoding="utf-8") == (cfg.studio / "pasqal/profile.json").read_text(encoding="utf-8")


def test_takes_add_update_and_unknown_id(cfg):
    t = store.add_take(cfg, "pasqal", {"id": "t1", "raw": "x", "rating": 0, "note": "", "fx": None})
    assert store.read_takes(cfg, "pasqal") == {"t1": t}
    assert store.update_take(cfg, "pasqal", "t1", rating=4)["rating"] == 4
    with pytest.raises(ApiError) as e:
        store.update_take(cfg, "pasqal", "nope", rating=1)
    assert e.value.status == 404


def test_corrupt_takes_file_is_reported_and_not_overwritten(cfg):
    p = cfg.studio / "pasqal/takes.json"
    p.parent.mkdir(parents=True)
    p.write_text("{broken", encoding="utf-8")
    with pytest.raises(ApiError) as e:
        store.add_take(cfg, "pasqal", {"id": "t1"})
    assert e.value.status == 500
    assert p.read_text(encoding="utf-8") == "{broken"


def test_concurrent_take_writes_do_not_lose_updates(cfg):
    import threading
    threads = [threading.Thread(target=store.add_take, args=(cfg, "pasqal", {"id": f"t{i}", "rating": 0})) for i in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(store.read_takes(cfg, "pasqal")) == 30


def test_new_take_id_is_unique_and_ordered():
    a, b = store.new_take_id(), store.new_take_id()
    assert a != b and a.startswith("t") and int(b[1:]) > int(a[1:])


def test_concurrent_profile_saves_and_take_ids_do_not_collide(cfg):
    import threading
    errs = []
    def save():
        try:
            store.save_profile(cfg, "pasqal", body())
        except Exception as e:  # noqa: BLE001
            errs.append(e)
    ts = [threading.Thread(target=save) for _ in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert errs == []
    ids = []
    ts = [threading.Thread(target=lambda: ids.append(store.new_take_id())) for _ in range(200)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(set(ids)) == 200
