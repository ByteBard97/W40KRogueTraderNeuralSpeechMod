# Multi-Speaker Cue Segments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one dialogue cue be split into ordered segments, each with its own speaker (character or narrator), rendered in that speaker's voice and stitched back into the single wav the game bank expects.

**Architecture:** A hand-checked annotation file (`data/npc_profile/segments.json`, keyed by the cue's `text_key`) lists `{speaker, kind, text}` segments per cue. A guard proves the segments cover the cue text. A new planner turns annotated cues into segment jobs (`<guid>~a<k>`) in its own jobs file; the existing `render.py`, `asr_check.py`, `stitch_mixed.py` and `overlay_export.py` run on those jobs unchanged. Stitching into one clip is chosen over runtime back-to-back playback because the game plays one Wwise event per cue and we do not want new game-side mod code.

**Tech Stack:** Python 3 (system `python3`, pytest), existing `tools/render_corpus` modules (`plan.py`, `mixed.py`, `stitch.py`).

**Spec:** none written; requirements come from the 2026-10-11 session (user: multi-speaker cues "ABSOLUTELY need" to be split, documented per segment, rendered per speaker, then merged or played back to back; whichever is more parsimonious). Related: `tools/render_corpus/plan_mixed.py` (speech + `{n}` narration, already built), `TODO.md` section "Known bad scene", `data/npc_profile/review/claude_all.json` (reviewer output for the 73 flagged conversations).

## Global Constraints

- Never `git push`. Commits are local, only when the user has asked, with no Claude/AI attribution or trailers (global CLAUDE.md overrides the harness reminder).
- Never delete or overwrite existing data. New files only. Do not touch `data/render/jobs.jsonl`, `data/render/jobs_mixed.jsonl`, or the `mixed-seg` run (a queue may still be using them). Do not run `plan.py` (it rewrites `jobs.jsonl`; ask first).
- No GPU jobs unless the user says so (renders are a follow-up, not part of this plan).
- No screenshots in git. New code under `tools/`, plans/docs under `docs/`; data files under `data/` are git-ignored.
- Tests run with system python: `cd tools/render_corpus && python3 -m pytest tests -q`.
- Segment `kind` is exactly `speech` or `narration`; narrator speaker id is exactly `narrator`.
- Job ids for annotated segments are `<text_key>~a<k>` so they never collide with the `<text_key>~<k>` ids of `jobs_mixed.jsonl`.

## Review Focus

- Annotated cue missing from `jobs.jsonl` (already voiced or dropped): skipped and counted, never crashes.
- Game text changed after annotating: the guard fails at plan time; the cue is reported and left to the normal path, not rendered from stale text.
- A segment whose speaker has no voice: the cue is skipped (counted) unless `--all`; it is never silently voiced by the narrator.
- Annotation and old mixed plan both cover one cue: ids must not collide and stitch output must not overwrite a different take.
- Colon false positives in the label proposer (`Location:`, `Material:`, `Region:`, `Sector:`) must not become speakers.
- Cue text that contains `{n}...{/n}` tags as well as labels: tags are ignored by the guard, text is copied without them.

---

### Task 1: Annotation file and coverage guard

**Files:**
- Create: `tools/render_corpus/segment_annotations.py`
- Test: `tools/render_corpus/tests/test_segment_annotations.py`

**Interfaces:**
- Produces: `ANNOTATIONS: Path`, `load(path=ANNOTATIONS) -> dict[str, dict]` (guid -> entry), `validate(cue_text: str, entry: dict) -> list[str]` (empty list = valid). Entry shape: `{"segments": [{"speaker": str, "kind": "speech"|"narration", "text": str, "voice": str (optional)}], "source": str}`.

- [ ] **Step 1: Write the failing tests**

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from segment_annotations import validate  # noqa: E402

CUE = '"Scout 1: WE\'RE RICH! Lookout: Fly, spit it out. What have you found?"'


def seg(speaker, text, kind="speech"):
    return {"speaker": speaker, "kind": kind, "text": text}


def test_labelled_cue_is_valid_when_labels_are_the_only_leftover():
    entry = {"segments": [seg("Scout 1", "WE'RE RICH!"), seg("Lookout", "Fly, spit it out. What have you found?")]}
    assert validate(CUE, entry) == []


def test_text_not_covered_is_rejected():
    entry = {"segments": [seg("Scout 1", "WE'RE RICH!"), seg("Lookout", "What have you found?")]}
    errs = validate(CUE, entry)
    assert any("not covered" in e for e in errs)


def test_out_of_order_segments_are_rejected():
    entry = {"segments": [seg("Lookout", "What have you found?"), seg("Scout 1", "WE'RE RICH!")]}
    assert validate(CUE, entry)


def test_single_segment_and_bad_kind_are_rejected():
    assert validate(CUE, {"segments": [seg("Scout 1", "WE'RE RICH!")]})
    assert validate(CUE, {"segments": [seg("a", "WE'RE RICH!", "shout"), seg("b", "Fly")]})


def test_label_word_dropped_mid_gap_is_rejected():
    cue = '"Listen: we go. Lookout: Fine."'
    entry = {"segments": [seg("Ava", "we go."), seg("Lookout", "Fine.")]}
    assert validate(cue, entry)


REAL = ('{n}The {g|Encyclopedia:Cogitator}cogitator{/g} is damaged.{/n}\n"Scout 1: RICH! Screw {g|Encyclopedia:Footfall}Footfall{/g}!\n'
        'Lookout: Yeah, because with our record, Calixis is the place to go."')


def test_real_game_markup_with_glossary_links():
    entry = {"segments": [seg("narrator", "The cogitator is damaged.", "narration"), seg("Scout 1", "RICH! Screw Footfall!"),
                          seg("Lookout", "Yeah, because with our record, Calixis is the place to go.")]}
    assert validate(REAL, entry) == []


def test_n_tags_in_the_cue_are_ignored():
    cue = '{n}He grins.{/n} "Mine!" {n}She frowns.{/n}'
    entry = {"segments": [seg("narrator", "He grins.", "narration"), seg("Ava", "Mine!"), seg("narrator", "She frowns.", "narration")]}
    assert validate(cue, entry) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/render_corpus && python3 -m pytest tests/test_segment_annotations.py -q`
Expected: FAIL (`ModuleNotFoundError: segment_annotations`).

- [ ] **Step 3: Implement**

```python
"""Hand-checked speaker segments for cues where more than one voice speaks (data/npc_profile/segments.json).

A cue maps to an ordered list of {speaker, kind, text}. validate() proves the segments are an in-order copy of the cue text:
anything left over (quote marks, {n} tags, "Name:" labels) may contain no words, so a segment list can never drop or invent speech.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANNOTATIONS = ROOT / "data/npc_profile/segments.json"
KINDS = ("speech", "narration")
_TAG = re.compile(r"\{/?[a-z_]+(?:\|[^}]*)?\}")   # {n} {/n} and glossary links {g|Encyclopedia:Vox} {/g}
_LABEL_TAIL = re.compile(r"[A-Z][\w' -]{0,28}:\s*$")   # a "Name:" label, excused only at the end of a gap (just before its segment)
_WORD = re.compile(r"[A-Za-z0-9]")


def load(path: Path = ANNOTATIONS) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub("", text)).strip()


def _gaps(cue_text: str, segments: list[dict]) -> list[str] | None:
    rest, pos, gaps = _norm(cue_text), 0, []
    for s in segments:
        piece = _norm(s["text"])
        i = rest.find(piece, pos)
        if i < 0:
            return None
        gaps.append(rest[pos:i])
        pos = i + len(piece)
    gaps.append(rest[pos:])
    return gaps


def validate(cue_text: str, entry: dict) -> list[str]:
    segs = entry.get("segments") or []
    errors = []
    if len(segs) < 2:
        errors.append("needs at least two segments")
    for k, s in enumerate(segs):
        if s.get("kind") not in KINDS:
            errors.append(f"segment {k}: kind must be one of {KINDS}")
        if not s.get("speaker"):
            errors.append(f"segment {k}: missing speaker")
        if not (s.get("text") or "").strip():
            errors.append(f"segment {k}: empty text")
    if errors:
        return errors
    gaps = _gaps(cue_text, segs)
    if gaps is None:
        return ["segments are not an in-order copy of the cue text"]
    for k, gap in enumerate(gaps):
        words = _LABEL_TAIL.sub("", gap) if k < len(gaps) - 1 else gap
        if _WORD.search(words):
            errors.append(f"cue text not covered by any segment: {words.strip()[:60]!r}")
    return errors
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/render_corpus && python3 -m pytest tests/test_segment_annotations.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit (only if the user has asked for commits)**

```bash
git add tools/render_corpus/segment_annotations.py tools/render_corpus/tests/test_segment_annotations.py
git commit -m "Segment annotations: per-cue speaker segments with a coverage guard"
```

---

### Task 2: Inline-label proposer and the add tool

**Files:**
- Create: `tools/render_corpus/propose_segments.py`
- Create: `tools/render_corpus/add_segments.py`
- Test: `tools/render_corpus/tests/test_propose_segments.py`

**Interfaces:**
- Consumes: `segment_annotations.validate`, `segment_annotations.load`, `segment_annotations.ANNOTATIONS`.
- Produces: `split_labelled(text: str) -> list[dict] | None` (segments, or None when the cue has fewer than two real speaker labels); `NOT_SPEAKERS: set[str]`; CLI `propose_segments.py` writing `data/npc_profile/segments_proposed.json` (guid -> entry with `"source": "inline-labels"`, plus `"conversation"`); CLI `add_segments.py GUID --file entry.json | --from-proposed GUID` that validates against the cue text and merges into `segments.json` after copying the old file to `segments.json.bak`.

- [ ] **Step 1: Write the failing tests**

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from propose_segments import split_labelled  # noqa: E402
from segment_annotations import validate  # noqa: E402

SKEL = ('The cogitator is damaged. "Scout 1: WE\'RE RICH! Chaos take me! Lookout: Fly, for crying out loud, '
        'spit it out. Scout 1: I want a house on some planet. Lookout: Get back here."')


def test_splits_on_labels_and_validates():
    segs = split_labelled(SKEL)
    assert [s["speaker"] for s in segs] == ["narrator", "Scout 1", "Lookout", "Scout 1", "Lookout"]
    assert segs[0]["kind"] == "narration" and segs[1]["kind"] == "speech"
    assert validate(SKEL, {"segments": segs}) == []


def test_adjacent_lines_by_one_speaker_merge():
    segs = split_labelled('"Scout 1: Rich! Lookout: Fly. Lookout: Fly. You coming? Scout 1: Yes."')
    assert [s["speaker"] for s in segs] == ["Scout 1", "Lookout", "Scout 1"]
    assert segs[1]["text"] == "Fly. Fly. You coming?"


def test_data_labels_are_not_speakers():
    assert split_labelled('"Location: Footfall. Material: iron. Region: Expanse."') is None


def test_one_label_is_not_enough():
    assert split_labelled('"Lookout: Fly, are you there?"') is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/render_corpus && python3 -m pytest tests/test_propose_segments.py -q`
Expected: FAIL (`ModuleNotFoundError: propose_segments`).

- [ ] **Step 3: Implement `propose_segments.py`**

```python
#!/usr/bin/env python3
"""Propose speaker segments for cues whose text carries inline "Name:" labels (recordings, logs, shouted exchanges).

  python3 tools/render_corpus/propose_segments.py [--out data/npc_profile/segments_proposed.json]

Proposals are not used by any planner. Review them, then merge accepted ones with add_segments.py.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from segment_annotations import validate  # noqa: E402

NOT_SPEAKERS = {"Location", "Material", "Region", "Sector", "Note", "Warning", "Result", "Status", "Type", "Name", "Date", "Subject"}
_TAG = re.compile(r"\{/?[a-z_]+\}")
_LABEL = re.compile(r"(?:(?<=[\"“\s])|^)([A-Z][\w' -]{0,28}):\s+(?=[A-Z\"“])")
NARRATOR = "narrator"


def _clean(piece: str) -> str:
    return piece.strip().strip("\"“”").strip()


def split_labelled(text: str) -> list[dict] | None:
    plain = re.sub(r"\s+", " ", _TAG.sub("", text)).strip()
    hits = [m for m in _LABEL.finditer(plain) if m.group(1) not in NOT_SPEAKERS]
    if len({m.group(1) for m in hits}) < 2:
        return None
    segs = []
    lead = _clean(plain[:hits[0].start()])
    if re.search(r"[A-Za-z]", lead):
        segs.append({"speaker": NARRATOR, "kind": "narration", "text": lead})
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(plain)
        body = _clean(plain[m.end():end])
        if not re.search(r"[A-Za-z]", body):
            continue
        if segs and segs[-1]["speaker"] == m.group(1):   # "Lookout: Fly." / "Lookout: Fly. You coming?" is one take, not two tiny ones
            segs[-1]["text"] += " " + body
        else:
            segs.append({"speaker": m.group(1), "kind": "speech", "text": body})
    return segs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data/npc_profile/segments_proposed.json"))
    a = ap.parse_args()
    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    out = {}
    for c in convs:
        for ln in c["lines"]:
            if ln.get("kind") != "cue" or not ln.get("text"):
                continue
            segs = split_labelled(ln["text"])
            if segs and not validate(ln["text"], {"segments": segs}):
                out[ln["text_key"]] = {"conversation": c["name"].strip(), "source": "inline-labels", "segments": segs}
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} proposals -> {a.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Implement `add_segments.py`**

```python
#!/usr/bin/env python3
"""Validate a segment entry against the cue's text and merge it into data/npc_profile/segments.json.

  add_segments.py GUID --file entry.json          (entry.json: {"segments": [...], "source": "..."})
  add_segments.py GUID --from-proposed            (take it from segments_proposed.json)

The previous segments.json is copied to segments.json.bak first. An invalid entry is refused and nothing is written.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from segment_annotations import ANNOTATIONS, load, validate  # noqa: E402


def cue_text(guid: str) -> str | None:
    for c in json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8")):
        for ln in c["lines"]:
            if ln.get("text_key") == guid and ln.get("text"):
                return ln["text"]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("guid")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file")
    src.add_argument("--from-proposed", action="store_true")
    a = ap.parse_args()
    if a.from_proposed:
        entry = json.loads((ROOT / "data/npc_profile/segments_proposed.json").read_text(encoding="utf-8"))[a.guid]
    else:
        entry = json.loads(Path(a.file).read_text(encoding="utf-8"))
    text = cue_text(a.guid)
    if text is None:
        sys.exit(f"no cue with text_key {a.guid}")
    errors = validate(text, entry)
    if errors:
        sys.exit("refused: " + "; ".join(errors))
    current = load()
    if ANNOTATIONS.is_file():
        shutil.copyfile(ANNOTATIONS, ANNOTATIONS.with_suffix(".json.bak"))
    current[a.guid] = {k: entry[k] for k in ("segments", "source", "conversation") if k in entry}
    ANNOTATIONS.parent.mkdir(parents=True, exist_ok=True)
    ANNOTATIONS.write_text(json.dumps(current, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"added {a.guid} ({len(entry['segments'])} segments); {len(current)} annotated cues")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests, then the proposer on the real corpus**

Run: `cd tools/render_corpus && python3 -m pytest tests/test_propose_segments.py -q`
Expected: 4 passed.
Run: `python3 tools/render_corpus/propose_segments.py`
Expected: prints a count (about 25 to 33; the data-label false positives are excluded). Open the output and look at it before accepting any entry.

- [ ] **Step 6: Commit (only if asked)**

```bash
git add tools/render_corpus/propose_segments.py tools/render_corpus/add_segments.py tools/render_corpus/tests/test_propose_segments.py
git commit -m "Segment tools: propose inline-label splits, validated add"
```

---

### Task 3: Annotated planner

**Files:**
- Create: `tools/render_corpus/plan_annotated.py`
- Test: `tools/render_corpus/tests/test_plan_annotated.py`

**Interfaces:**
- Consumes: `segment_annotations.load/validate`, `plan._ref(prompts, libs, speaker, emotion, is_narrator) -> (ref, voice_source)`, `plan._narrator_ref()`, `jobs.bucket_of`, `jobs.decode_binary`, `clean_text.clean_for_tts`.
- Produces: `annotated_jobs(job: dict, entry: dict, narrator_ref: dict, ref_fn) -> list[dict]` where `ref_fn(speaker: str, emotion: str | None) -> (ref, voice_source)`. Each job has the keys `plan_mixed.segment_jobs` produces (`guid`, `parent`, `seg_index`, `seg_count`, `seg_kind`, `speaker`, `text`, `engine`, `bucket`, `priority`, `voice_source`, `ref`, `annotation`, `src_text`, `speaker_kind`) with `guid = f"{parent}~a{k}"`. CLI writes `data/render/jobs_annotated.jsonl`.

- [ ] **Step 1: Write the failing tests**

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from plan_annotated import annotated_jobs  # noqa: E402

JOB = {"guid": "g1", "speaker": "Vladaym", "speaker_kind": "default_speaker", "src_text": "x", "priority": 1,
       "voice_source": "prompt_bank", "ref": {"wav": "v.wav", "text": "v"}, "annotation": {"emotion": "angry"}}
NARR = {"wav": "n.wav", "text": "n"}


def ref_fn(speaker, emotion):
    if speaker == "Jae":
        return {"wav": "jae.wav", "text": "j", "emotion": emotion}, "prompt_bank"
    return dict(NARR, emotion=None), "fallback"


def entry(*segs):
    return {"segments": [{"speaker": s, "kind": k, "text": t} for s, k, t in segs]}


def test_each_segment_gets_its_own_voice_and_a_distinct_id():
    jobs = annotated_jobs(JOB, entry(("narrator", "narration", "She turns."), ("Jae", "speech", "Fine."), ("Scout", "speech", "Wait!")), NARR, ref_fn)
    assert [j["guid"] for j in jobs] == ["g1~a0", "g1~a1", "g1~a2"]
    assert [j["speaker"] for j in jobs] == ["narrator", "Jae", "Scout"]
    assert [j["voice_source"] for j in jobs] == ["narrator", "prompt_bank", "fallback"]
    assert {j["parent"] for j in jobs} == {"g1"} and jobs[2]["seg_count"] == 3
    assert jobs[0]["seg_kind"] == "narration" and jobs[1]["seg_kind"] == "speech"


def test_cue_level_emotion_only_applies_to_the_cue_speaker():
    jobs = annotated_jobs(JOB, entry(("Vladaym", "speech", "Hmph."), ("Jae", "speech", "Fine.")), NARR, lambda s, e: ({"emotion": e}, "prompt_bank"))
    assert jobs[0]["ref"]["emotion"] == "angry" and jobs[1]["ref"]["emotion"] is None


def test_text_is_cleaned_for_tts():
    jobs = annotated_jobs(JOB, entry(("Jae", "speech", "Hello   there."), ("Scout", "speech", "Hi.")), NARR, ref_fn)
    assert jobs[0]["text"] == "Hello there."
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/render_corpus && python3 -m pytest tests/test_plan_annotated.py -q`
Expected: FAIL (`ModuleNotFoundError: plan_annotated`).

- [ ] **Step 3: Implement**

```python
#!/usr/bin/env python3
"""Plan segment jobs for cues annotated in data/npc_profile/segments.json (several speakers in one cue).

  python3 tools/render_corpus/plan_annotated.py [--out data/render/jobs_annotated.jsonl] [--all]

Reads data/render/jobs.jsonl (read only). Annotated cue "G" becomes jobs "G~a0", "G~a1", ...: each segment uses its own speaker's
reference (a bank voice, a pool_<id> slot, or the narrator). Ids differ from plan_mixed's "G~k", so the two plans never collide.
render.py, asr_check.py and stitch_mixed.py then run on the file unchanged. A cue where any speaking segment has no real voice is
skipped (counted) unless --all, and a cue whose annotation no longer matches the game text is reported and skipped.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools"))

from clean_text import clean_for_tts  # noqa: E402
from jobs import bucket_of, decode_binary  # noqa: E402
from plan import _narrator_ref, _ref  # noqa: E402
from plan_mixed import ENGINE, VOICED_SOURCES  # noqa: E402
from segment_annotations import load, validate  # noqa: E402

MIN_SPEECH_CHARS = 20   # shorter takes tend to fail take_problem or sound clipped; warn at plan time
PRIORITY = {"emotion_bank": 0, "prompt_bank": 1, "narrator": 2, "fallback": 3}
SEP = "~a"


def annotated_jobs(job: dict, entry: dict, narrator_ref: dict, ref_fn) -> list[dict]:
    segs, out = entry["segments"], []
    for k, s in enumerate(segs):
        narr = s["kind"] == "narration" or s["speaker"] == "narrator"
        if narr:
            speaker, ref, source = "narrator", dict(narrator_ref, emotion=None), "narrator"
        else:
            speaker = s["speaker"]
            emotion = (job.get("annotation") or {}).get("emotion") if speaker == job["speaker"] else None
            ref, source = ref_fn(s.get("voice", speaker), emotion)
        out.append({
            **{f: job[f] for f in ("speaker_kind", "src_text") if f in job},
            "guid": f"{job['guid']}{SEP}{k}", "parent": job["guid"], "seg_index": k, "seg_count": len(segs),
            "seg_kind": "narration" if narr else "speech", "speaker": speaker,
            "text": clean_for_tts(decode_binary(s["text"])), "engine": ENGINE, "bucket": bucket_of(job["guid"]),
            "priority": PRIORITY[source], "voice_source": source, "ref": ref,
            "annotation": (job.get("annotation") if speaker == job["speaker"] else None),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_annotated.jsonl"))
    ap.add_argument("--all", action="store_true", help="include cues with a speaker that has no real voice yet")
    a = ap.parse_args()
    annotations = load()
    texts = {}
    for c in json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8")):
        for ln in c["lines"]:
            if ln.get("text_key") in annotations and ln.get("text"):
                texts[ln["text_key"]] = ln["text"]
    prompts = json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8"))
    libs: dict = {}
    narrator = _narrator_ref()
    stats, rows, planned = Counter(), [], set()
    for line in Path(a.jobs).read_text(encoding="utf-8").splitlines():
        job = json.loads(line)
        entry = annotations.get(job["guid"])
        if entry is None:
            continue
        errors = validate(texts.get(job["guid"], ""), entry)
        if errors:
            print(f"STALE {job['guid']}: {errors[0]}")
            stats["stale"] += 1
            continue
        segs = annotated_jobs(job, entry, narrator, lambda sp, emo: _ref(prompts, libs, sp, emo, False))
        if not a.all and any(s["seg_kind"] == "speech" and s["voice_source"] not in VOICED_SOURCES for s in segs):
            stats["skipped_unvoiced"] += 1
            continue
        for s in segs:
            if s["seg_kind"] == "speech" and len(s["text"]) < MIN_SPEECH_CHARS:
                print(f"SHORT {s['guid']} ({s['speaker']}): {s['text']!r}")
        rows += segs
        planned.add(job["guid"])
    stats["not_in_jobs"] = len(set(annotations) - planned) - stats["stale"] - stats["skipped_unvoiced"]
    mixed_path = ROOT / "data/render/jobs_mixed.jsonl"
    in_mixed = {json.loads(l)["parent"] for l in mixed_path.read_text(encoding="utf-8").splitlines()} if mixed_path.is_file() else set()
    print(f"{len(planned & in_mixed)} of these cues are also in jobs_mixed.jsonl (rendered there in one voice; overlay_export.py: list annotated-stitched AFTER mixed-stitched, later runs win)")
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(planned)} annotated cues -> {len(rows)} segment jobs in {a.out}; "
          f"skipped {stats['skipped_unvoiced']} unvoiced, {stats['stale']} stale, {stats['not_in_jobs']} not in jobs.jsonl")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/render_corpus && python3 -m pytest tests/test_plan_annotated.py -q`
Expected: 3 passed. If `jobs.decode_binary` or `clean_text.clean_for_tts` import paths differ, copy the import lines from `tools/render_corpus/mixed.py`, which already imports both.

- [ ] **Step 5: Dry run (read-only)**

First grep `render.py`, `asr_check.py`, `merge.py` and `overlay_export.py` for any parsing of the `~` suffix (a grep on 2026-10-11 found none; recheck if they changed).
Run: `python3 tools/render_corpus/plan_annotated.py --out /tmp/claude-1000/-home-geoff-projects-games-W40KRogueTraderNeuralSpeechMod/a017b2fc-b1a8-4b2a-990d-9530c01e39d7/scratchpad/jobs_annotated_dry.jsonl`
Expected: runs without touching `jobs.jsonl`; with an empty or missing `segments.json` it plans 0 cues.

- [ ] **Step 6: Commit (only if asked)**

```bash
git add tools/render_corpus/plan_annotated.py tools/render_corpus/tests/test_plan_annotated.py
git commit -m "Plan annotated multi-speaker cues as per-speaker segment jobs"
```

---

### Task 4: Stitch compatibility and the first real annotations

**Files:**
- Modify (only if the check below fails): `tools/render_corpus/stitch_mixed.py:96-99`
- Test: `tools/render_corpus/tests/test_plan_annotated.py` (append)

**Interfaces:**
- Consumes: `plan_annotated.annotated_jobs`, `stitch_mixed.py` grouping (`by_parent[j["parent"]]`, sort on `seg_index`, manifest speaker = first job with `seg_kind == "speech"`, loudness target per `j["speaker"]`).
- Produces: confirmation that annotated jobs stitch with no changes, and the first entries in `data/npc_profile/segments.json`.

- [ ] **Step 1: Add a compatibility test**

```python
def test_jobs_carry_every_field_stitch_mixed_reads():
    jobs = annotated_jobs(JOB, entry(("Jae", "speech", "Fine."), ("narrator", "narration", "She leaves.")), NARR, ref_fn)
    for j in jobs:
        assert {"parent", "seg_index", "seg_kind", "speaker", "text", "src_text"} <= set(j)
    assert next(j["speaker"] for j in jobs if j["seg_kind"] == "speech") == "Jae"
```

- [ ] **Step 2: Run, confirm pass**

Run: `cd tools/render_corpus && python3 -m pytest tests/test_plan_annotated.py -q`
Expected: 4 passed. `stitch_mixed.py` needs no edit; if a later change breaks the manifest speaker line, fix it there.

- [ ] **Step 3: Add the known labelled cues**

Run `python3 tools/render_corpus/propose_segments.py`, read `data/npc_profile/segments_proposed.json`, and for each proposal that is truly multi-speaker run `python3 tools/render_corpus/add_segments.py <GUID> --from-proposed`. Start with the Skeletons cues (conversation `Skeletons_AncientTrapEE_dialog`, lines 10 and 11, Scout 1 / Lookout) and the Bridge / Lookout cues in `WebwayGate_c2_BE`. Reject the data-label false positives by not adding them.

- [ ] **Step 4: Add the reviewer-found cues by hand**

For the cues the 2026-10-11 review marked as several speakers in one clip (StryxShedCogitator lines 12-14, Cassia_Q2_BE lines 3, 4, 7, 8, 23, 47, Ulfar_BE if the user wants separate voices), write an `entry.json` per cue with the user's answers (speaker ids, and `voice` where a pool slot is needed), then `add_segments.py <GUID> --file entry.json`. The guard refuses anything that does not cover the cue text.

- [ ] **Step 4b: Size the unlabelled remainder**

Count cues where `mixed.segments()` gives two or more speech segments split by narration that names a different person, and put the number in the plan's Follow-ups, so the user knows what share of multi-speaker cues this plan does not reach. Also listen to the 0.35 s stitch pause between two characters once a render exists; it was tuned for speech to narration.

- [ ] **Step 5: Plan and read the result**

Run: `python3 tools/render_corpus/plan_annotated.py`
Expected: line like `N annotated cues -> M segment jobs`; read a few rows of `data/render/jobs_annotated.jsonl` for speaker/voice_source. Cues with a voiceless speaker are counted as skipped until pool voices exist; that is correct.

- [ ] **Step 6: Commit (only if asked)**

```bash
git add tools/render_corpus/tests/test_plan_annotated.py
git commit -m "Annotated segments: stitch compatibility test"
```

---

### Task 5: Docs and handoff notes

**Files:**
- Modify: `TODO.md` (add a short "Multi-speaker cues" item under section 4)
- Create: memory file `multi-speaker-segments.md` in the project memory dir, plus its `MEMORY.md` line

- [ ] **Step 1: Document the workflow**

In `TODO.md` section 4 add: annotated cues live in `data/npc_profile/segments.json`; plan with `plan_annotated.py` (own jobs file); render with `render.py --jobs data/render/jobs_annotated.jsonl --name annotated-seg` (needs the user's GPU go-ahead); ASR with `asr_check.py --run annotated-seg`; stitch with `stitch_mixed.py --jobs data/render/jobs_annotated.jsonl --runs annotated-seg --out annotated-stitched`; list `annotated-stitched` AFTER `mixed-stitched` in `overlay_export.py --overlay` (later runs win there; `merge.py` is the first-wins tool). Render command needs `--engine voxcpm2`.

- [ ] **Step 2: Run the whole render_corpus test suite**

Run: `cd tools/render_corpus && python3 -m pytest tests -q`
Expected: all pass, none of the previously passing tests broken.

- [ ] **Step 3: Write the memory note and index line, then commit if asked**

Memory file `multi-speaker-segments.md` (type project), body: annotation file `data/npc_profile/segments.json` (keyed by text_key, guard in `segment_annotations.validate`), tools `propose_segments.py` / `add_segments.py` / `plan_annotated.py`, job ids `<guid>~a<k>`, own jobs file `jobs_annotated.jsonl`, overlay `annotated-stitched` first, count of annotated cues, and what is still open (unlabelled multi-speaker detection, voiceless speakers, render needs GPU go-ahead). Index line in `MEMORY.md`: `- [Multi-speaker segments](multi-speaker-segments.md) — per-speaker segment annotations for cues with several voices, tools and run order`.

---

## Follow-ups (not in this plan; each needs the user)

1. Render the annotated segments (GPU), ASR-check, stitch, overlay, rebuild and install the banks.
2. Detect multi-speaker cues that carry no inline labels (nested quotes, `"A" he said. "B" she replied.`). The proposer only finds labelled ones; a model pass over reviewer-flagged mixed cues can feed `add_segments.py` through the same guard.
3. Voices for the segment speakers that have none (generic pool slots), set per segment with the `voice` field.
