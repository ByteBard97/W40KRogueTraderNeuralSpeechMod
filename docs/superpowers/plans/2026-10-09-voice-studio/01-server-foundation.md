# Voice Studio first slice, part 1 of 7: Server foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Overview and table of contents:** [Voice Studio first slice](../2026-10-09-voice-studio-first-slice.md). Read it first: it holds the goal, architecture, file structure and review focus for the whole slice.
**Spec:** [`docs/superpowers/specs/2026-10-09-voice-studio-design.md`](../../specs/2026-10-09-voice-studio-design.md)
**This part:** Tasks 1 to 3. Python API: scaffold, config, router, speakers, profiles and takes.
**Previous part:** none. **Next part:** [Server live calls and HTTP app](02-server-live-and-api.md).

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

### Task 1: Server scaffold, config, router, test fixture repo

**Files:**
- Create: `tools/studio/server/studio_server/__init__.py` (empty), `config.py`, `errors.py`, `jsonio.py`, `router.py`
- Create: `tools/studio/server/tests/conftest.py`, `tools/studio/server/tests/test_core.py`

**Interfaces:**
- Produces: `Config(root: Path, backend_url: str)` with properties `data, studio, voice_design, voices, render` and methods `file_roots() -> tuple[Path, ...]`, `resolve_file(rel: str) -> Path | None`, `under_data(rel: str) -> Path | None`; `ApiError(status: int, message: str)`; `read_json(path, default)`, `write_json_atomic(path, obj)`; `Request(cfg, model, params, query, body)`; `Router.add(method, pattern, fn)`, `Router.dispatch(method, path, query, body, cfg, model) -> tuple[int, object]`; test fixtures `cfg` (a `Config` over a tiny fake repo) and `make_repo(root) -> Config`.

- [ ] **Step 1: Write the failing tests**

`tools/studio/server/tests/test_core.py`:

```python
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
```

`tools/studio/server/tests/conftest.py` (the fake repo every later task uses):

```python
import json
import math
import struct
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio_server.config import Config  # noqa: E402


def write_wav(path: Path, seconds: float = 0.1, sr: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i / 10))) for i in range(int(sr * seconds))))


def put(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def make_repo(root: Path) -> Config:
    """A tiny fake repo: real speaker Pasqal (2 catalog clips, 1 curated), designed speaker Muaran (2 candidates)."""
    d = root / "data"
    for n in ("E1", "E2"):
        write_wav(d / f"voices/wav/Pasqal/{n}.wav")
    put(d / "voices/catalog.json", {
        "E1": {"event": "E1", "speaker": "Pasqal", "wav": "wav/Pasqal/E1.wav", "duration": 5.0,
               "texts": [{"guid": "g1", "text": "Hello."}]},
        "E2": {"event": "E2", "speaker": "Pasqal", "wav": "wav/Pasqal/E2.wav", "duration": 3.0,
               "texts": [{"guid": "g2", "text": "Bye."}]}})
    put(d / "voices/prompts/prompts.json", {"Pasqal": [{"rank": 1, "event": "E1", "wav": "prompts/Pasqal/01.wav",
                                                        "text": "Hello.", "noise_db": -60.0}]})
    jobs = [
        {"guid": "g1", "speaker": "Pasqal", "text": "Greetings, Rogue Trader.", "voice_source": "prompt_bank",
         "annotation": {"emotion": "neutral", "intensity": 0.25, "pace": "normal", "instruct": "formal"}},
        {"guid": "g2", "speaker": "Pasqal", "text": "Farewell.", "voice_source": "prompt_bank",
         "annotation": {"emotion": "sad", "intensity": 0.5, "pace": "slow", "instruct": None}},
        {"guid": "g3", "speaker": "Muaran", "text": "Welcome aboard.", "voice_source": "fallback", "annotation": {}},
        {"guid": "g4", "speaker": "narrator", "text": "You see a door.", "voice_source": "narrator", "annotation": {}},
    ]
    (d / "render").mkdir(parents=True, exist_ok=True)
    (d / "render/jobs.jsonl").write_text("\n".join(json.dumps(j) for j in jobs) + "\n", encoding="utf-8")
    write_wav(d / "render/export/wav/g1.wav")
    put(d / "render/export/index.json", {"g1": {"wav": "wav/g1.wav"}})
    for c in ("c0.wav", "c1.wav"):
        write_wav(d / f"voice_design/clips/muaran/{c}")
    put(d / "voice_design/design_manifest.json", {"Muaran": {
        "slug": "muaran", "gender": "Female", "role": "officer", "description": "A calm woman.",
        "text": "The augurs report nothing unusual.", "engine": "vox", "candidates": ["c0.wav", "c1.wav"]}})
    put(d / "voice_design/scores.json", {"clips/muaran/c0.wav": {"p_us": 0.2, "top": "england", "p_top": 0.7}})
    put(d / "voice_design/audit.json", {})
    put(root / "tools/fx_lab/scenarios.json", {"scenarios": [{"name": "Clean", "params": {}}]})
    return Config(root=root)


@pytest.fixture
def cfg(tmp_path) -> Config:
    return make_repo(tmp_path)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_core.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'studio_server.config'`.

