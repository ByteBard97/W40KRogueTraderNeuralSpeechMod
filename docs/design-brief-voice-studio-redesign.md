# Prompt for Claude Design: Voice Studio redesign

Paste everything below the line into Claude Design. Attach screenshots of each page if you can (they are in `.playwright-mcp/`).

---

I need a redesign of a local web app called **Voice Studio**. Improve usability first and aesthetics second. Produce a hi-fi design (clickable HTML prototype or per-page mockups) for every page listed below, plus a shared design system, and explain the main changes per page.

## Who uses it and why

One person (a hobbyist modder) uses it alone on a desktop with headphones, in long sessions. The app is a workbench for a mod that replaces unvoiced dialogue in Warhammer 40K: Rogue Trader with AI-generated speech. The work is almost entirely listening and judging audio: play a clip, compare it to another, decide good or bad, rank, move on. Thousands of items are reviewed, so speed, keyboard control and low fatigue matter more than decoration. The user cannot use light mode, so the UI is **dark only** and must stay comfortable for hours (no pure white, no harsh glare, restrained accent colour). It is a desktop tool but must not break at a 420px width.

The mod's setting is grimdark gothic sci-fi. A subtle nod to that (typography, a muted brass or ember accent, panel framing) is welcome. Do not turn it into a themed game UI: legibility and density win. No emoji as status markers.

## What exists today (the problems to solve)

Stack is Vue 3 + TypeScript, plain CSS tokens on `:root`. Every page is a stack of bordered cards with small text and many small buttons. Known weak spots:
- Audio is the core interaction, yet play controls are small and scattered; there is no persistent now-playing bar, no visible progress or seek, no global play/pause key on most pages.
- Dense pages (QA, Matches, Speakers) show everything at once with little hierarchy; the eye has no resting place and status (judged, picked, flagged) is easy to miss.
- Keyboard shortcuts exist on Render QA only and are not discoverable.
- Long lists use "Show more" or Next/Prev with little sense of position or progress.
- Saves happen on click with little feedback; errors appear as plain text.
- The model status (ready / busy / down) is a small label; busy state during a 5 to 10 second generation gives poor feedback.

## Design system to deliver first

Colour tokens (dark only; one neutral ramp, one accent, semantic good / bad / warn / info, plus a selected and a focus state that work for keyboard users), a type scale (a readable UI face plus a monospace for ids and paths), spacing and radius scale, elevation, and components: top bar with section nav and model-status pill, sidebar list with status dots, card or section with collapse, button set (primary, secondary, ghost, danger, icon), segmented control, chips and tags, filter bar, data row, empty state, toast and inline error, progress and busy states, and above all a **shared audio player**: a persistent bottom bar (now playing label, play/pause, seek, time, speed, loop, volume) and a compact inline play button used in rows, plus an **A/B compare strip** that plays N labelled clips with one shared element and lets the user switch between them while keeping the playhead position. Show keyboard shortcut hints on buttons and a `?` overlay listing all shortcuts for the current page.

## Pages (design each one, desktop plus a 420px view)

1. **Speakers list** (`/speakers`): 43 speakers grouped into "Needs a voice" (20), "Has a source" (23) and "Profile saved". Each has name, origin (real, designed), line count, a pick marker. Search box, a "Register all picks" action (confirm dialog, then a result summary listing skipped ones). Goal: see at a glance who still needs work and jump straight to the next unfinished speaker.

