# Voice Studio, Pools slice: design

Date: 2026-10-09. Parent spec: `2026-10-09-voice-studio-design.md` (sections 3.2, 4, 9). Second slice of the Studio.
Revised after Kimi's review the same day; its claims were re-checked against the data (section 2).

## 1. Goal

6,717 priority-3 lines are spoken by NPCs the game does not name (`speaker == default_speaker`). Today the render plan
gives every one of them the same fallback voice. The harness (`tools/npc_profile`) has attributed each line to a
character. This slice **routes** every such line to the right voice, and builds shared **voice slots** only for the lines
that really are anonymous.

Success: every unnamed line resolves to exactly one of a known speaker's voice, the narrator, or a slot voice; the user
reviews roughly a hundred decisions, not thousands; the render plan reads the result without hand-editing.

## 2. What the data says (checked 2026-10-09)

All numbers come from `data/render/jobs.jsonl` joined to `data/npc_profile/roster_35b_all.json` (join key: roster line
`key` == job `guid`) and to the existing matcher `tools/npc_profile/known.py`.

- Coverage is 100%: every one of the 6,717 lines has a harness attribution. Line-attribution confidence is near perfect
  (median 1.00; 97 lines below 0.8). The uncertainty sits in the roster entries' labels, not the attribution.
- **Most "unnamed" lines are not anonymous.** 5,400 are attributed to a roster entry with a personal name (163 names).
  Matching those names to speakers the game already names gives, roughly (the line total is 6,921 because a few lines
  appear in more than one conversation, so treat these as ±3%):

| Where the line goes | Lines | Voice |
|---|---|---|
| Known speaker **with a real voice bank** (Heinrix, Solomorne, Cassia, Yrliet, Marazhai, Kibellah, Argenta, Ulfar and 7 others) | ~1,900 | that speaker's own bank. These are extraction gaps: companion lines exported without speaker tags. |
| Known speaker **without a bank** (89 named NPCs: Tervantias, Calligos Winterscale and others) | ~2,900 | the named-NPC voice track (one designed voice per NPC, the Speakers section). Not a pool. |
| Narrator, or attributed to no roster entry | ~140 | narrator voice |
| **No known speaker: the real pool candidates** | **~1,860** (165 roster entries) | a slot voice |

- Pool candidates by voice-defining axes: male human ~1,300; female human ~320; male machine 74; male eldar 55; the rest
  (unknown, tyranid, drukhari, daemon) 5 to 36 lines each. Age is unknown for most entries.
- `match_decisions.json` holds only 25 decisions (17 accept, 8 reject) and **nothing reads it** except the review page
  (`match_review.py`). The routing above uses `known.match` directly; the saved decisions must override it.
- Mixed `{n}` lines stay dropped (project memory); the assignment view excludes them.
- Review need at threshold 0.8, queuing only on the voice-defining axes (see decision 3): about 560 lines from 92 roster
  entries, of which 134 are the no-roster-entry lines.

## 3. Decisions

1. **Assignment policy: automatic with an exception queue and a spot check.** Recommended by the author, the advisor and
   Kimi; the user has not objected. Every assignment records provenance (`auto` or `override`) and the harness
   confidence, so a harness re-run can be diffed without overwriting overrides.
2. **Routing comes first and is part of this slice.** Order: narrator, then known speaker with a bank, then known speaker
   without a bank, then slot. `known.match` supplies the first pass and the saved `match_decisions.json` overrides it, so
   wiring those decisions into routing is a prerequisite task here, not a follow-up. A rejected match falls through to the
   next rule.
3. **What goes in the exception queue** (only axes that change the voice): line attribution confidence below the
   threshold; roster-entry gender unknown or below the threshold; roster-entry species unknown or below the threshold;
   no roster entry. **Unknown age is not a review reason**: it means an age-neutral slot. Low FX confidence is the weakest
   axis (57 entries below 0.8) and belongs to FX-preset review, not slot assignment.
4. **Review per roster entry, not per line.** The queued lines attach to a small set of roster entries; one decision on
   an entry fixes all of its lines (92 entries instead of ~560 lines). Per-line override stays available.
5. **Defaults, changeable in the UI:** threshold 0.8; spot-check 10 lines per slot. **Any wrong line in a spot check
   doubles that slot's sample**, so a bad slot gets more scrutiny automatically. Zero errors in 100 samples bounds the
   true error rate near 3% at 95% confidence; with about 6 to 8 slots, 10 per slot gives that order of coverage.
