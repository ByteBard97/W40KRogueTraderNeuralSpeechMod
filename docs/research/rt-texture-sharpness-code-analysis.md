# Why upscaled character textures look only slightly sharper in the dollroom

Read-only analysis of the ILSpy decompile (`C:\Users\geoff\ilspy-scratch\full`, copies in the session scratchpad) plus
`tools/atlas_upscale/*.cs` and the game logs. Shader source is NOT available (see section 5).

Environment from `Player.log` / `general_settings.json`: Unity 6000.0.64f1, Direct3D 11.0, RTX 5080. Settings:
quality Ultra, textures High (`globalTextureMipmapLimit` = 0), antialiasing **TAA / High**, upscaler mode Fsr with
fsr-mode Off (native res, sharpness 0.92). Mod log: `factor 2, texture set 'topaz_recover'`,
`atlas data Human_AtlasData: 2048 -> 4096` (logged once). Atlas compression lines show `GPU=4-6ms` for all three
channels, so the GPU path is used (no CPU fallback warnings).

## Summary: ranked hypotheses

1. **Screen-pixel / render-target limit (most likely).** The doll view is a RenderTexture sized to the RawImage rect
   times the canvas scale factor (`DollRoomTargetController.cs:54`, `DollRoomBase.cs:92,200`), i.e. roughly
   screen resolution (1024x1024 fallback at `DollRoomBase.cs:88`). A head filling ~900 px shows a 512-texel region of the
   old 2048 atlas at about 1.8 px/texel, so the old atlas already nearly saturates the screen. 4096 needs the face to
   fill roughly 2x more screen pixels before it shows. Evidence for: RT size derivation. Against/unknown: actual zoom
   level reached; the mod already raises zoom range x2.5 (`Patches.cs` DollCamera_Start_Patch), so test at max zoom.
2. **TAA on the doll camera.** `DollCamera.OnEnable` adds `CameraAntialiasingHelper` (`DollCamera.cs:164`), which every
   frame copies the global AA setting (TAA/High here) onto the doll camera (`CameraAntialiasingHelper.cs` UpdateSettings).
   TAA resolves with history blending and softens fine detail, especially on a mostly static subject. Then the RT is
   shown through a UI RawImage and may be resampled again. Test by setting AA to Off or SMAA in options and comparing.
3. **BC3 (DXT5) compression of the whole atlas, no mips, "MiniMax" fast encoder.** See section 1. All three
   channels (diffuse, normal, masks) are compressed to BC3 with a fast min/max endpoint encoder. This costs
   high-frequency colour detail and acts the same for the 2048 and 4096 atlas, so it narrows the visible gap but does
   not explain it alone. Moderate likelihood as a contributing factor.
4. **Detail is lost before the atlas (ramp/shadow bake passes and painted textures).** Diffuse goes through
   `Hidden/CharacterShadowBake` and `Hidden/CharacterDiffuseBake` (`CharacterAtlas.cs:292-302`) with
   `RampShadowTexture`, which the mod does not scale, and `paintedTextures.Get(...)` (`CharacterAtlas.cs:289,303`)
   can return a recoloured RenderTexture instead of the source texture. If a painted RT was created at the original
   size (for example cached before the mod's RepaintTextures prefix, or created inside RepaintTextures from a
   texture other than the four the mod scales), the bake receives a 1x image bilinearly stretched to 2x. Unverified;
   needs one log line (section 7).
5. **Normal and mask channels are plain bilinear 2x.** Only diffuse has AI detail (`Resize` in `TextureScaler.cs`
   for textures without a PNG). The character shader very likely lights with normal/masks, so a smooth normal map
   over sharp albedo reads as soft. Cannot confirm without shader source.
6. **Lighting/shader hides albedo contrast (unverified).** Cutout character shader (`Character_Diffuse_Cutout`),
   `_BaseMap`/`_BumpMap`/`_MasksMap`; roughness, emission and metallic come from the masks atlas. Strong ramps, SSS or
   specular could mask micro-contrast. No sampler constants visible in C#.
7. **Mod-side defects that could defeat the intent (low, but check).** Section 6.

Ruled out by the code: a texture-quality option re-downscaling the atlas (the mod keeps ScaleFactor consistent,
section 3), streaming mipmaps or anisotropy set from game code (not found), CPU compression fallback (logs show GPU).

## 1. DxtCompressorServiceNew (`Kingmaker.Visual.CharacterSystem/DxtCompressorServiceNew.cs`)

