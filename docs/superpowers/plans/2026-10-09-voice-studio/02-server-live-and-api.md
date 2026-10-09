# Voice Studio first slice, part 2 of 7: Server live calls and HTTP app

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Overview and table of contents:** [Voice Studio first slice](../2026-10-09-voice-studio-first-slice.md). Read it first: it holds the goal, architecture, file structure and review focus for the whole slice.
**Spec:** [`docs/superpowers/specs/2026-10-09-voice-studio-design.md`](../../specs/2026-10-09-voice-studio-design.md)
**This part:** Tasks 4 to 6. Python API: designed-voice state, model client, live generation, FX, routes and the HTTP app.
**Previous part:** [Server foundation](01-server-foundation.md). **Next part:** [Web foundation](03-web-foundation.md).

## Global Constraints

- Local only: the server binds `127.0.0.1`; audio is extracted from the user's game files and is never published.
- File serving: resolve the path, require it to sit under one of `data/voices`, `data/render`, `data/studio`, `data/voice_design`, and to be a file; otherwise 404.
- Nothing in the app or the tests deletes files. Tests write only under pytest `tmp_path`; manual checks must not touch real audit/manifest data (back up and compare before/after).
- Do not run the real model or any GPU job in this plan's automated steps; use the mock backend. The real-model check is a manual step for when the user says the GPU is free.
- Do not `git commit` or `git push` unless the repo owner says so. Steps named "Checkpoint" run `git status` and stop. If the owner asks for commits: plain human messages, no AI/Claude attribution of any kind.
- Reuse existing JSON schemas as-is: `audit.json`, `design_manifest.json`, `overrides.json`, `scores.json`, `prompts.json`, `catalog.json`, `jobs.jsonl`, `export/index.json`, FX `scenarios.json` and `presets.json`.
- No magic numbers in frontend code; files under 500 lines; `<script setup lang="ts">`, order script / template / `<style scoped>`.
- Model backend states shown to the user: `down`, `ready`, `busy`. (Spec deviation: "loading" is shown as `down` because the backend only starts listening after the model is loaded.)
- API framework: stdlib `http.server` (spec open question resolved: FastAPI is not installed cleanly here and the existing tools are stdlib).

---

### Task 4: Designed-voice state: verdict, order, description, keep

**Files:**
- Create: `tools/studio/server/studio_server/design.py`, `tools/studio/server/tests/test_design.py`

