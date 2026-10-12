# Why the Topaz textures barely show in game: synthesis and the plan for the next session

Written 2026-10-11 while the user was away. Combines four research reports in this folder (web modding,
Unity mechanisms, decompiled code analysis, screenshot measurement). Nothing below was tested in game: the game was
running when this was written.

## Correction to something I said earlier

I called `QualitySettings.globalTextureMipmapLimit` a strong lead. The code analysis shows it is not. The user's texture
quality is High, which sets the limit to 0, and the compressed atlas is made non-readable with `Apply(false, true)`,
which exempts it from the limit anyway. Ruled out unless the game's memory-pressure controller raises it at runtime
(the new diagnostics log the live value).

## What the evidence says

1. **The belt buckle is a bad test subject, and in game it is already sharper than the texture.** The screenshot
   measurement put the buckle at about 530 screen pixels across versus about 86 pixels in the original texture, roughly
   6 screen pixels per original texel and 3 per Recover texel. The in-game buckle came out sharper than even the Recover
   texture shown at that size. The relief the user sees (teeth, sockets, rim) is normal-map and mesh shading plus mask
   tinting, not the grey painted albedo we upscaled. Two screenshots only, different pose, so treat as suggestive.
2. **TAA is forced onto the inventory camera.** `CameraAntialiasingHelper` copies the global setting (TAA, High) onto the
   doll camera every frame. Softens fine detail. Easy test: set anti-aliasing to Off or SMAA.
3. **Normal and mask maps only got a plain bilinear 2x.** The mod's `Resize` adds no detail to them, so the lit result
   can read softer than the albedo. The mod already picks up normal and mask PNGs from a set folder by texture name
   (`TextureScaler.Scale` calls `LoadOverride(source.name, ...)` for all four maps), so an upscaled `_n` set needs no
   code change.
4. **BC3 compression with a fast min/max encoder, no mips.** `DxtCompressorServiceNew` always writes BC3. Costs
   high-frequency detail equally for 2048 and 4096, so it narrows the gap but does not explain it alone.
5. **Possible doll atlas reset.** `CharacterDollRoom.CreateAvatar` resets `AtlasData` to the original
   (`CharacterDollRoom.cs:472`). If the doll character built an atlas before the mod's patch, it keeps 2048. New logging
   shows the real size.
6. **Possible detail loss before the atlas** (painted render textures created at 1x, ramp/shadow bake passes). Unverified.
   New logging shows painted render texture sizes.
7. **Cannot be checked yet:** the character shader source (not decompilable). Needs AssetRipper/UABEA or a RenderDoc
   capture.

Web research found no existing Rogue Trader HD character texture mod, no config that caps texture or mip level, and
nothing on this game's atlas internals. Related hints, not proven: the RogueTrader_DLSS README lists full-resolution
rendering of the inventory screen as unfinished, and Enhanced Graphics notes an over-aggressive FSR mip bias.

## What is installed and ready

- `AtlasUpscale.dll` with extra logging (backups `.before-dump.bak` and `.before-diagnostics.bak` beside it). Logs, all in
  `GameLogFull.txt` under `[AtlasUpscale]`:
  - at load: quality level, `globalTextureMipmapLimit`, anisotropic filtering, streaming flag, screen size;
  - on every atlas creation: character name, requested size, real atlas size, atlas data used;
  - on F9: the same quality line, the doll camera (pixel size, target texture size, dynamic resolution, AA mode),
    per-texture build lines (source size, atlas rect, painted render texture or none), compressed atlas format, mips,
    readable, filter, aniso, mip bias, loaded and desired mip level, and the `Dump` PNGs before and after compression;
  - on the first set switch: mip counts of the new and current texture.
- Texture set `probe_stripes` (13 files, exactly 2x each texture): 32-pixel cells of black-and-white stripes with
  periods of 1, 2, 4, 8 and 16 pixels, both orientations. Source copy in `data/atlas_upscale/idira_probe_stripes/`.
  It is a test pattern, trivially trashable, not an art asset.

## The return script, in order

1. Restart the game, open Idira in the inventory, press F9. Read the log and the `Dump` folder.
   Rules out or confirms: doll atlas stuck at 2048, 1x painted render textures, wrong format or mips, runtime mip limit,
   doll camera render size and AA mode.
2. F8 to `probe_stripes` at max zoom and take a screenshot.
   Shows: whether the swapped texture is sampled at all, whether 1-pixel stripes (4096 density) survive or average to
   grey, and the effective blur cutoff of the whole BC3 plus TAA plus display chain. The buckle cannot tell us this.
3. Same pose, F8 to `plain resize` and `topaz_recover`, screenshot each.
4. Options, anti-aliasing Off (or SMAA), repeat step 3. If the gap between the two sets grows, TAA is the cause.
5. Use the screenshot protocol from `rt-texture-sharpness-screenshot-analysis.md`: fixed camera, lossless PNG, three
   shots per set interleaved, selection outline off, restart the game after swaps if anything looks stale.
6. Choose a diffuse-dominated area to judge, not the buckle: hair strands, chain links, cloth stitching, the printed
   cloth on the vest.

## Texture names for the normal and mask maps

Read from `Bundles/equipment.orig`: Idira has `<piece>_n` (normal) and `<piece>_m` (mask) at the same size as each `_d`,
for example `BT_Idira_n`, `BT_Idira_m`, `SK_Idira_n`, `HD_Head02Idira_n`. Hair, hands and `UA` also have an `_s` texture
that the mod does not scale (purpose unknown). `HD_IdiraLips_F_HM_d` has no `_n` or `_m`.

## Reading the new log lines

`atlas created ... requested 4096, size 4096` is the expected line, because the log sees the size after the mod's own
prefix doubled it. A 2048 for any character named `Doll ...` is the anomaly (the doll atlas reset).

## Likely next experiment (not run)

Upscale the `_n` normal maps (and possibly masks) as well as the diffuse, since that is where the relief detail lives.
The mod already loads them by name from a set folder. Do this only if steps 1 to 4 say the atlas is really 4096 and the
final image is not just being blurred by TAA. Needs GPU time on the 5080 or the Windows box, not started.