- Path used: `CompressAsync` calls `CompressTextureGPU` (`CharacterAtlas.cs:361`) unless `ForceCpu` is 1/2. It wraps
  `CompressTextureGPUSync(textureIn, 0, 0, atlasType)` (lines ~120-190 of the decompile).
- Format: output `new Texture2D(w, h, (TextureFormat)12 /*DXT5 = BC3*/, mipChain:false, linear: !isSRGB)`. **Always BC3**,
  for diffuse, normal and masks alike. Not BC7, not BC1.
- **Mips: none.** The `false` is the mipChain flag, and `Graphics.CopyTexture(rt, 0,0,0,0,w/4,h/4, tex, 0,0,0,0)` copies
  only level 0. The CPU fallback (`CompressTexture`) does produce a mip chain (BC1 if no alpha, BC3 with alpha, via
  StbDxtSharp `CompressDxt1/5` with `CompressionMode 0`), but is not used here. Consequence: magnification is fine,
  minification (character far from camera) is unfiltered, but this does not hurt a zoomed-in close-up.
- Resolution: `targetWidth/Height` are 0, so the compress size = the RT size (4096 with the mod). No reduction.
  Internally: blit the atlas RT into a temporary ARGB32 RT with `RenderTextureReadWrite.Linear (1)`, then a compute
  shader `Resources/CharacterSystem/StbDxt_GPU_MiniMax` (kernel `CompressStbDxt`, params `InputWidth/Height`,
  `SRGBMode`, `DebugEnabled`) writes 4x4 blocks into a (w/4 x h/4) RG32/GraphicsFormat 40 RT. The "MiniMax" name
  means endpoints taken from block min/max colours, a low-quality-but-fast BC encoder. No quality parameter.
- Possible precision issue (same with and without the mod): for the sRGB diffuse atlas the blit goes sRGB RT -> Linear
  ARGB32 RT, which stores linear values in 8 bits (dark tones lose precision), after which `SRGBMode=1` presumably
  converts back. Needs the compute shader to confirm.
- Memory/quality: `Texture2D.Apply(false, true)` makes the atlas non-readable, so the mod cannot `GetPixel` it; use
  `AtlasDump` or a RenderTexture copy.

## 2. CharacterAtlas (`CharacterAtlas.cs`)

- Ctor (73-81): `ScaleFactor = (int)targetResolution / size`. Materials `Hidden/CharacterAtlasGenerator`,
  `CharacterShadowBake`, `CharacterDiffuseBake`, `RoughnessLightenBlend`.
- Build (152-333): RT `(size,size)`, ARGB32, `ReadWrite` Linear for non-diffuse and **sRGB for diffuse**
  (`(Channel != 0) ? 1 : 2`), Bilinear, aniso 1, `useMipMap = autoGenerateMips = !isPlatform51` (mips on for PC).
  A ping-pong static temp RT (`_PreviousTex`) is used. Clear colour (0,0,0,0); masks (0.85,0,0,0); normal (.5,.5,1,1).
  Per texture: `_SrcRect = (0,0, rect.w/(srcW/ScaleFactor), rect.h/(srcH/ScaleFactor))` and `_DstRect` in atlas UV.
  When the rect equals the source size this is a 1:1 copy, no resampling.
- Diffuse chain: if `UseShadowMask`, first a shadow-bake blit with `RampShadowTexture`; textures not ending `_D` are
  skipped from the diffuse-bake step (`continue` at 298); then the generator blit.
- UpdateMaterial (484-500): diffuse -> `_BaseMap`; normal -> keyword `_NORMALMAP` + `_BumpMap`; masks -> keyword
  `_MASKSMAP` + `_MasksMap`. Build also sets `_UseNormalMapAtlas`. No texel-size, mip-bias or sampler overrides in C#.
  The atlas Texture2D keeps default filter (bilinear, no mips, aniso 1).
- Note `Build` calls `UpdateMaterial(material, RT)` first (uncompressed RT with mips, mip-mapped), then `OnAtlasCompressed`
  swaps in the BC3 no-mip texture. Both are visible at different times; the final one is the BC3.
- Character.MergeOverlays (`Character.cs:2745-2870`): `atlasSize = Max(2048 >> globalTextureMipmapLimit, 512)`.

## 3. Texture quality settings and the mod's scaling consistency