- [ ] **Step 3: Implement**

`studio_server/errors.py`:

```python
class ApiError(Exception):
    """Raised by handlers; the router turns it into {"error": message} with this HTTP status."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message
```

`studio_server/jsonio.py`:

```python
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .errors import ApiError

# The server is threaded and several handlers read-modify-write the same JSON files (takes.json, audit.json).
# Every such update takes this lock so two requests cannot lose each other's write.
STATE_LOCK = threading.RLock()


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ApiError(500, f"{path.name} is not valid JSON: {e}")


def write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
```

`studio_server/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BACKEND_URL = "http://127.0.0.1:8909"


@dataclass(frozen=True)
class Config:
    root: Path = REPO_ROOT
    backend_url: str = DEFAULT_BACKEND_URL

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def studio(self) -> Path:
        return self.data / "studio"

    @property
    def voice_design(self) -> Path:
        return self.data / "voice_design"

    @property
    def voices(self) -> Path:
        return self.data / "voices"

    @property
    def render(self) -> Path:
        return self.data / "render"

    def file_roots(self) -> tuple[Path, ...]:
        return (self.voices, self.render, self.studio, self.voice_design)

    def _inside(self, rel: str, roots: tuple[Path, ...]) -> Path | None:
        if not rel or rel.startswith("/"):
            return None
        p = (self.root / rel).resolve()
        if p.is_file() and any(r.resolve() in p.parents for r in roots):
            return p
        return None

    def resolve_file(self, rel: str) -> Path | None:
        """Repo-relative path -> real file under a served root, else None."""
        return self._inside(rel, self.file_roots())

    def under_data(self, rel: str) -> Path | None:
        """Repo-relative path -> real file anywhere under data/, else None (used for clone references)."""
        return self._inside(rel, (self.data,))
```

`studio_server/router.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import Config
from .errors import ApiError


@dataclass
class Request:
    cfg: Config
    model: Any
    params: dict = field(default_factory=dict)
    query: dict = field(default_factory=dict)
    body: dict = field(default_factory=dict)


Handler = Callable[[Request], Any]


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern, Handler]] = []

    def add(self, method: str, pattern: str, fn: Handler) -> None:
        rx = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$")
        self._routes.append((method, rx, fn))

    def dispatch(self, method: str, path: str, query: dict, body: dict, cfg: Config, model) -> tuple[int, object]:
        for m, rx, fn in self._routes:
            hit = rx.match(path)
            if m != method or not hit:
                continue
            try:
                out = fn(Request(cfg, model, hit.groupdict(), query, body))
            except ApiError as e:
                return e.status, {"error": e.message}
            except Exception as e:  # a bad body (missing key, wrong type) must answer, not drop the connection
                return 500, {"error": f"{type(e).__name__}: {e}"}
            return out if isinstance(out, tuple) else (200, out)
        return 404, {"error": f"no route {method} {path}"}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests/test_core.py -q`
Expected: all pass.

- [ ] **Step 5: Checkpoint**

Run: `git status --short tools/studio` and confirm only new files under `tools/studio/`. Do not commit unless asked.

---

### Task 2: Speakers: list, detail, lines

**Files:**
- Create: `tools/studio/server/studio_server/speakers.py`, `tools/studio/server/tests/test_speakers.py`

