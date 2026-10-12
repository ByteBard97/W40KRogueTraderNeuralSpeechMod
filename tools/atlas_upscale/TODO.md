# TODO: texture sharpness and the game-driving bridge

Written 2026-10-11. Nothing here is started except the diagnostics (installed, untested in game).

## A. Texture sharpness: return script (needs the game, 10 minutes)

Full reasoning in `docs/research/rt-texture-sharpness-synthesis.md`.

- [x] (done via the bridge, results in the run1 doc) Restart the game, open Idira, press F9. Read `[AtlasUpscale]` lines in `GameLogFull.txt` and the `Dump` PNGs.
      A 2048 atlas for a character named "Doll ..." is the problem; `requested 4096, size 4096` is expected.
- [x] (done) F8 to `probe_stripes` at max zoom, screenshot (uniform grey / washed out / crisp: see the synthesis for what each means).
- [x] (done) Same pose: `plain resize` vs `topaz_recover`, screenshot each.
- [x] (done: TAA softens fine detail slightly, not the main cause) Repeat with anti-aliasing Off or SMAA. If the gap widens, TAA is the cause.
- [ ] Judge on hair, chains, stitching, not the belt buckle.
- [ ] Only if the atlas is a real 4096 and TAA is not the cause: upscale the `_n` (and maybe `_m`) maps, same names, no code change. Needs GPU time; ask first.
- [ ] Leftovers to decide on (not deleted): `screens/sharpness_analysis/_o.png`, `data/atlas_upscale/_stage/`,
      empty `C:\Users\geoff\tg-test\probe` on the Windows box.
- [ ] Commit `tools/atlas_upscale/` edits and `docs/research/rt-texture-sharpness-*.md` when asked (no Claude attribution).

## B. Game bridge: let Claude drive the game (no human as eyes and hands)

Idea: an in-process HTTP listener on localhost inside the Atlas Upscale UMM mod, plus a thin Python MCP server (or a Bash script)
that forwards tool calls to it. Game runs on this machine under Proton, so everything stays local.
Requests must be queued to the Unity main thread and each command must return only after the effect happened (wait a frame or two for screenshots).

Slice 1 status (2026-10-11): BUILT, INSTALLED AND TESTED IN GAME (ping, state, shot, aa, texture_set, zoom, ui_list, ui_click, dump all work). Slice 2 (ui_list/ui_click) also built. First measurements: docs/research/rt-texture-sharpness-bridge-run1.md.
Helpers: `restart_game.sh [dll]` (install, restart, press Enter to the main menu), `open_idira.sh` (Continue, inventory, select Idira; may need a space key at the loading screen first), `compare_sets.py` (set x AA matrix with crops).
The MCP wrapper needs a Claude Code restart before the tools show up; until then use bridge.py.
`Bridge.cs` + `bridge.py`; DLL backup `AtlasUpscale.dll.before-bridge.bak`. Commands: ping, state, shot (--doll, --label), set/sets,
dump, zoom, pan, aa, wait. First test once the game is up: `python3 tools/atlas_upscale/bridge.py state`.
Open risks: HttpListener under Proton/Mono, `SetTempValue` name on the AA setting (the command lists methods if it is wrong),
`ScreenCapture` under D3D11. Still to do from the list below: UnityScope read-through (slice 2), MCP wrapper, log_tail (tail GameLogFull.txt directly).

Slice 1 (a few hours, covers the whole texture return script):
- [ ] Read-only look at UnityScope (https://github.com/Orinks/unity-scope) in a throwaway directory, only to copy the
      approach for tree walk and text extraction. Do NOT install it: BepInEx 5 target, 2 stars, "V1", has an invoke feature.
- [x] (built, untested) HTTP listener in the mod (localhost only, main-thread queue, one in-flight command).
- [x] (built, untested) `screenshot`: lossless PNG of the framebuffer, and of the doll render texture alone.
- [x] (built, untested) `state`; `log_tail` skipped (tail GameLogFull.txt directly). Was: (scene, quality level, AA mode, mip limit, current texture set).
- [x] (built, untested) `texture_set`, `dump_atlas`, `zoom`, `pan`. No FOV or generic `press_key` yet.
- [x] (built, untested) `set_option` for AA Off / SMAA / quality, by calling the game's settings code instead of clicking.
- [x] Python MCP wrapper `mcp_server.py` (8 tools), registered in the repo's `.mcp.json` (untracked). Starts and lists tools; needs a Claude Code restart and approval to appear.

Slice 2 (menu navigation, moderate):
- [ ] `ui_tree`, `ui_find` (by name or text), `ui_click` (fires the button's onClick), `ui_snapshot` + `ui_diff`.
- [ ] Direct commands for the few screens we use: load save, open Idira's inventory, close.
- [ ] A "game ready" signal so loads can be waited on instead of guessed.

Slice 3 (only if needed):
- [ ] Real input via `uinput` into the Proton window, for anything that only reacts to hardware input events.
- [ ] Launch and restart the game from the bridge (Steam `steam://rungameid/2186680`, kill the process).

Caveats: clicking a handler skips any logic that only runs on real input; the invoke feature must stay localhost-only.
Do not start GPU jobs or restart the game unasked.
