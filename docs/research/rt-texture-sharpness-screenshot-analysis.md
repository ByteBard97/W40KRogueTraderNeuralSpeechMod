# Idira buckle: texture sharpness vs in-game screenshots

## Conclusion

The sharpness gain from the Topaz upscale at texture level (about 2x by edge width, 5x by Laplacian variance) does not
show up in the two screenshots. It is not that the screenshots are blurry. On every scale-normalised metric the plain
screenshot (1.png) is as sharp as or sharper than the Recover screenshot (2.png), and both screenshots are sharper
than even the Recover texture would be if shown at the same size. So the visible detail on the buckle is not coming
from the albedo (`BT_Idira_d`) at all.

The most likely cause, visible by eye in `screens/sharpness_analysis/montage.png`: the albedo is a flat, low-contrast,
painted grey skull (and it is UV-rotated about 120 degrees relative to the rendered skull). The relief the eye reads as
"sharp" (teeth, sockets, rim bevel, specular glints) is lit normal-map detail plus mesh silhouette. Upscaling only the
diffuse sheet cannot sharpen that. Fraction of the texture gain surviving into the screenshot: about 0% on every metric,
within noise. I can't prove the normal map is the cause from two images, but it fits everything measured.

Confidence is limited: two screenshots, slightly different pose and zoom, different lighting, 2.png carries a green
selection outline. Treat differences under about 15-20% between screenshots as noise.

## Inputs

- Screenshots: `.../images/1.png` (683x887, plain resize set), `2.png` (669x786, topaz_recover set). Both 8-bit RGB PNG, so no
  JPEG artefacts. `3.png` in the same folder is a texture preview (rotated flat skull), not a screenshot, and was not used.
- No other screenshots found. ~/Pictures does not exist, ~/Desktop and ~/Downloads have nothing of the buckle, the
  project `screens/` folder holds only texture previews and `buckle_compare.png`, and there is no Steam screenshots
  folder for app 2186680.
- Textures: `data/atlas_upscale/idira_{orig,topaz_recover,topaz_cgi}/BT_Idira_d.png`. Buckle circle in the 688x380 original:
  centre (632, 48), radius about 42 px. Screenshot buckle outer circle: about 530 px diameter in both (centre/radius picked by eye).
- Everything was resampled with Lanczos to a 480 px buckle diameter, converted to luma, contrast-normalised (2nd-98th
  percentile of the buckle disc, radius 0.46 D), and measured inside that disc. Script: scratchpad `m.py`; crops and
  `metrics.json` are in `screens/sharpness_analysis/`.
- Screen magnification: the original texture buckle is about 86 px across and is shown about 530 px across, so about 6x
  magnification for the original and about 3x for the 2x sheets. The game has plenty of screen pixels to show extra texel detail,
  so a resolution limit on the screen side is not the explanation.

## Results

Edge width is the median 10-90% rise distance (px at 480 px buckle scale) over the strongest 5% of edges, after a sigma 1
pre-blur (so the floor is about 2.5 px). HF fraction is the share of spectral power above 0.15 cycles/px (Nyquist 0.5).

| Image | Lap. variance | Mean grad | p95 grad | Edge width median (px) | Edge width p25 | HF >0.15 |
|---|---|---|---|---|---|---|
| ss1 plain (screenshot) | 0.0302 | 0.0302 | 0.1085 | 3.29 | 2.31 | 0.0187 |
| ss2 Recover (screenshot) | 0.0263 | 0.0329 | 0.1080 | 4.17 | 2.83 | 0.0158 |
| tex orig | 0.0021 | 0.0228 | 0.0714 | 8.11 | 6.88 | 0.0001 |
| tex Recover | 0.0112 | 0.0325 | 0.1431 | 4.21 | 3.95 | 0.0007 |
| tex CGI | 0.0052 | 0.0284 | 0.0971 | 5.55 | 4.53 | 0.0008 |

Ratios (sharper is higher for the first three columns, lower is sharper for edge width):

