# Voice Studio, Pools slice: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route every unnamed priority-3 line to the right voice (a companion's real bank, a named NPC's voice, the narrator, or a shared slot voice), let the user review the uncertain ones per roster entry, and make the render plan use the result.

**Architecture:** A pure routing engine (`pools_routing.py`, `pools_slots.py`) turns the harness roster plus the existing matcher (`tools/npc_profile/known.py`) into per-line routes and slots. A service module (`pools.py`) persists them in `data/studio/pools.json`, keeps user overrides across rebuilds, and registers each slot as a designed speaker in `design_manifest.json` so the existing Speakers page designs, ranks and registers its voice. New routes expose it; a Pools view in the Vue app shows the routing summary, slots, the by-entry review queue and a spot check. `plan.py` gets one rule that reads `pools.json`.

**Tech Stack:** Python 3.12 stdlib + pytest (server, same as slice 1); Vue 3.5, TypeScript, Pinia, Vitest (web).

**Spec:** `docs/superpowers/specs/2026-10-09-voice-studio-pools-design.md` (parent: `2026-10-09-voice-studio-design.md`).

## Global Constraints

- Local only; the server binds `127.0.0.1`. Nothing here runs the model or uses a GPU.
- Nothing in the app or the tests deletes files. Tests write only under pytest `tmp_path`; manual checks back up `data/studio/pools.json`, `data/voice_design/design_manifest.json`, `data/voices/prompts/prompts.json` and `data/render/jobs.jsonl` first and compare after.
- Do not `git commit` or `git push` unless the repo owner says so. Steps named "Checkpoint" run `git status` and stop. If the owner asks for commits: plain human messages, no AI/Claude attribution of any kind.
- Reuse existing schemas as-is: `roster_35b_all.json`, `match_decisions.json` (keys `"<conversation>|<roster id>"`, values `accept`/`reject`; the conversation string is used exactly as stored, including leading spaces), `design_manifest.json`, `prompts.json`, `jobs.jsonl`.
- Defaults: confidence threshold `0.8`, `MIN_SLOT_LINES = 40`, spot check `10` lines per slot, doubled for a slot with any wrong line.
- Frontend: `<script setup lang="ts">`, thin views, composables/stores for state, no magic numbers (named constants), files under 500 lines, `<style scoped>`, dark UI only (accent buttons use `color: #0b1220`).
- Server tests: `cd tools/studio/server && python3 -m pytest tests -q`. Web tests: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`.

## Review Focus

1. **A rebuild must never discard a user override** (a route with `source: "override"`, a renamed slot) and must not duplicate a manifest entry (Tasks 3, 4).
2. **A rejected match falls through** to the slot rules; an accepted one wins over ambiguity flags (Task 1).
3. **Bad input:** an override to an unknown slot or with no speaker is a 400 and writes nothing; a missing roster or an unbuilt `pools.json` answers a clear 404, never a crash (Tasks 3, 4).
4. **Lines stop being "unnamed" after `plan.py` reroutes them** (`routed_from`): a later rebuild must still see them (Task 3).
5. **Large lists:** the routes endpoint caps the page size and the web list pages instead of rendering 1,300 rows (Tasks 3, 7).
6. **Unrouted lines are unchanged** by the `plan.py` rule: no `pools.json`, or a guid with no route, gives exactly today's job (Task 5).

## File Structure

```
tools/studio/server/studio_server/
  pools_routing.py      route_lines: roster + matcher + decisions -> per-line routes           (Task 1)
  pools_slots.py        assign_slots: derive and merge slots from the slot-bound routes        (Task 2)
  pools.py              rebuild, summary, routes_page, queue, override, rename/merge, spot check (Task 3)
  routes.py             + /api/pools/* routes                                                  (Task 4)
tools/studio/server/tests/
  conftest.py           + make_pool_repo(root)                                                  (Task 3)
  test_pools_routing.py, test_pools_slots.py, test_pools.py, test_pools_http.py
tools/render_corpus/
  pool_routes.py        load_routes, resolve (pure)                                            (Task 5)
  plan.py               + one rule using pool_routes                                           (Task 5)
  tests/test_pool_routes.py
tools/studio/web/src/
  api/types.ts, api/client.ts         + pool types and calls                                    (Task 6)
  stores/pools.ts                                                                                (Task 6)
  components/pools/RoutingSummary.vue, SlotList.vue, QueuePanel.vue, SpotCheck.vue               (Task 7)
  views/PoolsView.vue, router.ts, components/shared/AppShell.vue (nav link)                      (Task 7)
```

---

### Task 1: Routing engine

**Files:**
- Create: `tools/studio/server/studio_server/pools_routing.py`, `tools/studio/server/tests/test_pools_routing.py`

**Interfaces:**
- Produces: `NARRATOR_ID = "NARRATOR"`, `DEFAULT_THRESHOLD = 0.8`, `entry_key(conversation: str, roster_id: str) -> str`, and `route_lines(guids: set[str], roster: list[dict], known: dict, decisions: dict, threshold: float = DEFAULT_THRESHOLD) -> dict[str, dict]`. Each route: `{"to": "speaker"|"narrator"|"slot", "speaker"?: str, "has_bank"?: bool, "attr"?: {"gender","species","age"}, "entry": str|None, "confidence": float|None, "reasons": list[str], "source": "auto"}`. A non-empty `reasons` means the line is in the review queue. Also re-exports `build_known` from `tools/npc_profile/known.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_pools_routing.py`:

```python
import pytest

from studio_server.pools_routing import build_known, entry_key, route_lines

KNOWN = {
    "Heinrix": {"lines": 40, "gender": "male", "has_bank": True, "tokens": {"heinrix"}},
    "Tervantias the Archmachinator": {"lines": 40, "gender": "male", "has_bank": False,
                                      "tokens": {"tervantias", "archmachinator"}},
}


def entry(rid, name=None, gender="male", species="human", age="unknown", conf=None):
    return {"id": rid, "name": name, "label": rid, "gender": gender, "species": species, "age": age,
            "conf": conf or {"gender": 0.95, "species": 0.95, "age": 0.9}, "evidence": []}


def conv(name, entries, lines):
    return {"conversation": name, "roster": entries,
            "lines": [{"n": i, "key": k, "speaker": s, "conf": {"speaker": c}} for i, (k, s, c) in enumerate(lines)]}


def route(roster, guids, decisions=None, threshold=0.8):
    return route_lines(set(guids), roster, KNOWN, decisions or {}, threshold)


def test_known_speaker_with_bank_and_without_bank():
    r = route([conv("C", [entry("a", "Heinrix"), entry("b", "Tervantias")], [("g1", "a", 1.0), ("g2", "b", 1.0)])], ["g1", "g2"])
    assert r["g1"]["to"] == "speaker" and r["g1"]["speaker"] == "Heinrix" and r["g1"]["has_bank"] is True
    assert r["g2"]["speaker"] == "Tervantias the Archmachinator" and r["g2"]["has_bank"] is False
    assert r["g1"]["entry"] == "C|a" and r["g1"]["reasons"] == [] and r["g1"]["source"] == "auto"


def test_narrator_lines_route_to_the_narrator():
    r = route([conv("C", [], [("g1", "NARRATOR", 1.0)])], ["g1"])
    assert r["g1"]["to"] == "narrator" and r["g1"]["entry"] is None and r["g1"]["reasons"] == []


def test_unknown_character_goes_to_a_slot_with_its_attributes():
    r = route([conv("C", [entry("m", gender="female", species="eldar", age="old")], [("g1", "m", 1.0)])], ["g1"])
    assert r["g1"]["to"] == "slot" and r["g1"]["attr"] == {"gender": "female", "species": "eldar", "age": "old"}
    assert r["g1"]["reasons"] == []


def test_a_rejected_match_falls_through_to_a_slot_and_an_accepted_one_clears_ambiguity():
    roster = [conv("C", [entry("a", "Heinrix")], [("g1", "a", 1.0)])]
    rejected = route(roster, ["g1"], {entry_key("C", "a"): "reject"})
    assert rejected["g1"]["to"] == "slot"
    known = {**KNOWN, "Heinrix Two": {"lines": 3, "gender": "male", "has_bank": False, "tokens": {"heinrix", "two"}}}
    amb = route_lines({"g1"}, roster, known, {}, 0.8)
    assert amb["g1"]["to"] == "speaker"
    accepted = route_lines({"g1"}, roster, known, {entry_key("C", "a"): "accept"}, 0.8)
    assert accepted["g1"]["reasons"] == []


@pytest.mark.parametrize("ent,line_conf,expected", [
    (entry("m", gender="unknown"), 1.0, ["gender unknown"]),
    (entry("m", conf={"gender": 0.5, "species": 0.95, "age": 0.9}), 1.0, ["gender low confidence"]),
    (entry("m", species="unknown"), 1.0, ["species unknown"]),
    (entry("m", conf={"gender": 0.95, "species": 0.4, "age": 0.9}), 1.0, ["species low confidence"]),
    (entry("m"), 0.5, ["line attribution"]),
    (entry("m", age="unknown", conf={"gender": 0.95, "species": 0.95, "age": 0.1}), 1.0, []),   # unknown age is not a review reason
])
def test_queue_reasons_use_only_the_voice_defining_axes(ent, line_conf, expected):
    r = route([conv("C", [ent], [("g1", "m", line_conf)])], ["g1"])
    assert r["g1"]["reasons"] == expected


def test_a_line_with_no_roster_entry_goes_to_a_human_slot_and_the_queue():
    r = route([conv("C", [], [("g1", "ghost", 1.0)])], ["g1"])
    assert r["g1"]["to"] == "slot" and r["g1"]["reasons"] == ["no roster entry"]
    assert r["g1"]["attr"]["species"] == "human"


def test_guids_missing_from_the_roster_still_get_a_queued_route():
    r = route([], ["lost"])
    assert r["lost"]["to"] == "slot" and r["lost"]["reasons"] == ["not in roster"]


def test_only_requested_guids_are_routed_and_first_conversation_wins():
    roster = [conv("A", [entry("m")], [("g1", "m", 1.0), ("other", "m", 1.0)]), conv("B", [entry("x", "Heinrix")], [("g1", "x", 1.0)])]
    r = route(roster, ["g1"])
    assert set(r) == {"g1"} and r["g1"]["to"] == "slot"


def test_build_known_is_reexported():
    assert callable(build_known)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_pools_routing.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'studio_server.pools_routing'`.

- [ ] **Step 3: Implement**

`studio_server/pools_routing.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools/npc_profile"))
from known import build_known, match  # noqa: E402,F401  (build_known is re-exported for pools.py)

NARRATOR_ID = "NARRATOR"
DEFAULT_THRESHOLD = 0.8
UNKNOWN = "unknown"


def entry_key(conversation: str, roster_id: str) -> str:
    """The key match_review.py uses in match_decisions.json. The conversation name is used exactly as stored."""
    return f"{conversation}|{roster_id}"


def _slot_route(attr: dict, entry: str | None, confidence: float | None, reasons: list[str]) -> dict:
    return {"to": "slot", "attr": attr, "entry": entry, "confidence": confidence, "reasons": reasons, "source": "auto"}


def _unknown_attr() -> dict:
    return {"gender": UNKNOWN, "species": "human", "age": UNKNOWN}


def _slot_reasons(x: dict, line_conf: float | None, threshold: float) -> list[str]:
    """Only the axes that change which voice a line gets. Unknown age is not a reason; low FX confidence is not either."""
    reasons = []
    if line_conf is not None and line_conf < threshold:
        reasons.append("line attribution")
    conf = x.get("conf") or {}
    if (x.get("gender") or UNKNOWN) == UNKNOWN:
        reasons.append("gender unknown")
    elif conf.get("gender", 1.0) < threshold:
        reasons.append("gender low confidence")
    if (x.get("species") or UNKNOWN) == UNKNOWN:
        reasons.append("species unknown")
    elif conf.get("species", 1.0) < threshold:
        reasons.append("species low confidence")
    return reasons


def _route_entry(key: str, x: dict, line_conf: float | None, known: dict, decisions: dict, threshold: float,
                 memo: dict) -> dict:
    verdict = decisions.get(key)
    if key not in memo:
        memo[key] = None if verdict == "reject" else match(x, known)
    m = memo[key]
    if m:
        reasons = ["ambiguous match"] if verdict != "accept" and (m.get("ambiguous_with") or m.get("warning")) else []
        return {"to": "speaker", "speaker": m["speaker"], "has_bank": bool(m["has_bank"]), "entry": key,
                "confidence": line_conf, "reasons": reasons, "source": "auto"}
    attr = {"gender": x.get("gender") or UNKNOWN, "species": x.get("species") or UNKNOWN, "age": x.get("age") or UNKNOWN}
    return _slot_route(attr, key, line_conf, _slot_reasons(x, line_conf, threshold))


def route_lines(guids: set[str], roster: list[dict], known: dict, decisions: dict,
                threshold: float = DEFAULT_THRESHOLD) -> dict[str, dict]:
    routes: dict[str, dict] = {}
    memo: dict = {}
    for conv in roster:
        entries = {x["id"]: x for x in conv["roster"]}
        for ln in conv["lines"]:
            guid = ln["key"]
            if guid not in guids or guid in routes:
                continue
            line_conf = (ln.get("conf") or {}).get("speaker")
            sid = ln["speaker"]
            if sid == NARRATOR_ID:
                routes[guid] = {"to": "narrator", "entry": None, "confidence": line_conf, "reasons": [], "source": "auto"}
            elif sid not in entries:
                routes[guid] = _slot_route(_unknown_attr(), None, line_conf, ["no roster entry"])
            else:
                routes[guid] = _route_entry(entry_key(conv["conversation"], sid), entries[sid], line_conf, known,
                                            decisions, threshold, memo)
    for guid in guids - routes.keys():
        routes[guid] = _slot_route(_unknown_attr(), None, None, ["not in roster"])
    return routes
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests/test_pools_routing.py -q`
Expected: all pass. If the ambiguity test fails because `known.match` returns no `ambiguous_with` for the test data, read `tools/npc_profile/known.py` `match()` and adjust the test's fake `known` so two names share the matched tokens (the code path is `len(best) > 1 and not all(...)`); do not change the engine.

- [ ] **Step 5: Checkpoint** (`git status --short tools/studio`; no commit unless asked)

---

### Task 2: Slot derivation

**Files:**
- Create: `tools/studio/server/studio_server/pools_slots.py`, `tools/studio/server/tests/test_pools_slots.py`

**Interfaces:**
- Consumes: routes from Task 1 (only `to == "slot"` routes with `attr`).
- Produces: `MIN_SLOT_LINES = 40`, `SLOT_PREFIX = "pool_"`, `assign_slots(routes: dict, min_lines: int = MIN_SLOT_LINES) -> dict[str, dict]`. It sets `route["slot"]` on every slot-bound route and returns `{slot_id: {"id", "name", "speaker_key", "gender", "species", "age", "lines"}}`. `speaker_key` is `pool_<id>`.

Rules: unknown gender joins the majority known gender of the same species (default `male`); a `(gender, species)` combination under `min_lines` merges into the `other` slot (id `other`, gender `any`, species `mixed`); for human slots, `old` and `young` age groups with at least `min_lines` lines of their own become separate slots `<gender>_human_<age>`.

- [ ] **Step 1: Write the failing tests**

`tests/test_pools_slots.py`:

```python
from studio_server.pools_slots import assign_slots


def r(gender="male", species="human", age="unknown"):
    return {"to": "slot", "attr": {"gender": gender, "species": species, "age": age}, "entry": "C|x",
            "confidence": 1.0, "reasons": [], "source": "auto"}


def many(n, **kw):
    return {f"g{kw.get('gender','m')}{kw.get('species','h')}{kw.get('age','a')}{i}": r(**kw) for i in range(n)}


def test_basic_slots_names_keys_and_counts():
    routes = {**many(5, gender="male"), **many(4, gender="female")}
    slots = assign_slots(routes, min_lines=3)
    assert set(slots) == {"male_human", "female_human"}
    assert slots["male_human"]["lines"] == 5 and slots["male_human"]["speaker_key"] == "pool_male_human"
    assert slots["male_human"]["name"] == "Male human"
    assert all(v["slot"] in slots for v in routes.values())


def test_unknown_gender_joins_the_majority_gender_of_its_species():
    routes = {**many(5, gender="male"), **many(2, gender="female"), **many(3, gender="unknown")}
    slots = assign_slots(routes, min_lines=2)
    assert slots["male_human"]["lines"] == 8 and slots["female_human"]["lines"] == 2


def test_unknown_gender_with_no_known_gender_defaults_to_male():
    slots = assign_slots(many(3, gender="unknown", species="machine"), min_lines=2)
    assert set(slots) == {"male_machine"}


def test_small_combinations_merge_into_other():
    routes = {**many(6, gender="male"), **many(2, gender="male", species="tyranid"), **many(1, gender="female", species="daemon")}
    slots = assign_slots(routes, min_lines=3)
    assert set(slots) == {"male_human", "other"}
    assert slots["other"]["lines"] == 3 and slots["other"]["name"] == "Other (mixed)" and slots["other"]["gender"] == "any"


def test_human_age_groups_split_only_when_big_enough():
    routes = {**many(5, gender="male"), **many(4, gender="male", age="old"), **many(1, gender="male", age="young")}
    slots = assign_slots(routes, min_lines=3)
    assert set(slots) == {"male_human", "male_human_old"}
    assert slots["male_human_old"]["lines"] == 4 and slots["male_human"]["lines"] == 6
    assert slots["male_human_old"]["name"] == "Male human, old" and slots["male_human_old"]["age"] == "old"


def test_non_slot_routes_are_ignored_and_empty_input_is_fine():
    routes = {"a": {"to": "narrator", "entry": None, "confidence": 1.0, "reasons": [], "source": "auto"}}
    assert assign_slots(routes) == {} and "slot" not in routes["a"]
    assert assign_slots({}) == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_pools_slots.py -q`
Expected: `ModuleNotFoundError: No module named 'studio_server.pools_slots'`.

- [ ] **Step 3: Implement**

`studio_server/pools_slots.py`:

```python
from __future__ import annotations

from collections import Counter

MIN_SLOT_LINES = 40
SLOT_PREFIX = "pool_"
KNOWN_GENDERS = ("male", "female")
AGE_SPLIT = ("old", "young")
OTHER_ID = "other"
DEFAULT_GENDER = "male"


def _slot_record(slot_id: str, gender: str, species: str, age: str | None, lines: int) -> dict:
    if slot_id == OTHER_ID:
        name = "Other (mixed)"
    else:
        name = f"{gender.capitalize()} {species}" + (f", {age}" if age else "")
    return {"id": slot_id, "name": name, "speaker_key": SLOT_PREFIX + slot_id, "gender": gender, "species": species,
            "age": age, "lines": lines}


def assign_slots(routes: dict, min_lines: int = MIN_SLOT_LINES) -> dict[str, dict]:
    bound = [r for r in routes.values() if r["to"] == "slot" and "attr" in r]
    if not bound:
        return {}
    by_species: dict[str, Counter] = {}
    for r in bound:
        if r["attr"]["gender"] in KNOWN_GENDERS:
            by_species.setdefault(r["attr"]["species"], Counter())[r["attr"]["gender"]] += 1

    def gender_of(r: dict) -> str:
        g = r["attr"]["gender"]
        if g in KNOWN_GENDERS:
            return g
        seen = by_species.get(r["attr"]["species"])
        return seen.most_common(1)[0][0] if seen else DEFAULT_GENDER

    combos = Counter((gender_of(r), r["attr"]["species"]) for r in bound)
    ages = Counter((gender_of(r), r["attr"]["age"]) for r in bound if r["attr"]["species"] == "human")
    slots: dict[str, dict] = {}
    for r in bound:
        g, sp, age = gender_of(r), r["attr"]["species"], r["attr"]["age"]
        if combos[(g, sp)] < min_lines:
            sid, rec = OTHER_ID, ("any", "mixed", None)
        elif sp == "human" and age in AGE_SPLIT and ages[(g, age)] >= min_lines:
            sid, rec = f"{g}_human_{age}", (g, "human", age)
        else:
            sid, rec = f"{g}_{sp}", (g, sp, None)
        r["slot"] = sid
        if sid not in slots:
            slots[sid] = _slot_record(sid, *rec, lines=0)
        slots[sid]["lines"] += 1
    return slots
```

Note for the implementer: with the age split, a `male_human` line with a small age group stays in `male_human`; `combos` counts every human line of that gender (including aged ones) for the minimum check, which is what the tests expect.

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests/test_pools_slots.py -q`
Expected: all pass. (`test_human_age_groups...` expects `male_human` = 6: 5 plain + 1 young, because `young` has 1 line, under the minimum.)

- [ ] **Step 5: Checkpoint**

---

### Task 3: Pools service and fixture repo

**Files:**
- Create: `tools/studio/server/studio_server/pools.py`, `tools/studio/server/tests/test_pools.py`
- Modify: `tools/studio/server/tests/conftest.py` (add `make_pool_repo`)

**Interfaces:**
- Consumes: Tasks 1 and 2; `speakers._jobs`, `speakers._cached`, `speakers.list_speakers`, `read_json`, `write_json_atomic`, `STATE_LOCK`, `ApiError`.
- Produces (all take `cfg` first):
  - `pools_path(cfg) -> Path` (`data/studio/pools.json`)
  - `rebuild(cfg, threshold: float | None = None, min_slot_lines: int | None = None) -> dict` (returns `summary`)
  - `summary(cfg) -> dict` with `{threshold, built, total, destinations: {narrator, speaker_bank, speaker_nobank, slot}, slots: [slot + slug + spot], queue_lines, queue_entries}`; 404 `ApiError` when not built
  - `routes_page(cfg, *, to=None, slot=None, speaker=None, queued=None, offset=0, limit=100) -> {total, items}`; items carry `guid` and `text`; `limit` is capped at `MAX_PAGE = 500`
  - `queue(cfg) -> list[{key, entry, conversation, label, name, attr, reasons, lines, samples, to, slot?, speaker?, evidence}]`, biggest first
  - `override(cfg, body) -> {changed: int}` (body: `entry` or `guids`; optional `to`, `slot`, `speaker`; no `to` means "accept the current destination")
  - `rename_slot(cfg, slot_id, name) -> slot`, `merge_slot(cfg, src, dst) -> {changed}`
  - `spot_check_sample(cfg, slot_id, seed=None) -> {slot, size, remaining, items}` and `record_spot_check(cfg, slot_id, results: dict[str, bool]) -> {checked, wrong}`
  - `ensure_slot_speakers(cfg, slots) -> int` (adds `design_manifest.json` entries named `pool_<id>`; never overwrites an entry)
  - `SPOT_CHECK_LINES = 10`, `MAX_PAGE = 500`, `SAMPLE_TEXT`

- [ ] **Step 1: Add the fixture repo**

Append to `tests/conftest.py`:

```python
def make_pool_repo(root: Path) -> Config:
    """make_repo plus unnamed lines, a harness roster, known speakers and a Heinrix prompt bank.

    Unnamed (default_speaker, priority 3) guids: u1,u2 Heinrix (has a bank); u3 Tervantias (no bank); u4 narrator;
    u5-u9 male human; u10-u12 female human; u13,u14 gender unknown (queued); u15 has no roster entry (queued).
    """
    cfg = make_repo(root)
    d = root / "data"
    extra = []
    for i in range(1, 16):
        extra.append({"guid": f"u{i}", "speaker": "default_speaker", "speaker_kind": "default_speaker",
                      "text": f"Unnamed line {i}.", "annotation": None, "priority": 3, "voice_source": "fallback"})
    with open(d / "render/jobs.jsonl", "a", encoding="utf-8") as f:
        for j in extra:
            f.write(json.dumps(j) + "\n")

    def ent(rid, name=None, gender="male", species="human", age="unknown"):
        return {"id": rid, "name": name, "label": rid.title(), "gender": gender, "species": species, "age": age,
                "conf": {"gender": 0.95, "species": 0.95, "age": 0.9}, "evidence": [f"{rid} said something"]}

    def ln(n, key, speaker, conf=1.0):
        return {"n": n, "key": key, "speaker": speaker, "conf": {"speaker": conf}}

    roster = [
        {"conversation": "C1", "roster": [ent("a", "Heinrix"), ent("b", "Tervantias")],
         "lines": [ln(0, "u1", "a"), ln(1, "u2", "a"), ln(2, "u3", "b"), ln(3, "u4", "NARRATOR")]},
        {"conversation": " C2", "roster": [ent("m"), ent("f", gender="female"), ent("q", gender="unknown")],
         "lines": ([ln(i, f"u{5 + i}", "m") for i in range(5)] + [ln(5 + i, f"u{10 + i}", "f") for i in range(3)]
                   + [ln(8, "u13", "q"), ln(9, "u14", "q"), ln(10, "u15", "ghost")])},
    ]
    put(d / "npc_profile/roster_35b_all.json", roster)
    unit = lambda name: {"speaker": {"kind": "unit", "name": name, "gender": "Male"}}
    put(d / "conversations.enGB.json", [{"lines": [unit("Heinrix")] * 5 + [unit("Tervantias the Archmachinator")] * 5}])
    prompts = json.loads((d / "voices/prompts/prompts.json").read_text(encoding="utf-8"))
    prompts["Heinrix"] = []
    put(d / "voices/prompts/prompts.json", prompts)
    return cfg


@pytest.fixture
def pcfg(tmp_path) -> Config:
    return make_pool_repo(tmp_path)
```

Run `cd tools/studio/server && python3 -m pytest tests -q` and confirm the existing 89 tests still pass (the pool fixture is separate, so `make_repo` is unchanged).

- [ ] **Step 2: Write the failing tests**

`tests/test_pools.py`:

```python
import json

import pytest

from conftest import put
from studio_server import pools
from studio_server.errors import ApiError
from studio_server.jsonio import read_json

MIN = 3     # slots need 3 lines in the fixture (the real default is 40)


def built(cfg, **kw):
    return pools.rebuild(cfg, min_slot_lines=MIN, **kw)


def state(cfg):
    return read_json(pools.pools_path(cfg), {})


def test_summary_before_build_is_a_clear_404(pcfg):
    with pytest.raises(ApiError) as e:
        pools.summary(pcfg)
    assert e.value.status == 404 and "rebuild" in e.value.message


def test_rebuild_routes_every_unnamed_line_and_counts_destinations(pcfg):
    s = built(pcfg)
    assert s["total"] == 15
    assert s["destinations"] == {"narrator": 1, "speaker_bank": 2, "speaker_nobank": 1, "slot": 11}
    ids = {x["id"]: x["lines"] for x in s["slots"]}
    assert ids == {"male_human": 8, "female_human": 3}     # u13-u15 (unknown gender, no entry) join the male majority
    assert s["queue_lines"] == 3 and s["queue_entries"] == 2


def test_rebuild_registers_each_slot_as_a_designed_speaker_once(pcfg):
    built(pcfg)
    built(pcfg)
    manifest = read_json(pcfg.voice_design / "design_manifest.json", {})
    assert manifest["pool_male_human"]["slug"] == "pool_male_human" and manifest["pool_male_human"]["candidates"] == []
    assert manifest["pool_male_human"]["description"] and manifest["pool_male_human"]["text"] == pools.SAMPLE_TEXT
    assert "Muaran" in manifest and len([k for k in manifest if k.startswith("pool_")]) == 2
    from studio_server import speakers
    names = {s["name"]: s for s in speakers.list_speakers(pcfg)}
    assert names["pool_male_human"]["origin"] == "designed"


def test_rebuild_never_discards_overrides_or_renamed_slots(pcfg):
    built(pcfg)
    pools.override(pcfg, {"guids": ["u5"], "to": "slot", "slot": "female_human"})
    pools.rename_slot(pcfg, "female_human", "Women of the Expanse")
    s = built(pcfg)
    st = state(pcfg)
    assert st["routes"]["u5"]["slot"] == "female_human" and st["routes"]["u5"]["source"] == "override"
    assert {x["id"]: x["name"] for x in s["slots"]}["female_human"] == "Women of the Expanse"


def test_rebuild_still_sees_lines_after_plan_reroutes_them(pcfg):
    path = pcfg.render / "jobs.jsonl"
    jobs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for j in jobs:
        if j["guid"] == "u1":
            j.update(speaker="Heinrix", routed_from="default_speaker", priority=1, voice_source="prompt_bank")
    path.write_text("\n".join(json.dumps(j) for j in jobs) + "\n", encoding="utf-8")
    assert built(pcfg)["total"] == 15


def test_a_rejected_match_decision_changes_the_route(pcfg):
    put(pcfg.data / "npc_profile/match_decisions.json", {"C1|a": "reject"})
    s = built(pcfg)
    assert s["destinations"]["speaker_bank"] == 0 and s["destinations"]["slot"] == 13


def test_missing_roster_is_a_clear_error_not_a_crash(pcfg):
    (pcfg.data / "npc_profile/roster_35b_all.json").unlink()      # test fixture file under tmp_path only
    with pytest.raises(ApiError) as e:
        pools.rebuild(pcfg, min_slot_lines=MIN)
    assert e.value.status == 404 and "roster" in e.value.message


def test_routes_page_filters_pages_and_caps_the_limit(pcfg):
    built(pcfg)
    page = pools.routes_page(pcfg, to="slot", slot="female_human")
    assert page["total"] == 3 and {i["guid"] for i in page["items"]} == {"u10", "u11", "u12"} and page["items"][0]["text"]
    assert pools.routes_page(pcfg, queued=True)["total"] == 3
    assert len(pools.routes_page(pcfg, limit=2)["items"]) == 2 and pools.routes_page(pcfg, offset=14, limit=5)["total"] == 15
    assert pools.routes_page(pcfg, speaker="Heinrix")["total"] == 2
    assert pools.routes_page(pcfg, limit=10_000)["limit"] == pools.MAX_PAGE


def test_queue_groups_by_roster_entry_with_evidence_and_samples(pcfg):
    built(pcfg)
    q = pools.queue(pcfg)
    by = {g["key"]: g for g in q}
    assert by[" C2|q"]["lines"] == 2 and by[" C2|q"]["reasons"] == ["gender unknown"] and by[" C2|q"]["samples"]
    assert by[" C2|q"]["evidence"] == ["q said something"] and by[" C2|q"]["slot"] == "male_human"
    assert len(q) == 2 and q[0]["lines"] >= q[1]["lines"]


def test_override_by_entry_accepts_or_moves_and_clears_the_queue(pcfg):
    built(pcfg)
    assert pools.override(pcfg, {"entry": " C2|q"}) == {"changed": 2}              # accept the current destination
    assert pools.summary(pcfg)["queue_entries"] == 1 and state(pcfg)["routes"]["u13"]["source"] == "override"
    pools.override(pcfg, {"entry": " C2|q", "to": "slot", "slot": "female_human"})
    assert state(pcfg)["routes"]["u14"]["slot"] == "female_human"
    pools.override(pcfg, {"guids": ["u5"], "to": "narrator"})
    assert state(pcfg)["routes"]["u5"]["to"] == "narrator" and "slot" not in state(pcfg)["routes"]["u5"]
    pools.override(pcfg, {"guids": ["u6"], "to": "speaker", "speaker": "Heinrix"})
    r = state(pcfg)["routes"]["u6"]
    assert r["to"] == "speaker" and r["speaker"] == "Heinrix" and r["has_bank"] is True


@pytest.mark.parametrize("body", [
    {"guids": ["u5"], "to": "slot", "slot": "no_such_slot"},
    {"guids": ["u5"], "to": "speaker", "speaker": " "},
    {"guids": ["u5"], "to": "teleport"},
    {"guids": ["nope"]},
    {"entry": "none|none"},
])
def test_bad_overrides_are_400_and_write_nothing(pcfg, body):
    built(pcfg)
    before = pools.pools_path(pcfg).read_text(encoding="utf-8")
    with pytest.raises(ApiError) as e:
        pools.override(pcfg, body)
    assert e.value.status == 400 and pools.pools_path(pcfg).read_text(encoding="utf-8") == before


def test_merge_slot_moves_every_line_and_rename_validates(pcfg):
    built(pcfg)
    assert pools.merge_slot(pcfg, "female_human", "male_human") == {"changed": 3}
    st = state(pcfg)
    assert "female_human" not in st["slots"] and st["slots"]["male_human"]["lines"] == 11
    with pytest.raises(ApiError):
        pools.merge_slot(pcfg, "male_human", "male_human")
    with pytest.raises(ApiError):
        pools.rename_slot(pcfg, "male_human", "  ")


def test_spot_check_samples_unchecked_auto_lines_and_doubles_after_a_failure(pcfg, monkeypatch):
    monkeypatch.setattr(pools, "SPOT_CHECK_LINES", 2)
    built(pcfg)
    a = pools.spot_check_sample(pcfg, "male_human", seed=1)
    assert a["size"] == 2 and len(a["items"]) == 2 and a["remaining"] == 8
    assert pools.spot_check_sample(pcfg, "male_human", seed=1) == a              # same seed, same sample
    results = {a["items"][0]["guid"]: True, a["items"][1]["guid"]: False}
    assert pools.record_spot_check(pcfg, "male_human", results) == {"checked": 2, "wrong": 1}
    b = pools.spot_check_sample(pcfg, "male_human", seed=1)
    assert b["size"] == 4 and a["items"][0]["guid"] not in {i["guid"] for i in b["items"]}
    assert "spot-check failed" in state(pcfg)["routes"][a["items"][1]["guid"]]["reasons"]
    with pytest.raises(ApiError) as e:
        pools.spot_check_sample(pcfg, "nope")
    assert e.value.status == 404
```

- [ ] **Step 3: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_pools.py -q`
Expected: `ModuleNotFoundError: No module named 'studio_server.pools'`.

- [ ] **Step 4: Implement**

`studio_server/pools.py`:

```python
from __future__ import annotations

import json
import random
import time
from collections import Counter

from . import speakers
from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic
from .pools_routing import DEFAULT_THRESHOLD, build_known, route_lines
from .pools_slots import MIN_SLOT_LINES, assign_slots

ROSTER = "data/npc_profile/roster_35b_all.json"
CONVERSATIONS = "data/conversations.enGB.json"
DECISIONS = "data/npc_profile/match_decisions.json"
SPOT_CHECK_LINES = 10
MAX_PAGE = 500
QUEUE_SAMPLES = 3
SAMPLE_TEXT = ("The augurs report nothing unusual, my lord. We should hold our position "
               "until the situation becomes clear.")
AGE_WORDS = {"old": ", in their sixties", "young": ", in their twenties"}


def pools_path(cfg: Config):
    return cfg.studio / "pools.json"


def _state(cfg: Config) -> dict:
    st = read_json(pools_path(cfg), None)
    if st is None:
        raise ApiError(404, "pools are not built yet: POST /api/pools/rebuild")
    return st


def _unnamed_jobs(cfg: Config) -> list[dict]:
    """Lines spoken by the unnamed default speaker, including ones plan.py has since rerouted (routed_from)."""
    return [j for j in speakers._jobs(cfg)
            if j.get("routed_from") == "default_speaker" or (j["speaker"] == "default_speaker" and j.get("priority") == 3)]


def _roster(cfg: Config) -> list[dict]:
    path = cfg.root / ROSTER
    if not path.is_file():
        raise ApiError(404, f"harness roster not found: {ROSTER}")
    return speakers._cached(path, lambda p: json.loads(p.read_text(encoding="utf-8")))


def _banks(cfg: Config) -> set[str]:
    return set(read_json(cfg.voices / "prompts/prompts.json", {}))


def _known(cfg: Config) -> dict:
    path = cfg.root / CONVERSATIONS
    base = speakers._cached(path, lambda p: {} if p is None else build_known(json.loads(p.read_text(encoding="utf-8")), set()))
    banks = _banks(cfg)
    return {name: {**k, "has_bank": name in banks} for name, k in base.items()}


def _count_lines(routes: dict, slots: dict) -> None:
    n = Counter(r["slot"] for r in routes.values() if r["to"] == "slot")
    for sid, s in slots.items():
        s["lines"] = n.get(sid, 0)


def _describe(s: dict) -> str:
    who = {"male": "man", "female": "woman"}.get(s["gender"], "person")
    species = "" if s["species"] in ("human", "mixed") else f" ({s['species']})"
    return f"A {who}{species}{AGE_WORDS.get(s.get('age'), '')}, British English accent, clear and neutral speaking voice."


def ensure_slot_speakers(cfg: Config, slots: dict) -> int:
    """Add a design_manifest entry per slot so it appears as a designed speaker. Existing entries are never touched."""
    path = cfg.voice_design / "design_manifest.json"
    with STATE_LOCK:
        manifest = read_json(path, {})
        added = 0
        for s in slots.values():
            name = s["speaker_key"]
            if name in manifest:
                continue
            manifest[name] = {"slug": name, "gender": "Female" if s["gender"] == "female" else "Male", "role": "pool slot",
                              "description": _describe(s), "text": SAMPLE_TEXT, "engine": "vox", "candidates": []}
            added += 1
        if added:
            write_json_atomic(path, manifest)
    return added


def rebuild(cfg: Config, threshold: float | None = None, min_slot_lines: int | None = None) -> dict:
    with STATE_LOCK:
        prev = read_json(pools_path(cfg), {})
        threshold = threshold if threshold is not None else prev.get("threshold", DEFAULT_THRESHOLD)
        min_lines = min_slot_lines if min_slot_lines is not None else prev.get("min_slot_lines", MIN_SLOT_LINES)
        guids = {j["guid"] for j in _unnamed_jobs(cfg)}
        decisions = read_json(cfg.root / DECISIONS, {})
        routes = route_lines(guids, _roster(cfg), _known(cfg), decisions, threshold)
        slots = assign_slots(routes, min_lines)
        prev_slots = prev.get("slots") or {}
        for sid, s in slots.items():
            if prev_slots.get(sid, {}).get("renamed"):
                s["name"], s["renamed"] = prev_slots[sid]["name"], True
        for guid, old in (prev.get("routes") or {}).items():       # user decisions survive a rebuild
            if old.get("source") == "override" and guid in routes:
                routes[guid] = old
                if old["to"] == "slot" and old["slot"] not in slots and old["slot"] in prev_slots:
                    slots[old["slot"]] = prev_slots[old["slot"]]
        _count_lines(routes, slots)
        write_json_atomic(pools_path(cfg), {
            "threshold": threshold, "min_slot_lines": min_lines, "built": time.strftime("%Y-%m-%d %H:%M:%S"),
            "slots": slots, "routes": routes, "spot": prev.get("spot", {})})
        ensure_slot_speakers(cfg, slots)
    return summary(cfg)


def _queued(st: dict) -> dict[str, dict]:
    return {g: r for g, r in st["routes"].items() if r["reasons"] and r["source"] == "auto"}


def _group(guid: str, r: dict) -> str:
    return r["entry"] or f"line:{guid}"


def summary(cfg: Config) -> dict:
    st = _state(cfg)
    dest = Counter()
    for r in st["routes"].values():
        dest["speaker_bank" if r["to"] == "speaker" and r.get("has_bank") else
             "speaker_nobank" if r["to"] == "speaker" else r["to"]] += 1
    by_name = {s["name"]: s["slug"] for s in speakers.list_speakers(cfg)}
    slots = [{**s, "slug": by_name.get(s["speaker_key"], s["speaker_key"]),
              "spot": st.get("spot", {}).get(sid, {"checked": 0, "wrong": 0})} for sid, s in st["slots"].items()]
    q = _queued(st)
    return {"threshold": st["threshold"], "built": st["built"], "total": len(st["routes"]),
            "destinations": {k: dest.get(k, 0) for k in ("narrator", "speaker_bank", "speaker_nobank", "slot")},
            "slots": sorted(slots, key=lambda s: -s["lines"]),
            "queue_lines": len(q), "queue_entries": len({_group(g, r) for g, r in q.items()})}


def routes_page(cfg: Config, *, to=None, slot=None, speaker=None, queued=None, offset=0, limit=100) -> dict:
    st = _state(cfg)
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))
    text = {j["guid"]: j["text"] for j in _unnamed_jobs(cfg)}
    rows = []
    for g, r in st["routes"].items():
        if to and r["to"] != to or slot and r.get("slot") != slot or speaker and r.get("speaker") != speaker:
            continue
        if queued is not None and bool(r["reasons"] and r["source"] == "auto") != bool(queued):
            continue
        rows.append({"guid": g, "text": text.get(g, ""), **r})
    return {"total": len(rows), "offset": offset, "limit": limit, "items": rows[offset:offset + limit]}


def queue(cfg: Config) -> list[dict]:
    st = _state(cfg)
    text = {j["guid"]: j["text"] for j in _unnamed_jobs(cfg)}
    index = {}
    for conv in _roster(cfg):
        for x in conv["roster"]:
            index[f"{conv['conversation']}|{x['id']}"] = (conv["conversation"], x)
    groups: dict[str, dict] = {}
    for g, r in _queued(st).items():
        key = _group(g, r)
        conv, x = index.get(r["entry"] or "", (None, {}))
        grp = groups.setdefault(key, {"key": key, "entry": r["entry"], "conversation": conv, "label": x.get("label") or "(no roster entry)",
                                      "name": x.get("name"), "attr": r.get("attr"), "reasons": [], "lines": 0, "samples": [],
                                      "to": r["to"], "slot": r.get("slot"), "speaker": r.get("speaker"),
                                      "evidence": (x.get("evidence") or [])[:QUEUE_SAMPLES]})
        grp["lines"] += 1
        grp["reasons"] = sorted(set(grp["reasons"]) | set(r["reasons"]))
        if len(grp["samples"]) < QUEUE_SAMPLES:
            grp["samples"].append(text.get(g, ""))
    return sorted(groups.values(), key=lambda g: -g["lines"])


def _targets(st: dict, body: dict) -> list[str]:
    if body.get("entry"):
        guids = [g for g, r in st["routes"].items() if r["entry"] == body["entry"]]
    else:
        guids = [g for g in body.get("guids", []) if g in st["routes"]]
    if not guids:
        raise ApiError(400, "no lines matched that entry or guid list")
    return guids


def override(cfg: Config, body: dict) -> dict:
    with STATE_LOCK:
        st = _state(cfg)
        guids = _targets(st, body)
        to_all = body.get("to")
        if to_all not in (None, "slot", "speaker", "narrator"):
            raise ApiError(400, f"unknown destination {to_all!r}")
        banks = _banks(cfg)
        updates = {}
        for g in guids:
            r = dict(st["routes"][g])
            to = to_all or r["to"]
            if to == "slot":
                sid = body.get("slot", r.get("slot"))
                if sid not in st["slots"]:
                    raise ApiError(400, f"unknown slot {sid!r}")
                r.update(to="slot", slot=sid)
                r.pop("speaker", None), r.pop("has_bank", None)
            elif to == "speaker":
                name = (body.get("speaker") or r.get("speaker") or "").strip()
                if not name:
                    raise ApiError(400, "a speaker name is required")
                r.update(to="speaker", speaker=name, has_bank=name in banks)
                r.pop("slot", None)
            else:
                r.update(to="narrator")
                r.pop("slot", None), r.pop("speaker", None), r.pop("has_bank", None)
            r.update(source="override", reasons=[])
            updates[g] = r
        st["routes"].update(updates)
        _count_lines(st["routes"], st["slots"])
        write_json_atomic(pools_path(cfg), st)
    return {"changed": len(updates)}


def rename_slot(cfg: Config, slot_id: str, name: str) -> dict:
    if not name.strip():
        raise ApiError(400, "slot name is empty")
    with STATE_LOCK:
        st = _state(cfg)
        if slot_id not in st["slots"]:
            raise ApiError(404, f"no slot {slot_id!r}")
        st["slots"][slot_id].update(name=name.strip(), renamed=True)
        write_json_atomic(pools_path(cfg), st)
        return st["slots"][slot_id]


def merge_slot(cfg: Config, src: str, dst: str) -> dict:
    with STATE_LOCK:
        st = _state(cfg)
        if src == dst or src not in st["slots"] or dst not in st["slots"]:
            raise ApiError(400, "merge needs two different existing slots")
        guids = [g for g, r in st["routes"].items() if r["to"] == "slot" and r.get("slot") == src]
        for g in guids:
            st["routes"][g].update(slot=dst, source="override", reasons=[])
        del st["slots"][src]                        # its manifest entry stays: the studio never deletes
        _count_lines(st["routes"], st["slots"])
        write_json_atomic(pools_path(cfg), st)
    return {"changed": len(guids)}


def spot_check_sample(cfg: Config, slot_id: str, seed=None) -> dict:
    st = _state(cfg)
    if slot_id not in st["slots"]:
        raise ApiError(404, f"no slot {slot_id!r}")
    spot = st.get("spot", {}).get(slot_id, {"checked": 0, "wrong": 0})
    size = SPOT_CHECK_LINES * (2 if spot["wrong"] else 1)
    pool = sorted(g for g, r in st["routes"].items()
                  if r["to"] == "slot" and r.get("slot") == slot_id and r["source"] == "auto" and not r.get("checked"))
    pick = random.Random(seed).sample(pool, min(size, len(pool)))
    text = {j["guid"]: j["text"] for j in _unnamed_jobs(cfg)}
    return {"slot": slot_id, "size": size, "remaining": len(pool),
            "items": [{"guid": g, "text": text.get(g, ""), "entry": st["routes"][g]["entry"]} for g in pick]}


def record_spot_check(cfg: Config, slot_id: str, results: dict) -> dict:
    with STATE_LOCK:
        st = _state(cfg)
        if slot_id not in st["slots"]:
            raise ApiError(404, f"no slot {slot_id!r}")
        spot = st.setdefault("spot", {}).setdefault(slot_id, {"checked": 0, "wrong": 0})
        for g, ok in results.items():
            r = st["routes"].get(g)
            if r is None or r.get("slot") != slot_id:
                continue
            r["checked"] = True
            spot["checked"] += 1
            if not ok:
                spot["wrong"] += 1
                r["reasons"] = sorted(set(r["reasons"]) | {"spot-check failed"})
        write_json_atomic(pools_path(cfg), st)
        return dict(spot)
```

- [ ] **Step 5: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests -q`
Expected: all pass (the 89 existing plus the new ones). If `test_rebuild_routes_every_unnamed_line...` shows different slot counts, print `state(pcfg)["routes"]` and check the fixture comments before changing the engine: `u13,u14` (gender unknown) and `u15` (no entry) should all land in `male_human` because male is the human majority.

- [ ] **Step 6: Checkpoint**

---

### Task 4: API routes

**Files:**
- Modify: `tools/studio/server/studio_server/routes.py`
- Create: `tools/studio/server/tests/test_pools_http.py`

**Interfaces:**
- Consumes: Task 3 functions. Produces the HTTP surface:

| Method and path | Handler |
|---|---|
| `GET /api/pools` | `pools.summary` (404 until built) |
| `POST /api/pools/rebuild` | `pools.rebuild` (body: optional `threshold`, `min_slot_lines`) |
| `GET /api/pools/routes?to=&slot=&speaker=&queued=&offset=&limit=` | `pools.routes_page` (`queued=1` or `0`) |
| `GET /api/pools/queue` | `pools.queue` |
| `POST /api/pools/routes` | `pools.override` |
| `POST /api/pools/slots/{slot}/rename` | `pools.rename_slot` (body `{name}`) |
| `POST /api/pools/slots/{slot}/merge` | `pools.merge_slot` (body `{into}`) |
| `GET /api/pools/spot-check/{slot}?seed=` | `pools.spot_check_sample` |
| `POST /api/pools/spot-check/{slot}` | `pools.record_spot_check` (body `{results: {guid: bool}}`) |

- [ ] **Step 1: Write the failing test**

`tests/test_pools_http.py` (same server fixture style as `test_http.py`, built on `pcfg`):

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/server && python3 -m pytest tests/test_pools_http.py -q`
Expected: first assertion fails (`404` for `/api/pools` is satisfied by "no route", so the failure shows at the rebuild call returning 404).

- [ ] **Step 3: Implement**

In `routes.py`, change the import line to `from . import clone, design, fx, pools, speakers, store` and, before `return r` in `build_router`, add:

```python
    def flag(v):                      # "1"/"0" in a query string; None when absent
        return None if v is None else v not in ("", "0", "false")

    r.add("GET", "/api/pools", lambda q: pools.summary(q.cfg))
    r.add("POST", "/api/pools/rebuild",
          lambda q: pools.rebuild(q.cfg, q.body.get("threshold"), q.body.get("min_slot_lines")))
    r.add("GET", "/api/pools/routes", lambda q: pools.routes_page(
        q.cfg, to=q.query.get("to"), slot=q.query.get("slot"), speaker=q.query.get("speaker"),
        queued=flag(q.query.get("queued")), offset=q.query.get("offset", 0), limit=q.query.get("limit", 100)))
    r.add("GET", "/api/pools/queue", lambda q: pools.queue(q.cfg))
    r.add("POST", "/api/pools/routes", lambda q: pools.override(q.cfg, q.body))
    r.add("POST", "/api/pools/slots/{slot}/rename", lambda q: pools.rename_slot(q.cfg, q.params["slot"], q.body.get("name", "")))
    r.add("POST", "/api/pools/slots/{slot}/merge", lambda q: pools.merge_slot(q.cfg, q.params["slot"], q.body.get("into", "")))
    r.add("GET", "/api/pools/spot-check/{slot}", lambda q: pools.spot_check_sample(q.cfg, q.params["slot"], q.query.get("seed")))
    r.add("POST", "/api/pools/spot-check/{slot}",
          lambda q: pools.record_spot_check(q.cfg, q.params["slot"], q.body.get("results", {})))
```

The route `/api/pools/routes` is registered for both GET and POST, which the router supports (it matches on method). `{slot}` matches one path segment, so slot ids must not contain `/` (they are `[a-z_]` only).

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/server && python3 -m pytest tests -q`
Expected: all pass.

- [ ] **Step 5: Smoke against the real repo, read-only**

Back up first: `cp data/studio/pools.json $S/pools.bak.json 2>/dev/null; cp data/voice_design/design_manifest.json $S/manifest.bak.json`. Do not call `rebuild` against the real data until Task 8 (it writes). Here only check the module imports: `cd tools/studio/server && python3 -c "import studio_server.routes"`.

- [ ] **Step 6: Checkpoint**

---

### Task 5: `plan.py` reads the routes

**Files:**
- Create: `tools/render_corpus/pool_routes.py`, `tools/render_corpus/tests/test_pool_routes.py`
- Modify: `tools/render_corpus/plan.py`

**Interfaces:**
- Produces: `load_routes(path=POOLS) -> dict[guid, {"narrator": bool, "speaker": str | None}]` (a missing file gives `{}`), `resolve(routes, guid, kind, speaker, is_narrator) -> (speaker, is_narrator, routed_from)`. Only lines whose speaker kind is `default_speaker` are rerouted, and a line already treated as narration stays narration.

- [ ] **Step 1: Write the failing tests**

`tools/render_corpus/tests/test_pool_routes.py`:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pool_routes import load_routes, resolve  # noqa: E402


def write(tmp_path, routes):
    p = tmp_path / "pools.json"
    p.write_text(json.dumps({"routes": routes}), encoding="utf-8")
    return p


def test_missing_file_means_no_routes(tmp_path):
    assert load_routes(tmp_path / "none.json") == {}


def test_load_maps_speakers_slots_and_narrator(tmp_path):
    p = write(tmp_path, {
        "a": {"to": "speaker", "speaker": "Heinrix"},
        "b": {"to": "slot", "slot": "male_human"},
        "c": {"to": "narrator"},
        "d": {"to": "speaker"},               # no speaker name: ignored
    })
    r = load_routes(p)
    assert r == {"a": {"narrator": False, "speaker": "Heinrix"}, "b": {"narrator": False, "speaker": "pool_male_human"},
                 "c": {"narrator": True, "speaker": None}}


def test_resolve_reroutes_only_default_speaker_lines():
    routes = {"a": {"narrator": False, "speaker": "Heinrix"}, "c": {"narrator": True, "speaker": None}}
    assert resolve(routes, "a", "default_speaker", None, False) == ("Heinrix", False, "default_speaker")
    assert resolve(routes, "c", "default_speaker", None, False) == ("narrator", True, "default_speaker")
    assert resolve(routes, "a", "unit", "Ravor", False) == ("Ravor", False, None)           # a named speaker is never rerouted
    assert resolve(routes, "a", "default_speaker", "narrator", True) == ("narrator", True, None)   # narration stays narration


def test_unrouted_lines_are_unchanged():
    assert resolve({}, "zzz", "default_speaker", None, False) == (None, False, None)
    assert resolve({"a": {"narrator": False, "speaker": "X"}}, "other", "default_speaker", None, False) == (None, False, None)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tools/render_corpus/tests/test_pool_routes.py -q` (from the repo root)
Expected: `ModuleNotFoundError: No module named 'pool_routes'`.

- [ ] **Step 3: Implement**

`tools/render_corpus/pool_routes.py`:

```python
"""Per-line voice routes for unnamed lines, written by the Voice Studio into data/studio/pools.json."""
from __future__ import annotations

import json
from pathlib import Path

POOLS = Path(__file__).resolve().parents[2] / "data/studio/pools.json"
SLOT_PREFIX = "pool_"


def load_routes(path: Path = POOLS) -> dict[str, dict]:
    if not path.is_file():
        return {}
    out: dict[str, dict] = {}
    for guid, r in (json.loads(path.read_text(encoding="utf-8")).get("routes") or {}).items():
        if r["to"] == "narrator":
            out[guid] = {"narrator": True, "speaker": None}
        elif r["to"] == "speaker" and r.get("speaker"):
            out[guid] = {"narrator": False, "speaker": r["speaker"]}
        elif r["to"] == "slot" and r.get("slot"):
            out[guid] = {"narrator": False, "speaker": SLOT_PREFIX + r["slot"]}
    return out


def resolve(routes: dict, guid: str, kind: str | None, speaker: str | None, is_narrator: bool):
    """(speaker, is_narrator, routed_from). Only the unnamed default speaker is rerouted; narration stays narration."""
    hit = routes.get(guid) if kind == "default_speaker" else None
    if hit is None or is_narrator:
        return speaker, is_narrator, None
    if hit["narrator"]:
        return "narrator", True, kind
    return hit["speaker"], False, kind
```

In `plan.py`:

1. After `from jobs import bucket_of, choose_engine, decode_binary  # noqa: E402` add: `from pool_routes import load_routes, resolve  # noqa: E402`
2. In `main()`, after `libs: dict = {}` add: `routes = load_routes()`
3. Replace
   ```python
               speaker = "narrator" if is_narrator else name
   ```
   with
   ```python
               speaker = "narrator" if is_narrator else name
               speaker, is_narrator, routed_from = resolve(routes, guid, kind, speaker, is_narrator)
   ```
4. In the job dict, after `"voice_source": source, "ref": ref,` add `**({"routed_from": routed_from} if routed_from else {}),`

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tools/render_corpus/tests/test_pool_routes.py -q && python3 -c "import ast,sys; ast.parse(open('tools/render_corpus/plan.py').read())"`
Expected: tests pass; `plan.py` parses. Do **not** run `plan.py` itself here: it rewrites `data/render/jobs.jsonl` (the real job list) and `plan.py` re-run is a decision for the user. Run `python3 -m pytest tools/render_corpus/tests -q` to confirm the other render_corpus tests still pass.

- [ ] **Step 5: Checkpoint**

---

### Task 6: Web foundation (types, client, store)

**Files:**
- Modify: `tools/studio/web/src/api/types.ts`, `tools/studio/web/src/api/client.ts`
- Create: `tools/studio/web/src/stores/pools.ts`, `tools/studio/web/src/stores/pools.test.ts`
- Modify: `tools/studio/web/src/api/client.test.ts` (add two cases)

**Interfaces:**
- Produces types `PoolSlot`, `PoolSummary`, `QueueEntry`, `PoolRoute`, `RoutesPage`, `SpotSample`; client methods `pools()`, `poolsRebuild(body?)`, `poolRoutes(params)`, `poolQueue()`, `poolOverride(body)`, `poolRename(slot, name)`, `poolMerge(slot, into)`, `poolSpot(slot, seed?)`, `poolSpotRecord(slot, results)`; store `usePoolsStore()` with `summary`, `queue`, `loading`, `error`, `notBuilt`, `load()`, `rebuild()`, `accept(entry)`, `move(entry, target)`.

- [ ] **Step 1: Write the failing tests**

Add to `src/api/client.test.ts` (inside the existing `describe`):

```ts
  it('calls the pool endpoints', async () => {
    const f = mockFetch(200, {})
    await api.pools()
    await api.poolRoutes({ to: 'slot', slot: 'male_human', limit: 50 })
    await api.poolOverride({ entry: 'C|a', to: 'slot', slot: 'male_human' })
    expect(f.mock.calls[0][0]).toBe('/api/pools')
    expect(f.mock.calls[1][0]).toBe('/api/pools/routes?to=slot&slot=male_human&limit=50')
    expect(f.mock.calls[2][0]).toBe('/api/pools/routes')
    expect(JSON.parse(f.mock.calls[2][1].body)).toMatchObject({ entry: 'C|a' })
  })
```

`src/stores/pools.test.ts`:

```ts
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError, api } from '../api/client'
import { usePoolsStore } from './pools'

vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: { pools: vi.fn(), poolQueue: vi.fn(), poolsRebuild: vi.fn(), poolOverride: vi.fn() },
}))

const summary = { threshold: 0.8, built: 'now', total: 3, destinations: { narrator: 0, speaker_bank: 1, speaker_nobank: 1, slot: 1 }, slots: [], queue_lines: 1, queue_entries: 1 }

describe('pools store', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('loads the summary and queue', async () => {
    vi.mocked(api.pools).mockResolvedValue(summary as never)
    vi.mocked(api.poolQueue).mockResolvedValue([{ key: 'C|a' }] as never)
    const s = usePoolsStore()
    await s.load()
    expect(s.summary?.total).toBe(3)
    expect(s.queue).toHaveLength(1)
    expect(s.notBuilt).toBe(false)
  })

  it('flags not-built on a 404 instead of showing an error', async () => {
    vi.mocked(api.pools).mockRejectedValue(new ApiRequestError(404, 'pools are not built yet'))
    const s = usePoolsStore()
    await s.load()
    expect(s.notBuilt).toBe(true)
    expect(s.error).toBeNull()
  })

  it('rebuild reloads, accept and move call the override endpoint and reload', async () => {
    vi.mocked(api.poolsRebuild).mockResolvedValue(summary as never)
    vi.mocked(api.pools).mockResolvedValue(summary as never)
    vi.mocked(api.poolQueue).mockResolvedValue([] as never)
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 2 } as never)
    const s = usePoolsStore()
    await s.rebuild()
    await s.accept('C|a')
    await s.move('C|a', { to: 'slot', slot: 'female_human' })
    expect(api.poolOverride).toHaveBeenNthCalledWith(1, { entry: 'C|a' })
    expect(api.poolOverride).toHaveBeenNthCalledWith(2, { entry: 'C|a', to: 'slot', slot: 'female_human' })
    expect(api.pools).toHaveBeenCalledTimes(3)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/web && npx vitest run src/stores/pools.test.ts src/api/client.test.ts`
Expected: FAIL (`./pools` not found; `api.pools` is not a function).

- [ ] **Step 3: Implement**

Append to `src/api/types.ts`:

```ts
export type PoolTarget = 'speaker' | 'narrator' | 'slot'

export interface PoolSlot {
  id: string
  name: string
  speaker_key: string
  slug: string
  gender: string
  species: string
  age: string | null
  lines: number
  spot: { checked: number; wrong: number }
}

export interface PoolSummary {
  threshold: number
  built: string
  total: number
  destinations: { narrator: number; speaker_bank: number; speaker_nobank: number; slot: number }
  slots: PoolSlot[]
  queue_lines: number
  queue_entries: number
}

export interface QueueEntry {
  key: string
  entry: string | null
  conversation: string | null
  label: string
  name: string | null
  attr: { gender: string; species: string; age: string } | null
  reasons: string[]
  lines: number
  samples: string[]
  to: PoolTarget
  slot?: string | null
  speaker?: string | null
  evidence: string[]
}

export interface PoolRoute {
  guid: string
  text: string
  to: PoolTarget
  speaker?: string
  has_bank?: boolean
  slot?: string
  entry: string | null
  confidence: number | null
  reasons: string[]
  source: 'auto' | 'override'
}

export interface RoutesPage {
  total: number
  offset: number
  limit: number
  items: PoolRoute[]
}

export interface SpotSample {
  slot: string
  size: number
  remaining: number
  items: { guid: string; text: string; entry: string | null }[]
}

export interface OverrideBody {
  entry?: string
  guids?: string[]
  to?: PoolTarget
  slot?: string
  speaker?: string
}
```

In `src/api/client.ts`, extend the type import with `OverrideBody, PoolSummary, QueueEntry, RoutesPage, SpotSample` and add inside `api`:

```ts
  pools: () => request<PoolSummary>('/api/pools'),
  poolsRebuild: (body: { threshold?: number } = {}) => post<PoolSummary>('/api/pools/rebuild', body),
  poolRoutes: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = Object.entries(params).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
    return request<RoutesPage>(`/api/pools/routes${qs ? `?${qs}` : ''}`)
  },
  poolQueue: () => request<QueueEntry[]>('/api/pools/queue'),
  poolOverride: (body: OverrideBody) => post<{ changed: number }>('/api/pools/routes', body),
  poolRename: (slot: string, name: string) => post<object>(`/api/pools/slots/${encodeURIComponent(slot)}/rename`, { name }),
  poolMerge: (slot: string, into: string) => post<{ changed: number }>(`/api/pools/slots/${encodeURIComponent(slot)}/merge`, { into }),
  poolSpot: (slot: string, seed?: number) => request<SpotSample>(`/api/pools/spot-check/${encodeURIComponent(slot)}${seed === undefined ? '' : `?seed=${seed}`}`),
  poolSpotRecord: (slot: string, results: Record<string, boolean>) => post<{ checked: number; wrong: number }>(`/api/pools/spot-check/${encodeURIComponent(slot)}`, { results }),
```

`src/stores/pools.ts`:

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiRequestError, api } from '../api/client'
import type { OverrideBody, PoolSummary, QueueEntry } from '../api/types'

const NOT_FOUND = 404

export const usePoolsStore = defineStore('pools', () => {
  const summary = ref<PoolSummary | null>(null)
  const queue = ref<QueueEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const notBuilt = computed(() => summary.value === null && error.value === null && !loading.value && loaded.value)
  const loaded = ref(false)

  async function load() {
    loading.value = true
    error.value = null
    try {
      summary.value = await api.pools()
      queue.value = await api.poolQueue()
    } catch (e) {
      summary.value = null
      queue.value = []
      if (!(e instanceof ApiRequestError && e.status === NOT_FOUND)) error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
      loaded.value = true
    }
  }
  async function rebuild() {
    error.value = null
    try {
      await api.poolsRebuild()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return
    }
    await load()
  }
  async function apply(body: OverrideBody) {
    try {
      await api.poolOverride(body)
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return
    }
    await load()
  }
  const accept = (entry: string) => apply({ entry })
  const move = (entry: string, target: Pick<OverrideBody, 'to' | 'slot' | 'speaker'>) => apply({ entry, ...target })

  return { summary, queue, loading, error, notBuilt, load, rebuild, accept, move }
})
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`
Expected: all pass; type check clean. (`notBuilt` depends on `loaded`, which is declared after the computed; hoisting is fine because the computed runs lazily.)

- [ ] **Step 5: Checkpoint**

---

### Task 7: Pools view and components

**Files:**
- Create: `src/components/pools/RoutingSummary.vue`, `SlotList.vue`, `QueuePanel.vue`, `SpotCheck.vue`, `src/views/PoolsView.vue`; tests `RoutingSummary.test.ts`, `SlotList.test.ts`, `QueuePanel.test.ts`, `SpotCheck.test.ts`, `src/views/PoolsView.test.ts`
- Modify: `src/router.ts` (add `/pools`), `src/components/shared/AppShell.vue` (nav link "Pools")

**Interfaces:**
- Consumes: Task 6 types, client and store; `SectionCard`, `EmptyState`.
- Produces: `<RoutingSummary :summary />`; `<SlotList :slots @rename="(id, name)" />` (each row links to `/speakers/<slug>`); `<QueuePanel :entries :slots @accept="(entry)" @move="(entry, target)" />` with a destination select per entry (every slot plus "narrator"); `<SpotCheck :slot />` (loads a sample, ✓ / ✗ per line, Submit records results); `PoolsView` (thin: loads the store on mount, shows a Build button when `notBuilt`).

- [ ] **Step 1: Write the failing tests**

`src/components/pools/RoutingSummary.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RoutingSummary from './RoutingSummary.vue'

const summary = { threshold: 0.8, built: 'now', total: 6717, destinations: { narrator: 138, speaker_bank: 1911, speaker_nobank: 2947, slot: 1863 }, slots: [], queue_lines: 556, queue_entries: 92 }

describe('RoutingSummary', () => {
  it('shows each destination with its count and the queue size', () => {
    const t = mount(RoutingSummary, { props: { summary } }).text()
    for (const n of ['6717', '138', '1911', '2947', '1863', '92']) expect(t).toContain(n)
    expect(t).toMatch(/real voice bank/i)
    expect(t).toMatch(/named NPC/i)
  })
})
```

`src/components/pools/SlotList.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import SlotList from './SlotList.vue'

const slots = [{ id: 'male_human', name: 'Male human', speaker_key: 'pool_male_human', slug: 'pool_male_human', gender: 'male', species: 'human', age: null, lines: 1300, spot: { checked: 4, wrong: 1 } }]
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/speakers/:slug', component: { template: '<i/>' } }] })

describe('SlotList', () => {
  it('lists slots with counts, spot-check progress and a link to the slot page', () => {
    const w = mount(SlotList, { props: { slots }, global: { plugins: [router] } })
    expect(w.text()).toContain('Male human')
    expect(w.text()).toContain('1300')
    expect(w.text()).toContain('4 checked')
    expect(w.find('a').attributes('href')).toBe('/speakers/pool_male_human')
  })

  it('emits rename with the new name', async () => {
    const w = mount(SlotList, { props: { slots }, global: { plugins: [router] } })
    await w.find('[data-rename]').trigger('click')
    await w.find('input').setValue('Dockhands')
    await w.find('[data-save-name]').trigger('click')
    expect(w.emitted('rename')![0]).toEqual(['male_human', 'Dockhands'])
  })

  it('shows an empty state with no slots', () => {
    expect(mount(SlotList, { props: { slots: [] }, global: { plugins: [router] } }).text()).toMatch(/no slots/i)
  })
})
```

`src/components/pools/QueuePanel.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import QueuePanel from './QueuePanel.vue'

const entries = [{ key: 'C|q', entry: 'C|q', conversation: 'C', label: 'Q', name: null, attr: { gender: 'unknown', species: 'human', age: 'unknown' },
  reasons: ['gender unknown'], lines: 4, samples: ['Hello there.'], to: 'slot', slot: 'male_human', speaker: null, evidence: ['said something'] }]
const slots = [{ id: 'male_human', name: 'Male human' }, { id: 'female_human', name: 'Female human' }]

describe('QueuePanel', () => {
  it('shows the entry, why it is queued, its lines and a sample', () => {
    const t = mount(QueuePanel, { props: { entries: entries as never, slots: slots as never } }).text()
    expect(t).toContain('gender unknown')
    expect(t).toContain('4 lines')
    expect(t).toContain('Hello there.')
  })

  it('accepts an entry', async () => {
    const w = mount(QueuePanel, { props: { entries: entries as never, slots: slots as never } })
    await w.find('[data-accept]').trigger('click')
    expect(w.emitted('accept')![0]).toEqual(['C|q'])
  })

  it('moves an entry to another slot or the narrator', async () => {
    const w = mount(QueuePanel, { props: { entries: entries as never, slots: slots as never } })
    await w.find('select').setValue('slot:female_human')
    await w.find('[data-move]').trigger('click')
    expect(w.emitted('move')![0]).toEqual(['C|q', { to: 'slot', slot: 'female_human' }])
    await w.find('select').setValue('narrator')
    await w.find('[data-move]').trigger('click')
    expect(w.emitted('move')![1]).toEqual(['C|q', { to: 'narrator' }])
  })

  it('shows an empty state when nothing needs review', () => {
    expect(mount(QueuePanel, { props: { entries: [], slots: [] } }).text()).toMatch(/nothing needs review/i)
  })
})
```

`src/components/pools/SpotCheck.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'

vi.mock('../../api/client', () => ({ api: { poolSpot: vi.fn(), poolSpotRecord: vi.fn() } }))

import SpotCheck from './SpotCheck.vue'

describe('SpotCheck', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads a sample, records ok/wrong per line and reports the result', async () => {
    vi.mocked(api.poolSpot).mockResolvedValue({ slot: 'male_human', size: 2, remaining: 5, items: [{ guid: 'u1', text: 'One.', entry: null }, { guid: 'u2', text: 'Two.', entry: null }] })
    vi.mocked(api.poolSpotRecord).mockResolvedValue({ checked: 2, wrong: 1 })
    const w = mount(SpotCheck, { props: { slotId: 'male_human' } })
    await flushPromises()
    expect(w.text()).toContain('One.')
    await w.findAll('[data-ok]')[0].trigger('click')
    await w.findAll('[data-wrong]')[1].trigger('click')
    await w.find('[data-submit]').trigger('click')
    await flushPromises()
    expect(api.poolSpotRecord).toHaveBeenCalledWith('male_human', { u1: true, u2: false })
    expect(w.text()).toContain('1 wrong')
  })

  it('does not submit until every line has a verdict', async () => {
    vi.mocked(api.poolSpot).mockResolvedValue({ slot: 's', size: 1, remaining: 1, items: [{ guid: 'u1', text: 'One.', entry: null }] })
    const w = mount(SpotCheck, { props: { slotId: 's' } })
    await flushPromises()
    expect(w.find('[data-submit]').attributes('disabled')).toBeDefined()
  })

  it('shows an empty state when the slot has nothing left to check', async () => {
    vi.mocked(api.poolSpot).mockResolvedValue({ slot: 's', size: 10, remaining: 0, items: [] })
    const w = mount(SpotCheck, { props: { slotId: 's' } })
    await flushPromises()
    expect(w.text()).toMatch(/nothing left/i)
  })
})
```

`src/views/PoolsView.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { ApiRequestError, api } from '../api/client'

vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: { pools: vi.fn(), poolQueue: vi.fn(), poolsRebuild: vi.fn(), poolOverride: vi.fn(), poolRename: vi.fn(), poolSpot: vi.fn() },
}))

import PoolsView from './PoolsView.vue'

const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/speakers/:slug', component: { template: '<i/>' } }] })
const summary = { threshold: 0.8, built: 'now', total: 3, destinations: { narrator: 0, speaker_bank: 1, speaker_nobank: 1, slot: 1 },
  slots: [{ id: 'male_human', name: 'Male human', speaker_key: 'pool_male_human', slug: 'pool_male_human', gender: 'male', species: 'human', age: null, lines: 1, spot: { checked: 0, wrong: 0 } }], queue_lines: 0, queue_entries: 0 }

describe('PoolsView', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('offers to build the pools when they do not exist yet', async () => {
    vi.mocked(api.pools).mockRejectedValue(new ApiRequestError(404, 'pools are not built yet'))
    const w = mount(PoolsView, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toMatch(/not built/i)
    vi.mocked(api.poolsRebuild).mockResolvedValue(summary as never)
    vi.mocked(api.pools).mockResolvedValue(summary as never)
    vi.mocked(api.poolQueue).mockResolvedValue([])
    await w.find('[data-build]').trigger('click')
    await flushPromises()
    expect(api.poolsRebuild).toHaveBeenCalled()
    expect(w.text()).toContain('Male human')
  })

  it('shows the summary, the slots and an empty queue', async () => {
    vi.mocked(api.pools).mockResolvedValue(summary as never)
    vi.mocked(api.poolQueue).mockResolvedValue([])
    const w = mount(PoolsView, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toContain('Male human')
    expect(w.text()).toMatch(/nothing needs review/i)
  })

  it('shows an error message when the load fails', async () => {
    vi.mocked(api.pools).mockRejectedValue(new Error('boom'))
    const w = mount(PoolsView, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toContain('boom')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/web && npx vitest run src/components/pools src/views/PoolsView.test.ts`
Expected: FAIL, components not found.

- [ ] **Step 3: Implement**

`src/components/pools/RoutingSummary.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { PoolSummary } from '../../api/types'

const props = defineProps<{ summary: PoolSummary }>()
const rows = computed(() => [
  { key: 'speaker_bank', label: 'Known speaker with a real voice bank', note: 'companion lines exported without a speaker tag', n: props.summary.destinations.speaker_bank },
  { key: 'speaker_nobank', label: 'Known named NPC without a bank', note: 'needs its own designed voice (Speakers section)', n: props.summary.destinations.speaker_nobank },
  { key: 'narrator', label: 'Narrator', note: 'narration and unattributed text', n: props.summary.destinations.narrator },
  { key: 'slot', label: 'Shared slot voice', note: 'genuinely anonymous characters', n: props.summary.destinations.slot },
])
</script>

<template>
  <div>
    <p class="dim">{{ summary.total }} unnamed lines routed · built {{ summary.built }} · threshold {{ summary.threshold }}</p>
    <div v-for="r in rows" :key="r.key" class="row">
      <b class="n">{{ r.n }}</b>
      <span>{{ r.label }}</span>
      <span class="dim">{{ r.note }}</span>
    </div>
    <p class="dim">{{ summary.queue_entries }} roster entries ({{ summary.queue_lines }} lines) need a look.</p>
  </div>
</template>

<style scoped>
.row { display: flex; gap: 10px; align-items: baseline; padding: 3px 0; }
.n { min-width: 56px; text-align: right; color: var(--acc); }
.dim { color: var(--dim); font-size: 12px; }
</style>
```

`src/components/pools/SlotList.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import type { PoolSlot } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'

defineProps<{ slots: PoolSlot[] }>()
const emit = defineEmits<{ rename: [id: string, name: string] }>()
const editing = ref<string | null>(null)
const draft = ref('')

function edit(s: PoolSlot) {
  editing.value = s.id
  draft.value = s.name
}
function save(id: string) {
  emit('rename', id, draft.value)
  editing.value = null
}
</script>

<template>
  <EmptyState v-if="!slots.length" message="No slots yet. Build the pools first." />
  <div v-for="s in slots" :key="s.id" class="slot">
    <template v-if="editing === s.id">
      <input v-model="draft" />
      <button data-save-name @click="save(s.id)">Save</button>
    </template>
    <template v-else>
      <RouterLink :to="`/speakers/${s.slug}`">{{ s.name }}</RouterLink>
      <button data-rename title="rename" @click="edit(s)">rename</button>
    </template>
    <span class="dim">{{ s.lines }} lines</span>
    <span class="dim">{{ s.spot.checked }} checked<template v-if="s.spot.wrong">, {{ s.spot.wrong }} wrong</template></span>
  </div>
</template>

<style scoped>
.slot { display: flex; gap: 10px; align-items: center; padding: 4px 0; border-top: 1px solid var(--line); }
.dim { color: var(--dim); font-size: 12px; }
</style>
```

`src/components/pools/QueuePanel.vue`:

```vue
<script setup lang="ts">
import { reactive } from 'vue'
import type { OverrideBody, PoolSlot, QueueEntry } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'

const NARRATOR = 'narrator'
const props = defineProps<{ entries: QueueEntry[]; slots: Pick<PoolSlot, 'id' | 'name'>[] }>()
const emit = defineEmits<{ accept: [entry: string]; move: [entry: string, target: Pick<OverrideBody, 'to' | 'slot'>] }>()
const choice = reactive<Record<string, string>>({})

const current = (e: QueueEntry) => choice[e.key] ?? (e.slot ? `slot:${e.slot}` : NARRATOR)
function move(e: QueueEntry) {
  if (!e.entry) return
  const v = current(e)
  emit('move', e.entry, v === NARRATOR ? { to: 'narrator' } : { to: 'slot', slot: v.slice('slot:'.length) })
}
</script>

<template>
  <EmptyState v-if="!props.entries.length" message="Nothing needs review." />
  <div v-for="e in props.entries" :key="e.key" class="entry">
    <div class="head">
      <b>{{ e.name ?? e.label }}</b>
      <span class="dim">{{ e.lines }} lines</span>
      <span v-for="r in e.reasons" :key="r" class="chip">{{ r }}</span>
      <span v-if="e.attr" class="dim">{{ e.attr.gender }} {{ e.attr.species }} {{ e.attr.age }}</span>
    </div>
    <p v-for="s in e.samples" :key="s" class="sample">“{{ s }}”</p>
    <p v-if="e.evidence.length" class="dim">evidence: {{ e.evidence.join(' · ') }}</p>
    <div class="acts">
      <button data-accept :disabled="!e.entry" @click="e.entry && emit('accept', e.entry)">Accept {{ e.slot ?? e.to }}</button>
      <select :value="current(e)" @change="choice[e.key] = ($event.target as HTMLSelectElement).value">
        <option v-for="s in props.slots" :key="s.id" :value="`slot:${s.id}`">{{ s.name }}</option>
        <option :value="NARRATOR">narrator</option>
      </select>
      <button data-move :disabled="!e.entry" @click="move(e)">Move</button>
    </div>
  </div>
</template>

<style scoped>
.entry { border-top: 1px solid var(--line); padding: 8px 0; }
.head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.chip { border: 1px solid #f0b400; color: #f0b400; border-radius: 10px; padding: 0 7px; font-size: 11px; }
.sample { margin: 3px 0; }
.acts { display: flex; gap: 8px; margin-top: 4px; }
.dim { color: var(--dim); font-size: 12px; }
</style>
```

(The test selects the second slot by `setValue('slot:female_human')`, so option values use the `slot:<id>` form; the narrator option value is `narrator`.)

`src/components/pools/SpotCheck.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../../api/client'
import type { SpotSample } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'

const props = defineProps<{ slotId: string }>()
const sample = ref<SpotSample | null>(null)
const verdicts = reactive<Record<string, boolean>>({})
const result = ref('')
const error = ref('')

const complete = computed(() => !!sample.value?.items.length && sample.value.items.every((i) => i.guid in verdicts))

async function load() {
  error.value = ''
  try {
    sample.value = await api.poolSpot(props.slotId)
    for (const k of Object.keys(verdicts)) delete verdicts[k]
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}
async function submit() {
  try {
    const r = await api.poolSpotRecord(props.slotId, { ...verdicts })
    result.value = `${r.checked} checked, ${r.wrong} wrong`
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}
onMounted(load)
</script>

<template>
  <div>
    <p v-if="error" class="err">{{ error }}</p>
    <EmptyState v-if="sample && !sample.items.length" message="Nothing left to check in this slot." />
    <div v-for="i in sample?.items ?? []" :key="i.guid" class="line">
      <span class="text">{{ i.text }}</span>
      <button data-ok :class="{ on: verdicts[i.guid] === true }" @click="verdicts[i.guid] = true">✓</button>
      <button data-wrong :class="{ on: verdicts[i.guid] === false }" @click="verdicts[i.guid] = false">✗</button>
    </div>
    <button v-if="sample?.items.length" data-submit :disabled="!complete" @click="submit">Submit {{ sample.items.length }} checks</button>
    <span class="dim">{{ result }}</span>
  </div>
</template>

<style scoped>
.line { display: flex; gap: 8px; align-items: center; padding: 3px 0; }
.text { flex: 1; }
button.on { background: var(--acc); color: #0b1220; border-color: var(--acc); }
.err { color: var(--bad); }
.dim { color: var(--dim); font-size: 12px; margin-left: 8px; }
</style>
```

`src/views/PoolsView.vue`:

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { api } from '../api/client'
import EmptyState from '../components/shared/EmptyState.vue'
import SectionCard from '../components/shared/SectionCard.vue'
import QueuePanel from '../components/pools/QueuePanel.vue'
import RoutingSummary from '../components/pools/RoutingSummary.vue'
import SlotList from '../components/pools/SlotList.vue'
import { usePoolsStore } from '../stores/pools'

const pools = usePoolsStore()
onMounted(pools.load)

async function rename(id: string, name: string) {
  await api.poolRename(id, name)
  await pools.load()
}
</script>

<template>
  <div>
    <h1>Pools</h1>
    <p v-if="pools.error" class="err">{{ pools.error }}</p>
    <template v-if="pools.notBuilt">
      <EmptyState message="The pools are not built yet. Building routes every unnamed line and registers the slots as designed speakers." />
      <button data-build class="primary" @click="pools.rebuild">Build pools</button>
    </template>
    <template v-else-if="pools.summary">
      <SectionCard title="1. Where the unnamed lines go">
        <RoutingSummary :summary="pools.summary" />
        <button data-rebuild @click="pools.rebuild">Rebuild (keeps your decisions)</button>
      </SectionCard>
      <SectionCard title="2. Slots"><SlotList :slots="pools.summary.slots" @rename="rename" /></SectionCard>
      <SectionCard title="3. Needs review (by roster entry)">
        <QueuePanel :entries="pools.queue" :slots="pools.summary.slots" @accept="pools.accept" @move="pools.move" />
      </SectionCard>
    </template>
    <EmptyState v-else-if="pools.loading" message="Loading…" />
  </div>
</template>

<style scoped>
h1 { font-size: 18px; margin: 0 0 8px; }
.primary { background: var(--acc); color: #0b1220; border-color: var(--acc); }
.err { color: var(--bad); }
</style>
```

The spot check is rendered inside a slot's own section: add to `SlotList.vue` a `data-spot` toggle per slot that shows `<SpotCheck :slot-id="s.id" />` below the row (a `ref<string|null>` named `checking`; import `SpotCheck`). Add this to the SlotList test: clicking `[data-spot]` renders the `SpotCheck` component (stub the API with `vi.mock`).

In `src/router.ts` add `import PoolsView from './views/PoolsView.vue'` and `{ path: '/pools', component: PoolsView },` to the routes. In `AppShell.vue` add `<nav><RouterLink to="/speakers">Speakers</RouterLink> <RouterLink to="/pools">Pools</RouterLink></nav>`.

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit && npm run build`
Expected: all pass; type check clean; build succeeds.

- [ ] **Step 5: Checkpoint**

---

### Task 8: Integration, real-data pass, docs, review

**Files:**
- Modify: `tools/studio/README.md`, `CLAUDE.md` (Voice Studio section), `docs/superpowers/specs/2026-10-09-voice-studio-pools-design.md` (record any deviations)

- [ ] **Step 1: Full automated pass**

Run:
```bash
cd tools/studio/server && python3 -m pytest tests -q
cd ../web && npx vitest run && npx vue-tsc --noEmit && npm run build
cd ../../.. && python3 -m pytest tools/render_corpus/tests tools/voice_design/tests -q
```
Expected: everything green.

- [ ] **Step 2: Real-data pass with the model off**

Back up first (scratchpad): `data/studio/pools.json` (may not exist), `data/studio/_slugs.json`, `data/voice_design/design_manifest.json`, `data/voices/prompts/prompts.json`, `data/render/jobs.jsonl`. Restart the server, then with Playwright MCP on http://127.0.0.1:8930/pools:

1. The page offers "Build pools". Click it.
2. Check the routing summary against the spec (section 2), within ±3%: known speaker with bank about 1,900, without bank about 2,900, narrator about 140, slot about 1,860, total 6,717.
3. The slot list shows 6 to 8 slots; the largest is "Male human" with about 1,300 lines.
4. The queue shows about 92 roster entries (about 560 lines).
5. Accept one entry: the queue count drops by one and `pools.json` shows `source: override` for its lines. Click Rebuild: that override survives.
6. Open a slot link: the Speakers page for `pool_male_human` loads as a designed speaker with no candidates and the model controls disabled with the reason.
7. Spot check: open a slot's spot check, mark lines ok, submit; the "checked" count updates.
8. Compare: `design_manifest.json` gained only `pool_*` entries; `prompts.json` and `jobs.jsonl` are byte-identical to the backups; the three voice-design files from slice 1 are unchanged.

If a count is far outside the spec, stop and debug with the Task 1 engine on the real data (print the destination counts and compare with the spec's checking script) before touching the UI.

- [ ] **Step 3: Docs**

Add a "Pools" paragraph to `tools/studio/README.md` (what it does, `pools.json`, the Rebuild button, that `plan.py` needs a re-run for the routes to take effect and that the re-run is the user's call). Add the Pools section's key points to the Voice Studio section of `CLAUDE.md` (what routes where, `data/studio/pools.json`, the `plan.py` rule, slots are `pool_<id>` designed speakers). Note any deviations from the spec in the spec file.

- [ ] **Step 4: Independent review**

Dispatch a fresh reviewer (a subagent on the most capable model) to read the new server, web and `plan.py` changes against the spec, with the Review Focus section verbatim, the ledger of rulings and the note that tests and implementation were written together. Triage the findings by user effect, fix Critical and Important in one pass test-first, and ledger the minors.

- [ ] **Step 5: Final checkpoint**

Run `git status --short` and list what is new. Ask the owner whether to commit. Leave the studio server running for the owner's trial.

---

## Self-Review

**Spec coverage** (spec section to task): 2 data facts, routing table and `match_decisions` wiring: Tasks 1, 3 (decisions read in `rebuild`), 8 (counts check). 3.1 policy A, provenance: Tasks 1, 3 (`source`, `confidence`). 3.2 routing order and rejected fall-through: Task 1. 3.3 queue axes and unknown age: Task 1 tests. 3.4 per-entry review: Task 3 `queue` and `override(entry)`, Task 7 `QueuePanel`. 3.5 threshold and spot check with doubling: Tasks 3, 7. 3.6 no-entry lines: Task 1 (`no roster entry` to a human slot plus queue). 3.7 slot derivation, rename, merge: Tasks 2, 3. 3.8 slot is a profile: Task 3 `ensure_slot_speakers`, Task 4 test through the speaker routes. 3.9 FX per slot: **gap by design**: slot FX defaults come from the harness categories, but the Pools slice stores no FX default; the user picks presets on the slot's own Speakers page (Post-processing), which already exists. Spec section 4 (`pools.json`, `plan.py` rule, `speaker_key`): Tasks 3, 5. Section 5 UI: Task 7 (routing summary, slot list, queue, spot check; the lines-by-destination table with filters is the `routes` endpoint in Task 3 and 4 but **has no UI in this plan**: the view shows summary, slots, queue and spot check, and the filtered line browser is left for a follow-up; the spec's mention of it in section 5 should be trimmed accordingly). Section 6 API: Task 4. Section 7 blocked items: Task 8 notes. Section 8 testing: each task.

**Placeholder scan:** no `TBD` or `TODO`. The one soft spot is Task 1 step 4's note that the ambiguity test depends on `known.match` behaviour; it tells the implementer what to adjust.

**Type consistency:** route record fields `to`, `speaker`, `has_bank`, `slot`, `attr`, `entry`, `confidence`, `reasons`, `source` are the same in Tasks 1, 3, 5 (`pool_routes.load_routes` reads `to`, `speaker`, `slot`) and in the web `PoolRoute`. Slot records `id, name, speaker_key, gender, species, age, lines` match between Task 2, Task 3 `summary` (adds `slug`, `spot`) and `PoolSlot`. `queue` groups carry `key, entry, conversation, label, name, attr, reasons, lines, samples, to, slot, speaker, evidence`, matching `QueueEntry`. `override` bodies `entry | guids`, `to`, `slot`, `speaker` match `OverrideBody`.

**Review Focus coverage:** 1 overrides survive: Task 3 `test_rebuild_never_discards_overrides_or_renamed_slots` and the manifest-once test. 2 rejected match: Task 1. 3 bad input and missing roster or unbuilt pools: Task 3 tests (400s, 404s) and Task 4. 4 rerouted lines: Task 3 `test_rebuild_still_sees_lines_after_plan_reroutes_them`. 5 large lists: Task 3 `MAX_PAGE` test; the web list does not render per-line rows at all in this plan, so no unpaged list exists. 6 unrouted lines unchanged: Task 5 `test_unrouted_lines_are_unchanged`.
