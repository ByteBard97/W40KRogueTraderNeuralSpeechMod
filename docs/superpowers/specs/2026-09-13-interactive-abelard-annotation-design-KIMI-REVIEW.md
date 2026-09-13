# Review request for Kimi: interactive Abelard annotation harness spec

You're reviewing a design spec before implementation starts. The spec is
`docs/superpowers/specs/2026-09-13-interactive-abelard-annotation-design.md` in this repo —
read it in full first.

## Context

`tools/annotate/annotate.py` automatically labels Rogue Trader dialogue lines with an
emotion/pace/delivery annotation for TTS. Its per-speaker mode (`--speaker Abelard
--unvoiced-only`) produces weak labels for the companion Abelard, because `conv_payload()`
in that file filters a conversation down to *only* his lines before sending it to the model
— the model never sees what he's responding to. The spec proposes having a human (in
practice, a Claude Code agent acting with real judgment) label his ~575 unvoiced lines
directly instead, via two new small scripts (`interactive_next.py`, `interactive_submit.py`)
plus a pure-logic `context_window.py`, reusing the existing cache-file format so
`annotate.py`'s existing `--merge` and `diff_cache_vs_production.py` handle
review/production-merge with minimal changes.

This spec already went through one review round with a different reviewer (Claude's
"advisor" tool), which found and fixed a real, verified blocker: `annotate.py --merge`
(lines ~247-257) rebuilds `annotations.enGB.json` from scratch out of *only*
`--cache-dir`'s contents rather than updating production — pointed at an Abelard-only
cache dir, it would have silently overwritten the other ~44,500 lines. The spec now calls
for making `--cache-dir` repeatable (`action="append"`, later dir wins per-guid) as a
required, in-scope fix, not something deferred. That round also dropped two earlier
context-window designs (flat-array slicing, then a parent-pointer tree walk) in favor of
simply showing the whole conversation and falling back to tunable flat chunking only for
conversations too long to read in one pass — check the spec's "Architecture" section for
the reasoning already given for that choice; you don't need to re-litigate it, but do flag
if you think it's actually wrong.

## What to actually check

Please read the real files, not just the spec's descriptions of them:
- `tools/annotate/annotate.py` (especially `conv_payload`, `validate`, the `--merge` block,
  and `line_hash`)
- `tools/annotate/schema.py`
- `tools/annotate/diff_cache_vs_production.py`
- `data/conversations.enGB.json` (sample a few conversations — it's ~1300 entries, no need
  to read all of it)
- `data/character_bios.json["Abelard"]`
- `data/voices/emotion_banks/speaker_vocab.json["Abelard"]`

Then check the spec's claims against what you actually find:

1. **The cache file format and merge/diff reuse.** Does the spec's described cache file
   shape (`{"conv", "model", "lines": [{"guid","emotion","intensity","pace","nonverbal",
   "instruct","text_hash"}]}`) match what `annotate.py` actually writes and what `--merge`
   and `diff_cache_vs_production.py` actually consume? Is the proposed `--cache-dir`
   repeatable/precedence fix actually sufficient and backward-compatible (single
   `--cache-dir`, today's only usage, must produce byte-identical output to before), or is
   there a subtlety the spec missed?
2. **The data model.** Does `data/conversations.enGB.json`'s real structure match what the
   spec assumes (`guid`/`kind`/`parent`/`via`/`depth`/`text_key`/`text`/`voiced`/`speaker`/
   `animation`, lines already in document order per conversation, `speaker.name` identifying
   named characters)? Any structural gotcha (multiple root nodes, orphaned `parent`
   references, lines with `text` but no `text_key` or vice versa, duplicate `text_key`
   across conversations, encoding issues) that `abelard_targets()`, `dialogue_lines()`, or
   `chunk_ranges()` as specified would mishandle?
3. **The chunking design specifically.** Chunking is flat-position-based (fixed-size ranges
   with overlap, dropping ranges with no Abelard target), explicitly chosen over a
   tree-aware split after checking that the largest real conversations don't have clean
   branch boundaries to exploit. Do you agree with that empirical claim, or does a spot
   check of a large conversation (e.g. one of the 36+ that exceed 150 lines) suggest a
   tree-aware or otherwise different split would in fact be meaningfully better? Also check:
   is a target line ever silently droppable at a chunk boundary as specified, despite the
   spec's intent that every target lands in at least one retained chunk?
4. **The vocabulary/schema plumbing.** Will `schema.build_json_schema(emotions)` actually
   accept `speaker_vocab.json["Abelard"]["words"]` (a 21-word list) as a drop-in custom
   enum with no other change, as the spec assumes?
5. **Anything else concretely wrong** — a bug, a missed edge case, a wrong assumption that
   would bite during implementation. Not style preferences or hypothetical future
   requirements; only things that would actually break or mislead given this repo's real
   code and data.

## How to report

Concrete findings only, with `file:line` references where you can give them. If a section
of the spec checks out, say so plainly rather than inventing a nitpick to fill space. If you
disagree with a design decision the spec already made a call on (e.g. whole-conversation +
chunking vs. a tree walk), say why with evidence from the actual data, not just in the
abstract — the previous round already showed that abstract-sounding tree-walk correctness
concerns can be wrong once checked against the real conversation shapes.