6. **No-entry lines (134)** go to the default slot for their conversation's evidence if it has any, otherwise to
   "human, unknown" and into the queue.
7. **Slots come from the data.** A slot is a gender / species combination with at least `MIN_SLOT_LINES` (default 40)
   lines; age is a second split only for the human slots when enough entries have a known age (old, young). Smaller
   combinations merge into the nearest slot (unknown gender joins the larger-gender slot of the same species, a species
   under the minimum joins "other"). Expect 6 to 8 slots. The user can rename, split or merge.
8. **A slot is a profile** and reuses the Speaker page (Source, Test lines, Options, Post-processing, Results) with a
   slot context; its voice is designed, ranked, registered, then cloned like any speaker.
9. **FX per slot** defaults from the harness FX categories (machine, vox_channel, helmet, ethereal, monstrous, cavernous),
   changeable per slot.

## 4. Integration with the render plan

`tools/render_corpus/plan.py` looks voices up by speaker name only (`_ref(prompts, libs, speaker, ...)`); it has no
line-level mapping. This slice adds one:

- The studio writes `data/studio/pools.json`: `{slots: {<slot_id>: {name, gender, species, age, fx, speaker_key}},
  routes: {<guid>: {to: "speaker"|"narrator"|"slot", speaker?, slot?, source: "auto"|"override", confidence}}}`.
- A registered slot voice goes into the prompt bank under `speaker_key` (`pool_<slot_id>`), exactly as Register pick does
  for a designed NPC.
- `plan.py` gains one rule: when a job's speaker is `default_speaker` and `pools.json` has a route for its `guid`, use the
  routed speaker's reference with `voice_source="prompt_bank"` (or `narrator`); otherwise behave as today. It is a small,
  tested change and its own task, with a test that an unrouted line still gets the fallback.
- Routes to a named NPC without a bank resolve to that NPC's designed voice once registered; until then they keep the
  fallback, and the Pools view shows them as "waiting on the named-NPC voice track".

## 5. User interface

Pools view (parent spec 3.2): a slot list and an Assignment panel.

- Slot list: name, line count, status (needs voice, has source, profile saved), spot-check progress.
- Slot page: the Speaker page with the slot context.
- Assignment: a **routing summary** first (the table in section 2, live counts), then lines grouped by destination with
  filters (confidence, gender, species, slot); the exception queue grouped **by roster entry**, each entry showing its
  evidence quotes and lines, with accept / reassign controls; a sampled spot-check per slot.
- Large lists are paged (the 1,300-line male-human slot must stay responsive).

## 6. API

`GET /api/pools` (slots, counts, routing summary, status); `POST /api/pools/slots` (create, rename, merge);
`GET /api/pools/routes` (paged, filtered); `GET /api/pools/queue` (roster entries needing review);
`POST /api/pools/routes` (override, batch, by entry or by line); `GET /api/pools/spot-check/{slot}`;
`POST /api/pools/rebuild` (re-derive auto routes from the roster and matcher; never touches overrides).
Slot voice endpoints reuse the speaker routes with `slug = pool_<slot_id>`.

## 7. What is blocked on whom

- **Not blocked:** routing, the match-decision wiring, slot derivation, exception queue, spot check, the `plan.py` rule
  and the Pools UI. All of it works on existing data with the model off.
- **Blocked on the user's ear:** designing slot voices (the same audition the 12 pilot NPC voices are waiting on). The
  89 named NPCs without a bank need the same.
- **Blocked on a GPU go:** generating candidates for the slot and named-NPC voices. The Windows 4070 is available when
  the user says so.

## 8. Testing

- pytest: routing order and the rejected-match fallthrough, slot derivation and merge rules, queue rules (unknown age is
  not queued), per-entry decisions, provenance, rebuild keeps overrides, the `plan.py` rule (routed, unrouted, narrator,
  known speaker), and the routes, on the fake-repo fixture.
- Vitest on the new views and composables.
- Real-data pass with the model off: the routing summary must reproduce the section 2 counts within the stated tolerance
  and the queue must be about 92 entries.
- Safety: back up `data/studio/pools.json`, `prompts.json`, `match_decisions.json` and the render jobs before any write
  test.

## 9. Not in this slice

The render itself, pronunciation verdicts, designing the named-NPC and slot voices (needs the user's ear and a GPU go),
FX Lab port, Matches, Render QA.