- `GraphicsSettingsController.cs:~492-505`: option Low/Medium/High sets `QualitySettings.globalTextureMipmapLimit`
  to 2/1/0 (or `BuildModeUtility.Data.ForceTextureMipLevel`). It is read in `Character.MergeOverlays` (`atlasSize`),
  so **Low gives 512, Medium 1024, High 2048**. The user's setting is High, so 2048 and ScaleFactor 1.
- `TexturesQualityController.cs:~100-180`: a memory-pressure controller can raise `globalTextureMipmapLimit` (or
  per-group limit bias via `SetTextureMipmapLimitSettings`) at runtime when system memory is low, and `CheatSetMipMapLevel`.
  This would shrink source textures and the atlas for *new* characters. Worth logging `QualitySettings.globalTextureMipmapLimit`
  in the mod. No `anisotropicFiltering`, `masterTextureLimit`, `streamingMipmaps` or mip-bias settings anywhere in game C#
  (grep over all decompiled .cs); aniso/streaming live in the Unity quality asset, which is not in C#.
- Mod consistency: Prefix multiplies `atlasSize` by 2 and clones `AtlasData` with `targetResolution` x2 and all
  rect/gpu coords x2 (`Patches.cs`). At High: size 4096, target 4096, ScaleFactor 1 (as in vanilla 2048/2048). At Medium: vanilla size 1024,
  target 2048, factor 2; with the mod size 2048, target 4096, factor 2. **Consistent at every quality level.**
  Source textures are scaled x2 so `srcW/ScaleFactor` still maps rect 1:1. Nothing in the game re-reads the original
  `targetResolution`: the only users are `CharacterAtlas` (via the instance's `AtlasData`) and the augmentation atlas
  (`AugmentationAtlasController.cs:57`, uses `UIConfig.AugmentationAtlasData`, not patched, separate).
- Watch: `CharacterDollRoom.CreateAvatar` sets `character.AtlasData = originalAvatar.AtlasData` (`CharacterDollRoom.cs:472`)
  every time, resetting to the original. The mod's `GetAtlas` prefix re-clones, but only `GetAtlas` calls are patched.
  `GetAtlas` constructs `CharacterAtlas` only once per character (`m_Atlases` lookup, `Character.cs:2868-2876`), so if a
  doll `Character` ever built its atlases *before* the patch/with the original data, it keeps a 2048 atlas. Atlas
  dimensions in the dump will show this directly. Also `MaxAtlasSize` branch is dead code (`if (true)`).

## 4. Doll room render path

- `DollRoomBase.EnsureRenderTexture` (192-203): `new RenderTexture(w, h, 0, RenderTextureFormat.ARGBHalf)` with
  `(w,h) = RawImage rect size * CanvasScalerWorkaround.scaleFactor` (or reference resolution * scale if rect is 0).
  No depth buffer in the RT constructor (depth handled by pipeline). Set as `DollCamera.targetTexture` and
  `RawImage.texture`. So the final image is screen-resolution, shown 1:1 through the UI.
- Pipeline is Owlcat's `WaaaghPipelineAsset` (URP-derived). Upscaler options map FSR/Point/Linear; with `fsr-mode Off`
  the 3D view is native. Whether the doll camera obeys the pipeline render scale is not visible in C#; log
  `camera.pixelWidth` and `targetTexture.width`.
- Per frame `CameraAntialiasingHelper` forces TAA/SMAA/Off onto the doll camera. Post processing: doll room has Volume
  profiles `m_DollRoomPostProcessVolume` / `CharGen` with a `CustomPostProcessOverride` (dissolve / background properties).
  Layer 15 is used for doll renderers.
- Zoom limits `m_MinZoom/m_MaxZoom` are negative toward the target; the mod scales them by 2.5.
- The doll avatar is a separate `Character` ("Doll [name]") with its own atlases, rebuilt via `CopyEquipmentFrom`, `OnStart`.

## 5. Character shader

Shaders referenced by name in code: `Hidden/CharacterAtlasGenerator`, `Hidden/CharacterShadowBake`,
`Hidden/CharacterDiffuseBake`, `Hidden/RoughnessLightenBlend`; runtime material `Character_Diffuse_Cutout`
(renderer `Renderer_Character_Diffuse_Cutout` in logs). Property ids come from `RogueTrader.Code.ShaderConsts.ShaderProps`
(`_BaseMap, _BumpMap, _MasksMap, _PreviousTex, _SrcRect, _DstRect, _AlphaMask, _Roughness, _Emission, _Metallic,
_UseNormalMapAtlas, _IsEmpty, _Mask`). Shader source is compiled into the bundles and is not decompilable here, so
how diffuse mixes with masks/ramps/normal, and any mip bias, is **unknown**. A `grep` of the install for the compute
shader name turned up nothing readable. To read them, extract with AssetRipper/UABEA from the bundles.

## 6. Mod-side issues (`tools/atlas_upscale`)

- `Resize()` is a plain bilinear blit to ARGB32 RT then `ReadPixels`: fine for normal/mask (no new detail) but means
  ~all non-PNG textures are only smooth 2x copies. Expected.
- `LoadOverride`: PNG decoded with `ImageConversion.LoadImage` into `Texture2D(2,2,RGBA32,mipChain true,linear)`. If the
  PNG size differs from `source*2` it is bilinearly `Resize`d again (second resample). Check topaz output sizes equal
  exactly 2x each source, or you get an extra blur.
- `CycleVariant`/`RefreshOverrides` use `Graphics.CopyTexture(fresh, entry.Texture)`. This needs equal mip counts and
  formats; if `LoadImage` produced a different mip count than `Resize`'s `Apply(true,false)` output, the copy
  logs an error or leaves stale mips. Since the atlas blit samples mip 0 at 1:1 this mostly does not matter for the
  final look, but it can leave an old variant visible. Verify with `Texture.mipmapCount` on both.
- The `ActiveTexture` replacement happens in a Prefix on `RepaintTextures`. Textures not in `bodyPart.Textures`
  (ramp/shadow textures, augmentation overlays, `m_AugOverlayBodyParts`) are not scaled. Hair/cloth ramps are separate.
- `Scale()` caches per source; `AddSecondaryTexture` errors "Textures must be the same size" if normal/mask/diffuse
  are scaled inconsistently (look for that string in the log; none was seen).
- Checksum grid uses `GetPixel` on readable mod textures: fine. It cannot detect whether the atlas (non-readable BC3)
  actually changed. The `AtlasDump` shows the pre-compression RT.
- Nothing in game code overwrites the scaled textures later: they are only read.

## 7. Next debugging steps (all in the mod, nothing to install into the game files)

1. Log in `CharacterAtlas.Build` (postfix) and `CompressTextureGPUSync` (postfix): channel, `m_Size`, `ScaleFactor`,
   result `AtlasTexture.width/height/format/mipmapCount/anisoLevel/filterMode`. Confirm the **doll** `Character`'s
   diffuse atlas really is 4096 BC3 (hypothesis 7 / doll AtlasData reset).
2. Log per sorted texture in `Build`: `sortedTexture.ActiveTexture.name/size`, and `paintedTextures.Get(sortedTexture)`
   RT size or null. Any painted RT at 1x size confirms hypothesis 4.
3. Log `QualitySettings.globalTextureMipmapLimit`, `anisotropicFiltering`, `Texture.GetGlobalAnisotropicFilteringLimits`,
   `streamingMipmapsActive`, and the doll camera `pixelWidth/Height`, `targetTexture.width/height`, `allowDynamicResolution`
   plus its `WaaaghAdditionalCameraData.Antialiasing`.
4. Experiment, no code: set Anti-aliasing to Off or SMAA in game options, view at max zoom, compare `topaz_recover` vs
   `plain resize` with F8. If the gap grows, TAA is the culprit.
5. Take a 1:1 screenshot at max zoom of a known high-detail area and compare to the 4096 AtlasDump crop at the same
   scale. If the dump is much sharper than the screenshot, loss is at BC3/render/TAA; if the dump itself is soft, the
   loss is in the bake chain (hypothesis 4, 5).
6. Dump the atlas **after** compression (copy BC3 via `Graphics.CopyTexture` into a readable Texture2D of the same format,
   or `AsyncGPUReadback`) and diff against the pre-compression RT dump to measure BC3 loss directly.
7. Extract the shaders from the bundles (AssetRipper/UABEA, or RenderDoc a frame) and read `Character_Diffuse_Cutout`
   for how `_BaseMap` is combined with masks/ramps, plus any `_MipBias`/`SAMPLE_TEXTURE2D_BIAS`.
   A RenderDoc capture of the doll frame also shows the true RT size and the sampler state.
8. Optional probe patch: postfix `CharacterAtlas.UpdateMaterial` to set `texture.anisoLevel = 16`, `mipMapBias = -0.5`
   (or `FilterMode.Trilinear`) on the final atlas, to see if sampler state matters at the zoom used.