| Ratio | Lap. var | Mean grad | p95 grad | Edge width (orig/new) |
|---|---|---|---|---|
| Texture: Recover / orig | 5.3x | 1.43x | 2.0x | 1.93x |
| Texture: CGI / orig | 2.5x | 1.25x | 1.36x | 1.46x |
| Screenshot: Recover / plain | 0.87x | 1.09x | 1.00x | 0.79x |

Reading: Recover is clearly sharper than the original as a texture. In the screenshots it is no sharper, and by edge
width and Laplacian variance slightly softer. The edge-width difference (3.3 vs 4.2) could be pose, lighting or my hand-picked
crop centre rather than a real regression; one pair of shots cannot separate those.

## Other things looked for

- Screenshots vs textures: the screenshots are sharper than the Recover texture at the same size (lap. var 0.026-0.030 vs
  0.011, edge width 3.3-4.2 vs 4.2). That is the opposite of "screen is softer than the original texture", so there is
  no sign of render-scale, TAA or DOF blur capping the image. Screenshot p25 edge width (2.3-2.8 px) is close to the 2.5 px
  floor set by my own pre-blur, i.e. the sharpest edges on screen are essentially pixel-sharp. The screenshot HF energy
  is, however, small in absolute terms (about 1.6-1.9% of power above 0.15 c/px), consistent with smooth bevels, not blur.
- Blocky DXT artefacts: in the original albedo, mean absolute gradient at 4 px block boundaries is about 1.5x that of
  other columns (5.2 vs about 3.5 at one phase, both axes), a DXT block signature. Recover reduces this to about 1.0-1.1x
  (5.1 vs 4.7) and CGI to about 1.0x. So the upscales do remove block seams, but this is not visible in the screenshots.
  Block seams were not obviously visible in either screenshot at 1x.
- Ringing: Recover shows thin light/dark halos beside high-contrast edges in the 3x-zoomed crop
  (`detail_nearest.png`), mild. CGI looks more painterly/mottled with noise in flat areas. Neither halo is evident on screen.
- Mip transition blur: not measurable from two stills. With about 3-6x magnification the game should be sampling mip 0, so
  mips are unlikely to matter here, but a streaming/mip-limit setting that clamps to a lower mip would produce exactly this
  "no change" result. Worth ruling out separately, for example by swapping in a deliberately obvious test texture (a
  high-contrast checker or bright red tint) and confirming mip 0 shows it at full resolution.
- Temporal AA softness: no evidence in the stills. Both shots appear to have been taken with a still camera.
- Other caveat: whether the plain-resize set and the Recover set both actually loaded in game was not verified here.
  The slight tonal difference between the two screenshots (2.png lighter, wider rim highlight) hints at lighting or pose
  differences, not a texture change.

## Recommended controlled screenshot protocol

1. Fix the camera: open the inventory, zoom in on the buckle, then do not touch zoom or rotate again between sets.
   Note the pose (or use a save with a fixed inventory camera) so it is repeatable.
2. Only change the texture set between shots. Quit and restart the game after swapping files so streaming and cache
   state are fresh. Same time of day and area, same character animation idle (wait about 3 seconds so it is still).
3. Take 3 shots per set (original, plain-resize, Recover, CGI), in an interleaved order (A B C D A B C D ...) to expose drift.
4. Use the same capture method each time and save lossless PNG. Steam's screenshot key (F12) saves the native
   framebuffer, which is the best option for comparison (no window scaling, no UI overlay differences). Avoid
   snipping a scaled window. Keep the game at the same resolution and render scale, and disable UI overlays and the selection outline.
5. Add one reference object that does not change (for example a non-upscaled item) in the same frame, to confirm
   exposure and softness are the same across shots.
6. Also test the mip/streaming hypothesis with a loud marker texture (point 'Mip transition' above), and compare an
   Idira albedo-only change versus a normal-map upscale, since the metrics suggest normal maps drive the visible relief.
7. Analyse with the same script (crop to equal buckle diameter, Lanczos, normalise, compare edge width and Laplacian variance).
   With 3 shots per set you get a noise floor for the pose-to-pose variation.