**Interfaces:**
- Consumes: `Config`, `read_json`, `ApiError`.
- Produces:
  - `slugify(name: str) -> str`
  - `list_speakers(cfg) -> list[dict]` each `{slug, name, origin: 'real'|'designed', line_count: int, status: 'needs_voice'|'source'|'profile'}`, sorted by name, slugs unique.
  - `find_speaker(cfg, slug) -> dict` (a summary; raises `ApiError(404)`)
  - `speaker_detail(cfg, slug) -> {summary, clips, design, profile}` where `clips: list[{id, wav, duration, text, curated_rank, noise_db}]`, `design` is `None` for real speakers or `{description, text, candidates: list[{id, file, scores, verdict, gen}], order: list[str], pick}`, `profile` is the saved profile dict or `None` (read through `studio_dir(cfg, slug) / "profile.json"`).
  - `speaker_lines(cfg, name) -> list[{guid, text, emotion, intensity, pace, instruct, baseline}]`
  - `studio_dir(cfg, slug) -> Path` (`cfg.studio / slug`)

- [ ] **Step 1: Write the failing tests**

`tests/test_speakers.py`:

```python
import pytest

from studio_server import speakers
from studio_server.errors import ApiError
from conftest import put, write_wav


def by_name(cfg):
    return {s["name"]: s for s in speakers.list_speakers(cfg)}


def test_list_marks_origin_counts_and_status(cfg):
    s = by_name(cfg)
    assert s["Pasqal"]["origin"] == "real" and s["Pasqal"]["line_count"] == 2 and s["Pasqal"]["status"] == "source"
    assert s["Muaran"]["origin"] == "designed" and s["Muaran"]["line_count"] == 1
    assert s["Muaran"]["status"] == "needs_voice"
    assert "narrator" not in s


def test_status_follows_pick_and_profile(cfg):
    put(cfg.voice_design / "audit.json", {"Muaran": {"cands": {}, "pick": "c1.wav", "order": ["c1.wav"]}})
    assert by_name(cfg)["Muaran"]["status"] == "source"
    put(cfg.studio / "muaran/profile.json", {"name": "Muaran"})
    assert by_name(cfg)["Muaran"]["status"] == "profile"


def test_slugs_are_unique_and_stable_when_names_collide(cfg):
    put(cfg.voices / "prompts/prompts.json", {"Ulfar": [], "ulfar!": []})
    slugs = [s["slug"] for s in speakers.list_speakers(cfg) if s["name"] in ("Ulfar", "ulfar!")]
    assert len(set(slugs)) == 2
    assert slugs == [s["slug"] for s in speakers.list_speakers(cfg) if s["name"] in ("Ulfar", "ulfar!")]


def test_detail_real_speaker_clips_sorted_curated_first(cfg):
    d = speakers.speaker_detail(cfg, "pasqal")
    assert d["design"] is None and d["profile"] is None
    assert [c["id"] for c in d["clips"]] == ["E1", "E2"]
    assert d["clips"][0]["curated_rank"] == 1 and d["clips"][0]["noise_db"] == -60.0
    assert d["clips"][1]["curated_rank"] is None
    assert d["clips"][0]["wav"] == "data/voices/wav/Pasqal/E1.wav"


def test_detail_designed_speaker_merges_scores_audit_overrides(cfg):
    put(cfg.voice_design / "audit.json", {"Muaran": {"cands": {"c0.wav": {"fit": 4}}, "pick": "c0.wav",
                                                     "order": ["c1.wav", "c0.wav"]}})
    put(cfg.voice_design / "overrides.json", {"Muaran": "A stern woman."})
    d = speakers.speaker_detail(cfg, "muaran")["design"]
    assert d["description"] == "A stern woman." and d["pick"] == "c0.wav"
    assert [c["id"] for c in d["candidates"]] == ["c1.wav", "c0.wav"]      # ranked order first
    c0 = next(c for c in d["candidates"] if c["id"] == "c0.wav")
    assert c0["verdict"] == {"fit": 4} and c0["scores"]["p_us"] == 0.2
    assert c0["file"] == "data/voice_design/clips/muaran/c0.wav"


def test_detail_unknown_slug_is_404(cfg):
    with pytest.raises(ApiError) as e:
        speakers.speaker_detail(cfg, "nobody")
    assert e.value.status == 404


def test_lines_include_bank_clip_and_skip_other_speakers(cfg):
    ls = speakers.speaker_lines(cfg, "Pasqal")
    assert [l["guid"] for l in ls] == ["g1", "g2"]
    assert ls[0]["baseline"] == "data/render/export/wav/g1.wav" and ls[1]["baseline"] is None
    assert ls[0]["emotion"] == "neutral" and ls[0]["instruct"] == "formal"


def test_registered_designed_speaker_stays_designed_and_shows_its_registered_clip(cfg):
    write_wav(cfg.voices / "prompts/designed/muaran.wav")
    put(cfg.voices / "prompts/prompts.json", {"Pasqal": [], "Muaran": [
        {"rank": 1, "event": "designed_muaran", "wav": "prompts/designed/muaran.wav", "text": "t", "duration": 1.0}]})
    s = by_name(cfg)["Muaran"]
    assert s["origin"] == "designed"
    d = speakers.speaker_detail(cfg, "muaran")
    assert d["design"] is not None
    assert [c["id"] for c in d["clips"]] == ["designed_muaran"]
    assert d["clips"][0]["wav"] == "data/voices/prompts/designed/muaran.wav"


def test_prompt_only_speaker_such_as_the_narrator_lists_its_prompt_clips(cfg):
    put(cfg.voices / "prompts/prompts.json", {"narrator_bg3": [
        {"rank": 1, "event": "n1", "wav": "prompts/narrator_bg3/01.wav", "text": "x", "duration": 9.0}]})
    d = speakers.speaker_detail(cfg, "narrator_bg3")
    assert [c["id"] for c in d["clips"]] == ["n1"] and d["design"] is None


def test_speaker_with_no_lines_or_clips_is_empty_not_error(cfg):
    put(cfg.voices / "prompts/prompts.json", {"Pasqal": [], "Ghost": []})
    assert speakers.speaker_lines(cfg, "Ghost") == []
    assert speakers.speaker_detail(cfg, "ghost")["clips"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_speakers.py -q`
