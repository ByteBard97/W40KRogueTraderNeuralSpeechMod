# First in-game measurements through the game bridge (2026-10-11)

Run with `tools/atlas_upscale/bridge.py` and `compare_sets.py`, Idira in the inventory, zoom 0.5 (head and shoulders),
anti-aliasing TAA and Off, sets plain resize / topaz_recover / topaz_cgi / probe_stripes. Screenshots are under
`screens/bridge_run1/` (git-ignored). Lossless 3840x2160 framebuffer shots, label hidden.

## What is now established
- The Idira atlas is a real 4096x4096 (DXT5, 1 mip, filter bilinear, aniso 1, mip limit 0). Slots are 2x sized
  (BT_Idira_d_x2 1376x760, SK_Idira_d_x2 2184x1352, ...). Painted render textures are 2x as well (e.g. 1376x520).
  So the "doll atlas reset to 2048" and "painted at 1x" suspects are ruled out.
- The stripe probe shows on the model: stripes with 2, 4 and 8 pixel periods in the 4096 atlas come through crisp. The 1 pixel period
  averages to grey (screen density is lower than texel density, expected). TAA softens the fine stripes slightly; it does not erase them.
  So the render chain preserves 4096 detail. This is the main answer to "does the game throw away the extra resolution".
- Plain resize vs Recover, whole crop: mean edge energy 4.07 vs 4.27 under TAA, 3.78 vs 3.97 with AA off (+5% both).
  Mean absolute pixel difference 8.9 (TAA) / 6.4 (off) on 0..255. TAA vs Off on the same set differs about as much as the sets do.
- Lips (HD_IdiraLips_F_HM_d): Recover is clearly sharper (lip creases visible) but has a bright white halo along the upper lip edge, an upscaler
  artifact, not real detail. Scarf and collar: nearly identical in both sets, only slightly crisper grain on the red trim.
- First reading: at the inventory's normal zoom the extra detail is not visible because most of these textures are smooth, painted or grey base
  layers, and the real surface relief comes from the normal map and shading. The Recover gain is real but small, and
  concentrated in a few textures (lips), where it also introduces halos.

## Next experiments, in order
1. Upscale the `_n` normal maps (and maybe `_m`), compare in the same crop. Needs GPU time, ask first.
2. Check the Recover halo on other textures; consider blending Recover with plain resize, or sharpening less, for the lips.
3. Measure at a closer zoom (value 0.4 to 0.45) so one screen pixel is under one texel.

## Bridge notes learned the hard way
- `shot --doll` captures the doll camera's render texture, which here holds only the dim background scene, not the character. Use the framebuffer shot.
- `zoom value=0..1`: 1 is the default view, 0.5 is head and shoulders, 0 is the closest limit and goes through the character with the mod's x2.5 range.
- A stuck tooltip comes from clicking a hover-only element; `xdotool mousemove` to an empty spot clears it.
- `texture_set` no longer waits for every character to merge (it never did for some); it waits up to 90 frames plus settle.
- The main menu needs a real Enter key ("press Enter to use a keyboard"); `restart_game.sh` does it with xdotool.
  After Continue the loading screen ends at "Press any key" (space).
