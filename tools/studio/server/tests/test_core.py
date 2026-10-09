import pytest

from studio_server.config import Config
from studio_server.errors import ApiError
from studio_server.jsonio import read_json, write_json_atomic
from studio_server.router import Router


def test_resolve_file_allows_whitelisted_roots(cfg):
    assert cfg.resolve_file("data/voices/wav/Pasqal/E1.wav") is not None
    assert cfg.resolve_file("data/render/export/wav/g1.wav") is not None


@pytest.mark.parametrize("bad", ["../etc/passwd", "data/voices/../../secret.txt", "/etc/passwd",
                                 "data/strings.enGB.json", "data/voices/wav/Pasqal/missing.wav", "data/voices"])
def test_resolve_file_rejects_escape_missing_and_other_roots(cfg, bad):
    assert cfg.resolve_file(bad) is None


def test_under_data_accepts_any_data_file_but_not_outside(cfg):
    assert cfg.under_data("data/voices/wav/Pasqal/E1.wav") is not None
    assert cfg.under_data("tools/x.py") is None
    assert cfg.under_data("data/../tools/x.py") is None


def test_read_json_default_and_corrupt(tmp_path):
    assert read_json(tmp_path / "none.json", {"a": 1}) == {"a": 1}
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(ApiError) as e:
        read_json(bad, {})
    assert e.value.status == 500 and "bad.json" in e.value.message


def test_write_json_atomic_roundtrip(tmp_path):
    p = tmp_path / "sub" / "x.json"
    write_json_atomic(p, {"é": 1})
    assert read_json(p, None) == {"é": 1}
    assert not list(p.parent.glob("*.tmp"))


def test_router_matches_params_methods_and_errors(cfg):
    r = Router()
    r.add("GET", "/api/a/{slug}", lambda req: {"slug": req.params["slug"], "q": req.query.get("x")})
    r.add("POST", "/api/a/{slug}", lambda req: (201, req.body))
    r.add("GET", "/api/boom", lambda req: (_ for _ in ()).throw(ApiError(418, "teapot")))
    r.add("POST", "/api/crash", lambda req: req.body["missing"])
    assert r.dispatch("GET", "/api/a/pasqal", {"x": "1"}, {}, cfg, None) == (200, {"slug": "pasqal", "q": "1"})
    assert r.dispatch("POST", "/api/a/p", {}, {"k": 1}, cfg, None) == (201, {"k": 1})
    assert r.dispatch("GET", "/api/boom", {}, {}, cfg, None) == (418, {"error": "teapot"})
    status, body = r.dispatch("POST", "/api/crash", {}, {}, cfg, None)
    assert status == 500 and "KeyError" in body["error"]
    assert r.dispatch("GET", "/api/nope", {}, {}, cfg, None)[0] == 404
    assert r.dispatch("DELETE", "/api/a/p", {}, {}, cfg, None)[0] == 404


def test_resolve_file_handles_nul_bytes_and_odd_input(cfg):
    assert cfg.resolve_file("data/voices/wav/Pasqal/E1.wav\x00.png") is None