Expected: `ModuleNotFoundError: No module named 'studio_server.speakers'`.

- [ ] **Step 3: Implement**

`studio_server/speakers.py`:

```python
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import Config
from .errors import ApiError
from .jsonio import read_json

_CACHE: dict[Path, tuple[int, object]] = {}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "unnamed"


def studio_dir(cfg: Config, slug: str) -> Path:
    return cfg.studio / slug


def _cached(path: Path, load):
    """Parse big files once per modification time (jobs.jsonl is ~26k rows)."""
    if not path.exists():
        return load(None)
    mtime = path.stat().st_mtime_ns
    hit = _CACHE.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    val = load(path)
    _CACHE[path] = (mtime, val)
    return val


def _jobs(cfg: Config) -> list[dict]:
    def load(p):
        if p is None:
            return []
        return [json.loads(ln) for ln in p.open(encoding="utf-8") if ln.strip()]
    return _cached(cfg.render / "jobs.jsonl", load)


def _export_index(cfg: Config) -> dict:
    return _cached(cfg.render / "export/index.json", lambda p: {} if p is None else json.loads(p.read_text(encoding="utf-8")))


def _designed(cfg: Config) -> dict:
    return read_json(cfg.voice_design / "design_manifest.json", {})


def _real_names(cfg: Config) -> list[str]:
    return list(read_json(cfg.voices / "prompts/prompts.json", {}))


def list_speakers(cfg: Config) -> list[dict]:
    audit = read_json(cfg.voice_design / "audit.json", {})
    counts: dict[str, int] = {}
    for j in _jobs(cfg):
        counts[j["speaker"]] = counts.get(j["speaker"], 0) + 1
    designed = _designed(cfg)      # a name in the design manifest stays "designed" even after its pick is registered
    entries = [(n, "designed") for n in designed] + [(n, "real") for n in _real_names(cfg) if n not in designed]
    out, used = [], set()
    for name, origin in sorted(entries, key=lambda e: e[0].lower()):
        base = slug = slugify(name)
        i = 2
        while slug in used:
            slug, i = f"{base}_{i}", i + 1
        used.add(slug)
        if (studio_dir(cfg, slug) / "profile.json").exists():
            status = "profile"
        elif origin == "real" or (audit.get(name) or {}).get("pick"):
            status = "source"
        else:
            status = "needs_voice"
        out.append({"slug": slug, "name": name, "origin": origin, "line_count": counts.get(name, 0), "status": status})
    return out


def find_speaker(cfg: Config, slug: str) -> dict:
    for s in list_speakers(cfg):
        if s["slug"] == slug:
            return s
    raise ApiError(404, f"no speaker '{slug}'")


def _clips(cfg: Config, name: str) -> list[dict]:
    prompts = read_json(cfg.voices / "prompts/prompts.json", {}).get(name, [])
    curated = {p["event"]: p for p in prompts}
    out, seen = [], set()
    for e in read_json(cfg.voices / "catalog.json", {}).values():
        if e["speaker"] != name:
            continue
        seen.add(e["event"])
        pr = curated.get(e["event"])
        out.append({"id": e["event"], "wav": "data/voices/" + e["wav"], "duration": e["duration"],
                    "text": " ".join(t["text"] for t in e["texts"]),
                    "curated_rank": pr["rank"] if pr else None, "noise_db": pr.get("noise_db") if pr else None})
    for p in prompts:   # prompt-bank clips with no catalog entry: registered designed voices, narrator clips
        if p["event"] not in seen:
            out.append({"id": p["event"], "wav": "data/voices/" + p["wav"], "duration": p.get("duration", 0.0),
                        "text": p.get("text", ""), "curated_rank": p.get("rank"), "noise_db": p.get("noise_db")})
    out.sort(key=lambda c: (c["curated_rank"] is None, c["curated_rank"] or 0, c["id"]))
    return out


def _design(cfg: Config, name: str) -> dict | None:
    m = _designed(cfg).get(name)
    if not m:
        return None
    a = read_json(cfg.voice_design / "audit.json", {}).get(name) or {}
    scores = read_json(cfg.voice_design / "scores.json", {})
    gen = m.get("gen", {}).get("candidates", {})
    cands = [{"id": c, "file": f"data/voice_design/clips/{m['slug']}/{c}",
              "scores": scores.get(f"clips/{m['slug']}/{c}"), "verdict": (a.get("cands") or {}).get(c, {}),
              "gen": gen.get(c)} for c in m["candidates"]]
    order = [c for c in a.get("order", []) if c in m["candidates"]]
    cands.sort(key=lambda c: (c["id"] not in order, order.index(c["id"]) if c["id"] in order else 0))
    desc = read_json(cfg.voice_design / "overrides.json", {}).get(name, m["description"])
    return {"description": desc, "text": m["text"], "candidates": cands, "order": order, "pick": a.get("pick")}


def speaker_detail(cfg: Config, slug: str) -> dict:
    s = find_speaker(cfg, slug)
    return {"summary": s, "clips": _clips(cfg, s["name"]),
            "design": _design(cfg, s["name"]) if s["origin"] == "designed" else None,
            "profile": read_json(studio_dir(cfg, slug) / "profile.json", None)}


def speaker_lines(cfg: Config, name: str) -> list[dict]:
    index = _export_index(cfg)
    out = []
    for j in _jobs(cfg):
        if j["speaker"] != name:
            continue
        a = j.get("annotation") or {}
        wav = index.get(j["guid"], {}).get("wav")
        out.append({"guid": j["guid"], "text": j["text"], "emotion": a.get("emotion"), "intensity": a.get("intensity"),
                    "pace": a.get("pace"), "instruct": a.get("instruct"),
                    "baseline": f"data/render/export/{wav}" if wav else None})
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests -q`
Expected: all pass (test_core + test_speakers).