**Interfaces:**
- Consumes: `find_speaker`, `Config`, `read_json`/`write_json_atomic`; pure helpers `apply_verdict(audit, body)`, `apply_order(audit, body)`, `keep_candidate(manifest, name, tmp, rec, vd)` imported from `tools/voice_design/audit_server.py` (they already exist and are tested there).
- Produces: `design_name(cfg, slug) -> str` (404 unless the speaker is `designed`); `post_verdict(cfg, slug, body) -> {}` (body `{cand, accent?, fit?, reject?, pick?}`); `post_order(cfg, slug, order: list[str]) -> {}`; `post_description(cfg, slug, description: str) -> {}`; `keep(cfg, slug, body) -> {"cand": "cN.wav"}` (body `{file, seed, cfg, timesteps, description, text}`, where `file` is `live_tmp/<name>.wav` relative to `data/voice_design`); `register_pick(cfg, slug) -> {"registered": [name]}` (copies the speaker's picked candidate into the prompt bank through `tools/voice_design/register.py`, the only path from an audition verdict into `plan.py`; 400 if there is no pick). Every read-modify-write here runs under `STATE_LOCK`.

- [ ] **Step 1: Write the failing tests**

`tests/test_design.py`:

```python
import pytest

from studio_server import design
from studio_server.errors import ApiError
from studio_server.jsonio import read_json
from conftest import write_wav


def test_verdict_pick_and_toggle(cfg):
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "accent": "british", "fit": 4})
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    a = read_json(cfg.voice_design / "audit.json", {})["Muaran"]
    assert a["cands"]["c0.wav"] == {"accent": "british", "fit": 4} and a["pick"] == "c0.wav"
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": False})
    assert read_json(cfg.voice_design / "audit.json", {})["Muaran"]["pick"] is None


def test_order_sets_rank_one_as_pick(cfg):
    design.post_order(cfg, "muaran", ["c1.wav", "c0.wav"])
    a = read_json(cfg.voice_design / "audit.json", {})["Muaran"]
    assert a["order"] == ["c1.wav", "c0.wav"] and a["pick"] == "c1.wav"


def test_order_rejects_unknown_candidate(cfg):
    with pytest.raises(ApiError) as e:
        design.post_order(cfg, "muaran", ["c9.wav"])
    assert e.value.status == 400


def test_description_saved_as_override(cfg):
    design.post_description(cfg, "muaran", "A stern woman.")
    assert read_json(cfg.voice_design / "overrides.json", {}) == {"Muaran": "A stern woman."}


def test_register_copies_the_pick_into_the_prompt_bank_and_leaves_others(cfg):
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    assert design.register_pick(cfg, "muaran") == {"registered": ["Muaran"]}
    assert (cfg.voices / "prompts/designed/muaran.wav").is_file()
    prompts = read_json(cfg.voices / "prompts/prompts.json", {})
    assert prompts["Muaran"][0]["event"] == "designed_muaran" and "Pasqal" in prompts


def test_register_without_a_pick_is_400_and_changes_nothing(cfg):
    before = (cfg.voices / "prompts/prompts.json").read_text(encoding="utf-8")
    with pytest.raises(ApiError) as e:
        design.register_pick(cfg, "muaran")
    assert e.value.status == 400
    assert (cfg.voices / "prompts/prompts.json").read_text(encoding="utf-8") == before


def test_keep_copies_take_to_next_candidate_and_records_gen(cfg):
    write_wav(cfg.voice_design / "live_tmp/t1.wav")
    r = design.keep(cfg, "muaran", {"file": "live_tmp/t1.wav", "seed": 7, "cfg": 2.0, "timesteps": 10,
                                    "description": "A calm woman.", "text": "The augurs…"})
    assert r == {"cand": "c2.wav"}
    assert (cfg.voice_design / "clips/muaran/c2.wav").is_file()
    m = read_json(cfg.voice_design / "design_manifest.json", {})["Muaran"]
    assert m["candidates"][-1] == "c2.wav" and m["gen"]["candidates"]["c2.wav"]["seed"] == 7


def test_keep_backfills_description_and_text_so_every_kept_candidate_is_regenerable(cfg):
    write_wav(cfg.voice_design / "live_tmp/t2.wav")
    design.keep(cfg, "muaran", {"file": "live_tmp/t2.wav", "seed": 9, "cfg": 2.0, "timesteps": 10})
    rec = read_json(cfg.voice_design / "design_manifest.json", {})["Muaran"]["gen"]["candidates"]["c2.wav"]
    assert rec["description"] == "A calm woman." and rec["text"] == "The augurs report nothing unusual."


def test_keep_rejects_a_take_with_no_seed(cfg):
    write_wav(cfg.voice_design / "live_tmp/t3.wav")
    with pytest.raises(ApiError) as e:
        design.keep(cfg, "muaran", {"file": "live_tmp/t3.wav"})
    assert e.value.status == 400


@pytest.mark.parametrize("bad", ["live_tmp/missing.wav", "../audit.json", "clips/muaran/c0.wav", "/etc/passwd"])
def test_keep_rejects_files_outside_live_tmp_or_missing(cfg, bad):
    with pytest.raises(ApiError) as e:
        design.keep(cfg, "muaran", {"file": bad, "seed": 1, "cfg": 2.0, "timesteps": 10})
    assert e.value.status == 400


def test_real_speaker_has_no_design(cfg):
    with pytest.raises(ApiError) as e:
        design.post_verdict(cfg, "pasqal", {"cand": "c0.wav"})
    assert e.value.status == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_design.py -q`
Expected: `ModuleNotFoundError: No module named 'studio_server.design'`.

- [ ] **Step 3: Implement**

`studio_server/design.py`:

```python
from __future__ import annotations

import sys

from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic
from .speakers import find_speaker

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[4] / "tools/voice_design"))
from audit_server import apply_order, apply_verdict, keep_candidate  # noqa: E402  (pure helpers, already tested)
from register import register as register_picks  # noqa: E402  (copies picks into the prompt bank, already tested)


def design_name(cfg: Config, slug: str) -> str:
    sp = find_speaker(cfg, slug)
    if sp["origin"] != "designed":
        raise ApiError(404, f"'{sp['name']}' has no designed voice")
    return sp["name"]


def _manifest(cfg: Config) -> dict:
    return read_json(cfg.voice_design / "design_manifest.json", {})


def post_verdict(cfg: Config, slug: str, body: dict) -> dict:
    name = design_name(cfg, slug)
    with STATE_LOCK:
        audit = read_json(cfg.voice_design / "audit.json", {})
        write_json_atomic(cfg.voice_design / "audit.json", apply_verdict(audit, {**body, "name": name}))
    return {}


def post_order(cfg: Config, slug: str, order: list[str]) -> dict:
    name = design_name(cfg, slug)
    known = set(_manifest(cfg)[name]["candidates"])
    if any(c not in known for c in order):
        raise ApiError(400, "order contains an unknown candidate")
    with STATE_LOCK:
        audit = read_json(cfg.voice_design / "audit.json", {})
        write_json_atomic(cfg.voice_design / "audit.json", apply_order(audit, {"name": name, "order": order}))
    return {}


def post_description(cfg: Config, slug: str, description: str) -> dict:
    name = design_name(cfg, slug)
    with STATE_LOCK:
        ov = read_json(cfg.voice_design / "overrides.json", {})
        ov[name] = description
        write_json_atomic(cfg.voice_design / "overrides.json", ov)
    return {}


def keep(cfg: Config, slug: str, body: dict) -> dict:
    name = design_name(cfg, slug)
    rel = body.get("file", "")
    tmp = (cfg.voice_design / rel).resolve() if rel and not rel.startswith("/") else None
    live = (cfg.voice_design / "live_tmp").resolve()
    if tmp is None or live not in tmp.parents or not tmp.is_file():
        raise ApiError(400, f"not a live take: {rel!r}")
    with STATE_LOCK:
        manifest = _manifest(cfg)
        # Every kept candidate must be regenerable, so description and text are always recorded: take them from the
        # request when sent, otherwise from the speaker's saved description and sample sentence.
        description = body.get("description") or read_json(cfg.voice_design / "overrides.json", {}).get(name, manifest[name]["description"])
        rec = {"description": description, "text": body.get("text") or manifest[name]["text"]}
        for k in ("seed", "cfg", "timesteps"):
            if k not in body:
                raise ApiError(400, f"keep needs '{k}' so the candidate can be regenerated")
            rec[k] = body[k]
        cand = keep_candidate(manifest, name, tmp, rec, vd=cfg.voice_design)
        write_json_atomic(cfg.voice_design / "design_manifest.json", manifest)
    return {"cand": cand}


def register_pick(cfg: Config, slug: str) -> dict:
    name = design_name(cfg, slug)
    with STATE_LOCK:
        audit = read_json(cfg.voice_design / "audit.json", {})
        if not (audit.get(name) or {}).get("pick"):
            raise ApiError(400, f"'{name}' has no pick yet; rank a candidate first")
        pj = cfg.voices / "prompts/prompts.json"
        prompts = read_json(pj, {})
        done = register_picks({name: audit[name]}, _manifest(cfg), prompts, vd_root=cfg.voice_design,
                              voices_root=cfg.voices)
        write_json_atomic(pj, prompts)
    return {"registered": done}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests -q`
Expected: all pass.

- [ ] **Step 5: Checkpoint** (`git status`; no commit unless asked)

---

### Task 5: Model client, live generation (design and clone), FX apply

**Files:**
- Modify: `tools/voice_design/live_backend.py` (`/health` reports `busy`)
- Create: `studio_server/model.py`, `studio_server/clone.py`, `studio_server/fx.py`, `studio_server/fx_apply.py`
- Modify: `studio_server/design.py` (add `generate`)
- Create: `tests/mock_backend.py`, `tests/test_model.py`, `tests/test_live.py`

**Interfaces:**
- Consumes: Tasks 1 to 4; backend routes `GET /health -> {"ok": bool, "busy": bool}` and `POST /generate` (design: `{description, text, seed, cfg, timesteps}`; clone: `{text, reference_wav, instruct?, seed, cfg, timesteps, retry_badcase, normalize, prompt_text?}`) returning `{file, seed, cfg, timesteps, seconds, audio_s}` where `file` is relative to `data/voice_design`.
- Produces:
  - `ModelClient(url, timeout=240)`; `.health() -> 'down'|'ready'|'busy'`; `.call(path, body) -> dict` (raises `ApiError(503, ...)` when unreachable, `ApiError(502, msg)` when the backend returns `error`).
  - `design.generate(cfg, model, slug, body) -> dict` (body `{description?, seed?, cfg?, timesteps?}`; returns the backend result plus `description`, `text`).
  - `clone.generate(cfg, model, slug, body) -> take dict` (body `{guid?, text, instruct?, reference: {wav, text}, options}`); saved via `store.add_take`.
  - `fx.list_presets(cfg) -> list[str]`; `fx.apply_to_take(cfg, slug, take_id, presets: list[str]) -> take dict`.
  - `rate(cfg, slug, take_id, body) -> take` lives in `clone.py`: `rate_take(cfg, slug, take_id, body)` (body keys `rating` 0 to 5 and/or `note`).

- [ ] **Step 1: Write the mock backend and failing tests**

`tests/mock_backend.py`:

```python
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from conftest import write_wav


class MockBackend:
    """Stands in for tools/voice_design/live_backend.py. Writes a short wav under <voice_design>/live_tmp."""

    def __init__(self, voice_design: Path, busy: bool = False, fail: bool = False):
        self.voice_design, self.busy, self.fail, self.calls = voice_design, busy, fail, []
        outer = self

        class H(BaseHTTPRequestHandler):
            def _send(self, obj, code=200):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                self._send({"ok": True, "busy": outer.busy})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.calls.append(body)
                if outer.fail:
                    return self._send({"error": "ValueError: boom"}, 500)
                n = len(outer.calls)
                write_wav(outer.voice_design / f"live_tmp/mock{n}.wav")
                self._send({"file": f"live_tmp/mock{n}.wav", "seed": int(body.get("seed") or 99),
                            "cfg": body.get("cfg", 2.0), "timesteps": body.get("timesteps", 10),
                            "seconds": 0.1, "audio_s": 0.1})

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
```

`tests/test_model.py`:

```python
import pytest

from studio_server.errors import ApiError
from studio_server.model import ModelClient
from mock_backend import MockBackend


def test_health_states(cfg):
    assert ModelClient("http://127.0.0.1:9").health() == "down"
    mb = MockBackend(cfg.voice_design)
    try:
        assert ModelClient(mb.url).health() == "ready"
        mb.busy = True
        assert ModelClient(mb.url).health() == "busy"
    finally:
        mb.close()


def test_call_unreachable_is_503_and_backend_error_is_502(cfg):
    with pytest.raises(ApiError) as e:
        ModelClient("http://127.0.0.1:9").call("/generate", {})
    assert e.value.status == 503 and "live_backend" in e.value.message
    mb = MockBackend(cfg.voice_design, fail=True)
    try:
        with pytest.raises(ApiError) as e2:
            ModelClient(mb.url).call("/generate", {})
        assert e2.value.status == 502 and "boom" in e2.value.message
    finally:
        mb.close()
```

`tests/test_live.py`:

```python
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
    assert t["raw"].startswith("data/voice_design/live_tmp/") and t["seed"] == 55 and t["rating"] == 0 and t["fx"] is None
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_model.py tests/test_live.py -q`
Expected: `ModuleNotFoundError: No module named 'studio_server.model'`.

- [ ] **Step 3: Implement**

Modify `tools/voice_design/live_backend.py`, the health branch of `do_GET`:

```python
    def do_GET(self):
        if self.path == "/health":
            self._send({"ok": STATE["model"] is not None, "busy": LOCK.locked()})
        else:
            self._send({}, 404)
```

`studio_server/model.py`:

```python
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .errors import ApiError

HEALTH_TIMEOUT_S = 3
CALL_TIMEOUT_S = 240
DOWN_MESSAGE = "model backend is not running (start tools/voice_design/live_backend.py when the GPU is free)"


class ModelClient:
    def __init__(self, url: str, timeout: int = CALL_TIMEOUT_S):
        self.url, self.timeout = url, timeout

    def health(self) -> str:
        try:
            with urllib.request.urlopen(self.url + "/health", timeout=HEALTH_TIMEOUT_S) as r:
                h = json.loads(r.read())
        except (OSError, ValueError):
            return "down"
        if not h.get("ok"):
            return "down"
        return "busy" if h.get("busy") else "ready"

    def call(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                out = json.loads(e.read() or b"{}")
            except ValueError:
                out = {}
            raise ApiError(502, out.get("error", f"backend HTTP {e.code}"))
        except OSError:
            raise ApiError(503, DOWN_MESSAGE)
        if "error" in out:
            raise ApiError(502, out["error"])
        return out
```

Append to `studio_server/design.py`:

```python
def generate(cfg: Config, model, slug: str, body: dict) -> dict:
    name = design_name(cfg, slug)
    m = _manifest(cfg)[name]
    description = body.get("description") or read_json(cfg.voice_design / "overrides.json", {}).get(name, m["description"])
    r = model.call("/generate", {"description": description, "text": m["text"], "seed": body.get("seed", ""),
                                 "cfg": body.get("cfg", 2.0), "timesteps": body.get("timesteps", 10)})
    return {**r, "description": description, "text": m["text"]}
```

`studio_server/clone.py`:

```python
from __future__ import annotations

from .config import Config
from .errors import ApiError
from .speakers import find_speaker
from .store import add_take, new_take_id, update_take

MAX_RATING = 5


def generate(cfg: Config, model, slug: str, body: dict) -> dict:
    find_speaker(cfg, slug)
    ref = body.get("reference") or {}
    if cfg.under_data(ref.get("wav", "")) is None:
        raise ApiError(400, f"reference is not a file under data/: {ref.get('wav')!r}")
    o = body["options"]
    req = {"text": body["text"], "reference_wav": ref["wav"], "seed": o.get("seed", ""), "cfg": o["cfg"],
           "timesteps": o["timesteps"], "retry_badcase": o["retry_badcase"], "normalize": o["normalize"]}
    if o.get("use_instruct") and body.get("instruct"):
        req["instruct"] = body["instruct"]
    if o.get("continuation"):
        req["prompt_text"] = ref.get("text", "")
    r = model.call("/generate", req)
    take = {"id": new_take_id(), "raw": f"data/voice_design/{r['file']}", "text": body["text"],
            "guid": body.get("guid"), "reference": ref["wav"], "options": o, "instruct": req.get("instruct"),
            "seed": r["seed"], "seconds": r["seconds"], "audio_s": r.get("audio_s"), "rating": 0, "note": "",
            "fx": None}
    return add_take(cfg, slug, take)


def rate_take(cfg: Config, slug: str, take_id: str, body: dict) -> dict:
    fields = {}
    if "rating" in body:
        if not isinstance(body["rating"], int) or not 0 <= body["rating"] <= MAX_RATING:
            raise ApiError(400, f"rating must be an integer 0 to {MAX_RATING}")
        fields["rating"] = body["rating"]
    if "note" in body:
        fields["note"] = str(body["note"])
    return update_take(cfg, slug, take_id, **fields)
```

`studio_server/fx_apply.py` (run under `tools/fx_lab/.venv-fx/bin/python`; it imports the FX Lab's `batch.py`):

```python
#!/usr/bin/env python3
"""Apply FX Lab presets to one wav, as tools/fx_lab/batch.py does for the bank.

  tools/fx_lab/.venv-fx/bin/python fx_apply.py --in raw.wav --out fx.wav --preset "Name" [--preset "Name2"]
Presets run in series, in order; output loudness matches the input.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import soundfile as sf

FXLAB = Path(__file__).resolve().parents[3] / "fx_lab"   # file is tools/studio/server/studio_server/fx_apply.py
sys.path.insert(0, str(FXLAB))
import batch  # noqa: E402


def apply(src: Path, dst: Path, names: list[str]) -> None:
    presets = batch.load_presets()
    missing = [n for n in names if n not in presets]
    if missing:
        raise SystemExit(f"unknown preset(s): {missing}")
    codes: dict[str, str] = {}
    steps = []
    for n in names:
        f = presets[n].get("dsp", "chain.dsp")
        codes.setdefault(f, (FXLAB / "faust" / f).read_text(encoding="utf-8"))
        steps.append({"dsp": f, "params": presets[n]["params"]})
    x, sr = sf.read(str(src), dtype="float32")
    x = x if x.ndim == 1 else x.mean(axis=1)
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), batch.process_clip(x, sr, steps, codes), sr, subtype="PCM_16")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preset", action="append", default=[])
    a = ap.parse_args()
    apply(Path(a.src), Path(a.out), a.preset)
```

`studio_server/fx.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import Config
from .errors import ApiError
from .jsonio import read_json
from .speakers import studio_dir
from .store import read_takes, update_take

FX_TIMEOUT_S = 120


def list_presets(cfg: Config) -> list[str]:
    names = [s["name"] for s in read_json(cfg.root / "tools/fx_lab/scenarios.json", {"scenarios": []})["scenarios"]]
    names += [n for n in read_json(cfg.data / "fx_lab/presets.json", {}) if n not in names]
    return names


def apply_to_take(cfg: Config, slug: str, take_id: str, presets: list[str]) -> dict:
    take = read_takes(cfg, slug).get(take_id)
    if take is None:
        raise ApiError(404, f"no take '{take_id}'")
    if not presets:
        return update_take(cfg, slug, take_id, fx=None)
    py = cfg.root / "tools/fx_lab/.venv-fx/bin/python"
    if not py.is_file():
        raise ApiError(500, "tools/fx_lab/.venv-fx is missing")
    out = studio_dir(cfg, slug) / "fx" / f"{take_id}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).with_name("fx_apply.py")
    try:
        r = subprocess.run([str(py), str(script), "--in", str(cfg.root / take["raw"]), "--out", str(out)]
                           + [a for n in presets for a in ("--preset", n)], capture_output=True, text=True,
                           timeout=FX_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise ApiError(500, f"FX took longer than {FX_TIMEOUT_S}s and was stopped")
    if r.returncode != 0:
        raise ApiError(500, ((r.stderr or r.stdout).strip().splitlines() or ["fx failed"])[-1][:300])
    return update_take(cfg, slug, take_id, fx={"presets": presets, "wav": f"data/studio/{slug}/fx/{take_id}.wav",
                                               "v": int(out.stat().st_mtime)})
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests -q`
Expected: all pass.

- [ ] **Step 5: Real FX check (CPU only, no GPU)**

Run:
```bash
cd /home/geoff/projects/games/W40KRogueTraderNeuralSpeechMod && S=/tmp/claude-1000/-home-geoff-projects-games-W40KRogueTraderNeuralSpeechMod/cfeb1f31-c9bd-483d-bff2-26fc2e9d570a/scratchpad
tools/fx_lab/.venv-fx/bin/python tools/studio/server/studio_server/fx_apply.py --in data/voices/wav/Pasqal/BNTRS_DLC2_Pasqal_347.wav --out $S/fx_check.wav --preset Clean && ls -l $S/fx_check.wav
```
Expected: a non-empty wav is written to the scratchpad.

- [ ] **Step 6: Checkpoint** (`git status`; no commit unless asked)

---

### Task 6: Routes, HTTP app, static serving, integration test

**Files:**
- Create: `studio_server/routes.py`, `studio_server/app.py`, `studio_server/__main__.py`, `tests/test_http.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `build_router() -> Router`; `make_server(cfg, model, port=0, web_dist=None) -> ThreadingHTTPServer`; CLI `python -m studio_server [--port 8930] [--backend URL]`. HTTP surface:

| Method and path | Handler |
|---|---|
| `GET /api/model/health` | `{"state": "down"|"ready"|"busy"}` |
| `GET /api/speakers` | `list_speakers` |
| `GET /api/speakers/{slug}` | `speaker_detail` |
| `GET /api/speakers/{slug}/lines` | `speaker_lines` |
| `GET /api/speakers/{slug}/takes` | `read_takes` as a list, newest first |
| `GET /api/speakers/{slug}/profile` / `POST` | `get_profile` (404 if none) / `save_profile` |
| `POST /api/speakers/{slug}/active` | `set_active` |
| `POST /api/speakers/{slug}/register` | `design.register_pick` (picked candidate into the prompt bank) |
| `POST /api/speakers/{slug}/design/generate` / `keep` / `verdict` / `order` / `description` | design functions (`order` body `{order: [...]}`, `description` body `{description}`) |
| `POST /api/speakers/{slug}/clone/generate` | `clone.generate` |
| `POST /api/speakers/{slug}/takes/{id}/fx` | `fx.apply_to_take` (body `{presets}`) |
| `POST /api/speakers/{slug}/takes/{id}/rate` | `clone.rate_take` |
| `GET /api/fx/presets` | `fx.list_presets` |
| `GET /file?p=<repo-relative>` | audio from whitelisted roots (404 otherwise) |
| anything else | static file from `web/dist`, SPA fallback to `index.html`, 503 text if not built |

- [ ] **Step 1: Write the failing test**

`tests/test_http.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_http.py -q`
Expected: `ModuleNotFoundError: No module named 'studio_server.app'`.

- [ ] **Step 3: Implement**

`studio_server/routes.py`:

```python
from __future__ import annotations

from . import clone, design, fx, speakers, store
from .errors import ApiError
from .router import Router


def build_router() -> Router:
    r = Router()
    S = "/api/speakers/{slug}"
    r.add("GET", "/api/model/health", lambda q: {"state": q.model.health()})
    r.add("GET", "/api/speakers", lambda q: speakers.list_speakers(q.cfg))
    r.add("GET", S, lambda q: speakers.speaker_detail(q.cfg, q.params["slug"]))
    r.add("GET", S + "/lines", lambda q: speakers.speaker_lines(q.cfg, speakers.find_speaker(q.cfg, q.params["slug"])["name"]))
    def list_takes(q):
        speakers.find_speaker(q.cfg, q.params["slug"])      # 404 for an unknown speaker, like every sibling route
        return sorted(store.read_takes(q.cfg, q.params["slug"]).values(), key=lambda t: t["id"], reverse=True)

    r.add("GET", S + "/takes", list_takes)

    def get_profile(q):
        p = store.get_profile(q.cfg, q.params["slug"])
        if p is None:
            raise ApiError(404, "no profile saved yet")
        return p

    r.add("GET", S + "/profile", get_profile)
    r.add("POST", S + "/profile", lambda q: store.save_profile(q.cfg, q.params["slug"], q.body))
    r.add("POST", S + "/active", lambda q: store.set_active(q.cfg, q.params["slug"]))
    r.add("POST", S + "/design/generate", lambda q: design.generate(q.cfg, q.model, q.params["slug"], q.body))
    r.add("POST", S + "/design/keep", lambda q: design.keep(q.cfg, q.params["slug"], q.body))
    r.add("POST", S + "/design/verdict", lambda q: design.post_verdict(q.cfg, q.params["slug"], q.body))
    r.add("POST", S + "/design/order", lambda q: design.post_order(q.cfg, q.params["slug"], q.body.get("order", [])))
    r.add("POST", S + "/register", lambda q: design.register_pick(q.cfg, q.params["slug"]))
    r.add("POST", S + "/design/description",
          lambda q: design.post_description(q.cfg, q.params["slug"], q.body.get("description", "")))
    r.add("POST", S + "/clone/generate", lambda q: clone.generate(q.cfg, q.model, q.params["slug"], q.body))
    r.add("POST", S + "/takes/{id}/fx",
          lambda q: fx.apply_to_take(q.cfg, q.params["slug"], q.params["id"], q.body.get("presets", [])))
    r.add("POST", S + "/takes/{id}/rate", lambda q: clone.rate_take(q.cfg, q.params["slug"], q.params["id"], q.body))
    r.add("GET", "/api/fx/presets", lambda q: fx.list_presets(q.cfg))
    return r
```

`studio_server/app.py`:

```python
from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import DEFAULT_BACKEND_URL, Config
from .model import ModelClient
from .routes import build_router

DEFAULT_PORT = 8930
DEFAULT_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def make_server(cfg: Config, model: ModelClient, port: int = DEFAULT_PORT, web_dist: Path | None = None):
    router, dist = build_router(), web_dist or DEFAULT_DIST

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _api(self, method: str, body: dict) -> None:
            u = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(u.query).items()}
            status, obj = router.dispatch(method, u.path, query, body, cfg, model)
            self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path.startswith("/api/"):
                return self._api("GET", {})
            if u.path == "/file":
                p = cfg.resolve_file(parse_qs(u.query).get("p", [""])[0])
                if p is None:
                    return self._send(404, b"not found", "text/plain")
                return self._send(200, p.read_bytes(), mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            rel = u.path.lstrip("/")
            f = (dist / rel).resolve() if rel else None
            if f and f.is_file() and dist.resolve() in f.parents:
                return self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            index = dist / "index.html"
            if index.is_file():
                return self._send(200, index.read_bytes(), "text/html; charset=utf-8")
            self._send(503, b"web app not built: cd tools/studio/web && npm run build", "text/plain")

        def do_POST(self) -> None:
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except ValueError:
                return self._send(400, b'{"error":"body is not JSON"}', "application/json")
            self._api("POST", body)

        def log_message(self, *a) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--backend", default=DEFAULT_BACKEND_URL)
    a = ap.parse_args()
    cfg = Config(backend_url=a.backend)
    print(f"Voice Studio on http://127.0.0.1:{a.port}  (model backend {a.backend})", flush=True)
    make_server(cfg, ModelClient(a.backend), a.port).serve_forever()
```

`studio_server/__main__.py`:

```python
from .app import main

main()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests -q`
Expected: all pass (about 60 tests).

- [ ] **Step 5: Run against the real repo with the model off**

Run:
```bash
cd tools/studio/server && (python3 -m studio_server --port 8930 > /tmp/claude-1000/-home-geoff-projects-games-W40KRogueTraderNeuralSpeechMod/cfeb1f31-c9bd-483d-bff2-26fc2e9d570a/scratchpad/studio.log 2>&1 &) ; sleep 1.5
curl -s localhost:8930/api/model/health; curl -s localhost:8930/api/speakers | head -c 300; echo
curl -s -o /dev/null -w "%{http_code}\n" "localhost:8930/file?p=data/voices/wav/Pasqal/BNTRS_DLC2_Pasqal_347.wav"
curl -s -o /dev/null -w "%{http_code}\n" "localhost:8930/file?p=data/strings.enGB.json"
curl -s -X POST localhost:8930/api/speakers/muaran/design/generate -d '{}'
```
Expected: `{"state": "down"}`, a speaker list JSON, `200`, `404`, and the 503 "model backend is not running" error. Stop the server by PID (`ss -ltnp | grep :8930`, then `kill <pid>`).

- [ ] **Step 6: Checkpoint** (`git status`; no commit unless asked)
