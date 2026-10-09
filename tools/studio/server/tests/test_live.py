import pytest

from studio_server import clone, design, fx, store
from studio_server.errors import ApiError
from studio_server.model import ModelClient
from mock_backend import MockBackend


@pytest.fixture
def mb(cfg):
    m = MockBackend(cfg.voice_design)
    yield m
    m.close()


def test_design_generate_uses_manifest_text_and_passes_seed(cfg, mb):
    r = design.generate(cfg, ModelClient(mb.url), "muaran", {"seed": "4242", "cfg": 2.5, "timesteps": 12})
    assert r["seed"] == 4242 and r["file"].startswith("live_tmp/") and r["text"] == "The augurs report nothing unusual."
    assert mb.calls[0]["description"] == "A calm woman." and mb.calls[0]["timesteps"] == 12


def test_design_generate_uses_given_description(cfg, mb):
    design.generate(cfg, ModelClient(mb.url), "muaran", {"description": "A gruff man."})
    assert mb.calls[0]["description"] == "A gruff man."


def clone_body(**kw):
    return {"guid": "g1", "text": "Greetings.", "instruct": "formal",
            "reference": {"wav": "data/voices/wav/Pasqal/E1.wav", "text": "Hello."},
            "options": {"cfg": 3.0, "timesteps": 10, "seed": "55", "use_instruct": True, "retry_badcase": False,
                        "normalize": False, "continuation": False}, **kw}


def test_clone_generate_records_take_and_sends_expected_fields(cfg, mb):
    t = clone.generate(cfg, ModelClient(mb.url), "pasqal", clone_body())
    sent = mb.calls[0]
    assert sent["reference_wav"] == "data/voices/wav/Pasqal/E1.wav" and sent["instruct"] == "formal"
    assert "prompt_text" not in sent and sent["seed"] == "55"
    assert t["raw"].startswith("data/studio/pasqal/raw/") and (cfg.root / t["raw"]).is_file() and t["seed"] == 55 and t["rating"] == 0 and t["fx"] is None
    assert store.read_takes(cfg, "pasqal")[t["id"]] == t


def test_clone_continuation_sends_prompt_text_and_instruct_is_optional(cfg, mb):
    b = clone_body()
    b["options"].update(continuation=True, use_instruct=False)
    clone.generate(cfg, ModelClient(mb.url), "pasqal", b)
    assert mb.calls[0]["prompt_text"] == "Hello." and "instruct" not in mb.calls[0]


@pytest.mark.parametrize("ref", ["data/voices/wav/Pasqal/missing.wav", "../x.wav", "tools/fx_lab/scenarios.json"])
def test_clone_rejects_bad_reference_before_calling_backend(cfg, mb, ref):
    b = clone_body()
    b["reference"]["wav"] = ref
    with pytest.raises(ApiError) as e:
        clone.generate(cfg, ModelClient(mb.url), "pasqal", b)
    assert e.value.status == 400 and mb.calls == []


def test_clone_backend_failure_leaves_no_take(cfg):
    mb = MockBackend(cfg.voice_design, fail=True)
    try:
        with pytest.raises(ApiError) as e:
            clone.generate(cfg, ModelClient(mb.url), "pasqal", clone_body())
        assert e.value.status == 502 and store.read_takes(cfg, "pasqal") == {}
    finally:
        mb.close()


def test_rate_take_validates_range(cfg, mb):
    t = clone.generate(cfg, ModelClient(mb.url), "pasqal", clone_body())
    assert clone.rate_take(cfg, "pasqal", t["id"], {"rating": 5, "note": "best"})["rating"] == 5
    with pytest.raises(ApiError) as e:
        clone.rate_take(cfg, "pasqal", t["id"], {"rating": 9})
    assert e.value.status == 400


def test_fx_list_presets_merges_scenarios_and_saved(cfg):
    from conftest import put
    put(cfg.data / "fx_lab/presets.json", {"Mine": {"params": {}}})
    assert fx.list_presets(cfg) == ["Clean", "Mine"]


def test_fx_apply_with_no_presets_clears_fx_and_missing_env_is_reported(cfg, mb):
    t = clone.generate(cfg, ModelClient(mb.url), "pasqal", clone_body())
    assert fx.apply_to_take(cfg, "pasqal", t["id"], [])["fx"] is None
    with pytest.raises(ApiError) as e:        # the fake repo has no tools/fx_lab/.venv-fx
        fx.apply_to_take(cfg, "pasqal", t["id"], ["Clean"])
    assert e.value.status == 500 and ".venv-fx" in e.value.message


@pytest.mark.parametrize("opt", [{"seed": "abc"}, {"seed": "-5"}, {"cfg": ""}, {"timesteps": ""}, {"cfg": "x"}, {"timesteps": 0}])
def test_clone_rejects_bad_option_values_before_calling_the_backend(cfg, mb, opt):
    b = clone_body()
    b["options"].update(opt)
    with pytest.raises(ApiError) as e:
        clone.generate(cfg, ModelClient(mb.url), "pasqal", b)
    assert e.value.status == 400 and mb.calls == []


def test_clone_with_a_corrupt_takes_file_fails_before_the_model_runs(cfg, mb):
    p = cfg.studio / "pasqal/takes.json"
    p.parent.mkdir(parents=True)
    p.write_text("{broken", encoding="utf-8")
    with pytest.raises(ApiError) as e:
        clone.generate(cfg, ModelClient(mb.url), "pasqal", clone_body())
    assert e.value.status == 500 and mb.calls == []