- [ ] **Step 5: Smoke against the real repo (read-only)**

Run:
```bash
cd tools/studio/server && python3 -c "
from studio_server.config import Config
from studio_server import speakers as s
c = Config()
L = s.list_speakers(c); print(len(L), [x['name'] for x in L][:5])
d = s.speaker_detail(c, 'pasqal'); print(len(d['clips']), len(s.speaker_lines(c, 'Pasqal')))
print(len(s.speaker_detail(c, 'vox_master_vigdis')['design']['candidates']))"
```
Expected: 35 speakers (23 real + 12 designed), Pasqal 45 clips and 844 lines, Vigdis 6 or more candidates.

- [ ] **Step 6: Checkpoint** (`git status`; no commit unless asked)

---

### Task 3: Profiles, takes and "set active" store

**Files:**
- Create: `tools/studio/server/studio_server/store.py`, `tools/studio/server/tests/test_store.py`

**Interfaces:**
- Consumes: `studio_dir`, `find_speaker` (Task 2), `read_json`, `write_json_atomic`, `Config.under_data`.
- Produces:
  - `OPTION_DEFAULTS: dict` = `{"cfg": 2.0, "timesteps": 10, "seed": "", "use_instruct": False, "retry_badcase": False, "normalize": False, "continuation": False}`
  - `save_profile(cfg, slug, body) -> dict` (body: `{source: {wav, text, origin}, options?, fx?, test_lines?, notes?}`)
  - `get_profile(cfg, slug) -> dict | None`
  - `set_active(cfg, slug) -> {"active": "data/studio/<slug>/active.json"}`
  - `read_takes(cfg, slug) -> dict[str, dict]`, `add_take(cfg, slug, take) -> dict`, `update_take(cfg, slug, take_id, **fields) -> dict`, `new_take_id() -> str`