2. **Speaker workbench** (`/speakers/:slug`): the main working page. One scrolling page with sticky results, previous/next speaker and an "N / total, M picked" progress indicator. Sections:
   - *Source*: for real speakers a list of catalogue clips (play, duration, transcript, noise level, rank) with multi-select to compare; for designed speakers a description editor, live design (seed, cfg, steps, Generate, Keep) and a **candidate ranker** (6 candidates per speaker; drag or arrow-key reorder; accent and fit 1 to 5 scores; reject; "Pick"; score chips such as p_us, top label, "unscored"; per-candidate row of clone-test clips that read real lines in the designed voice); for supplied voices a wav path plus transcript.
   - *Test lines*: searchable list with emotion filter chips, bank render playable, checkboxes, "pick 6 spread across emotions".
   - *Options*: cfg, timesteps, seed policy, style prefix, retry bad takes, normalise text, continuation mode.
   - *Post-processing*: FX preset multi-select, "Open in FX Lab".
   - *Results*: per line, a compare row (real clip, bank render, raw clone, FX version) with star ratings; profile bar (save profile, set active).
   - *Register pick* for the chosen candidate. Make the listen, rank, pick loop fast: ideally the candidates are visible and playable together without scrolling, with keyboard play and rank.

3. **Pools** (`/pools`): unnamed lines (about 6,700) are routed to known speakers, the narrator, or shared "slot" voices (8 slots). Show routing summary (counts by destination), a slot list (name, line count, rename, **merge into another slot** with a confirm that states how many lines move), a routes table with filters and per-line override, a review queue of low-confidence routes (Accept or Move), and a **spot check** per slot (10 sampled lines, mark each right or wrong, submit). Needs a clear sense of "what still needs my attention".

4. **FX** (`/fx`): preset library list, a label-to-preset map editor (which effect presets apply to which voice label, with unsaved-edit state), an assignments preview and an explicit Write action (confirm, shows the backup file), and the embedded FX Lab (an iframe of another tool; design the surrounding frame, not the iframe's contents).

5. **Matches** (`/matches`): 277 proposed matches of roster entries to known speakers (25 flagged). Each row: roster name, gender, species, role, proposed speaker, sample lines (text, up to 600 chars), Accept or Reject. Filters by group (flagged, has bank, no bank), speaker, decision state and text search; counts per group; "Show more". Needs fast keyboard review (accept, reject, next) and visible progress.

6. **Render QA** (`/qa`): the highest-volume page: about 11,000 rendered clips to judge. Run picker (merged export or a single run), filters (speaker, reference voice, engine, flag, verdict, text search), sort (suspicious first, slowest, fastest, longest, shortest, random), a stats line (good, bad, unjudged, plus per-reference tallies), a compressor A/B selector (off, mild, strong). Each clip row shows text, speaker, engine, duration, characters per second, auto flags (cap hit, slow, fast, short, very long, plus ASR flags with "heard" text and word error rate), and compare buttons for the clip, its clone reference, the earlier render and the game's own line ("Real: speaker"). Good and Bad buttons, tag chips, a note field. Existing keys: j/k move, space play, g good, b bad, u clear, n next unjudged, x compressor on or off. Design this as a focused review mode: one prominent current clip, a compact queue beside it, large Good and Bad targets, visible shortcuts, and a progress bar.

Also design: the **top bar** with the five sections, the model-status pill (ready, busy with a progress or elapsed time, down with a reason), and global empty, loading and error states.

## Constraints

- Dark theme only; WCAG AA contrast; visible focus rings; every action reachable by keyboard; respect `prefers-reduced-motion`.
- Do not hide information the user relies on: flags, counts, durations and ids stay visible, just better organised.
- Prefer progressive disclosure for rarely used controls (Options, continuation mode) and sensible defaults.
- Components must map onto Vue single-file components with scoped CSS and CSS variables, with no heavy UI framework required. Give tokens as CSS custom properties.
- Optimise for dense, repeated use: fewer clicks per judgement, large hit targets for the judging buttons, no modal dialogs for routine actions (use inline confirmation or undo toasts).

## Deliverables

1. The design system (tokens, components, shared audio player and A/B strip).
2. A mockup or prototype for each of the six pages above, desktop and 420px.
3. A short rationale per page: what changed and which usability problem it solves.
4. A prioritised list of the changes that give the most usability gain for the least build effort, so they can be implemented first.