- [ ] **Step 1: Write the failing tests**

`tests/test_store.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_store.py -q`
Expected: `ModuleNotFoundError: No module named 'studio_server.store'`.

- [ ] **Step 3: Implement**

`studio_server/store.py`:

```python
from __future__ import annotations

import shutil
import time

from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic
from .speakers import find_speaker, studio_dir

OPTION_DEFAULTS = {"cfg": 2.0, "timesteps": 10, "seed": "", "use_instruct": False, "retry_badcase": False,
                   "normalize": False, "continuation": False}
ORIGINS = ("real", "designed", "supplied")
_LAST_ID = [0]


def new_take_id() -> str:
    """Millisecond timestamp id, forced strictly increasing within the process."""
    n = max(int(time.time() * 1000), _LAST_ID[0] + 1)
    _LAST_ID[0] = n
    return f"t{n}"


def get_profile(cfg: Config, slug: str) -> dict | None:
    return read_json(studio_dir(cfg, slug) / "profile.json", None)


def save_profile(cfg: Config, slug: str, body: dict) -> dict:
    sp = find_speaker(cfg, slug)
    src = body.get("source") or {}
    if src.get("origin") not in ORIGINS:
        raise ApiError(400, f"source.origin must be one of {ORIGINS}")
    if cfg.under_data(src.get("wav", "")) is None:
        raise ApiError(400, f"source.wav is not a file under data/: {src.get('wav')!r}")
    opts = {k: (body.get("options") or {}).get(k, v) for k, v in OPTION_DEFAULTS.items()}
    prof = {"name": sp["name"], "slug": slug, "kind": "speaker",
            "source": {"wav": src["wav"], "text": src.get("text", ""), "origin": src["origin"]},
            "options": opts, "fx": list(body.get("fx") or []), "test_lines": list(body.get("test_lines") or []),
            "notes": body.get("notes", ""), "saved": time.strftime("%Y-%m-%d %H:%M:%S")}
    write_json_atomic(studio_dir(cfg, slug) / "profile.json", prof)
    return prof


def set_active(cfg: Config, slug: str) -> dict:
    find_speaker(cfg, slug)
    src = studio_dir(cfg, slug) / "profile.json"
    if not src.is_file():
        raise ApiError(404, "save a profile first")
    shutil.copyfile(src, studio_dir(cfg, slug) / "active.json")
    return {"active": f"data/studio/{slug}/active.json"}


def read_takes(cfg: Config, slug: str) -> dict:
    return read_json(studio_dir(cfg, slug) / "takes.json", {})


def add_take(cfg: Config, slug: str, take: dict) -> dict:
    with STATE_LOCK:
        takes = read_takes(cfg, slug)      # raises 500 on a corrupt file before anything is written
        takes[take["id"]] = take
        write_json_atomic(studio_dir(cfg, slug) / "takes.json", takes)
    return take


def update_take(cfg: Config, slug: str, take_id: str, **fields) -> dict:
    with STATE_LOCK:
        takes = read_takes(cfg, slug)
        if take_id not in takes:
            raise ApiError(404, f"no take '{take_id}'")
        takes[take_id].update(fields)
        write_json_atomic(studio_dir(cfg, slug) / "takes.json", takes)
        return takes[take_id]
```

Note: `test_save_profile_rejects_unknown_origin_and_speaker` uses the slug `nobody`; `find_speaker` raises 404 before origin is checked, which is the order the test expects for the second case. The first case uses a known speaker with a bad origin.

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests -q`
Expected: all pass.

- [ ] **Step 5: Checkpoint** (`git status`; no commit unless asked)
