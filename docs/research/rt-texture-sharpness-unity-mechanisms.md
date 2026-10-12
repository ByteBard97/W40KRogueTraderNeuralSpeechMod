# Why a 2x atlas may not look sharper in Rogue Trader: Unity mechanisms

Status: desk research. Searches covered Unity docs and forums; nothing here was tested in the game. Items marked (unverified) come from my knowledge of Unity/D3D behaviour, not from a fetched page.

Engine version: Owlcat's official modification template is for Unity 6000.0.52f1 per a Steam Workshop modding guide (search result; the old RTModificationTemplate GitHub repo says 2021.3.3f1, which looks stale). Confirm the game's real version from `globalgamemanagers` / `UnityPlayer.dll` file version or the `Player.log` header line. The 6000.0 docs are the right reference.

## Summary: ranked hypotheses

1. **Mip limit / quality setting silently dropping mip 0 of `AtlasTexture` (HIGH priority, cheap to test).**
   `QualitySettings.globalTextureMipmapLimit` applies to 2D textures including run-time-created, readable ones. It does not apply to render targets. So the RT atlas is full size but the compressed Texture2D copy can be loaded without mip 0 (4096 becomes 2048) if the game's "Texture Quality" option sets the limit above 0 and the texture is readable or has no `ignoreMipmapLimit`. Exempt: run-time textures made non-readable via `Apply(makeNoLongerReadable:true)`, and textures flagged `ignoreMipmapLimit` or assigned to a limit group that allows it. This is the one mechanism that would make the 4096 atlas literally equivalent to the old 2048 one.
2. **Mip selection from texel/screen ratio is not the issue when magnified, but a wrong/low mip chain is (MEDIUM).** If `AtlasTexture` was created with mipCount that omits or misorders levels, or `DxtCompressor` only writes mip 0 while upper mips are blank/blurry, sampling could choose lower mips. Magnified views should sample mip 0, so this only matters if hypothesis 1 holds or the mip chain is wrong.
3. **Content-side: atlas region mapping (MEDIUM).** The mod's source textures are 2x sharper, but if `_SrcRect/_DstRect` still target the old 2048 layout scaled up, or sources are downsampled during Blit (bilinear minification of a 2x source into a 1x dst rect), detail is lost before compression. Check that dst rects were actually doubled, and that sources are blitted 1:1.
4. **Other-map dominance: normal/mask/metallic/lighting + material specular (MEDIUM).** Characters in a PBR-ish pipeline are lit by normal maps and gloss; a sharper albedo shows less than expected under heavy shading, especially for armor with small regions. Compare the albedo-only debug view.
5. **Final image softening: TAA/FSR/DLSS, render scale, DoF, film grain (MEDIUM, easy to test).** Temporal AA and upscalers blur at the pixel level, which hides texel-level gains. Disable in graphics options first.
6. **BC1/BC3/BC7 compression artefacts (LOW-MEDIUM).** BC1 stores 4x4 blocks with two endpoints; fine detail and colour transitions get flattened. If the DXT compressor is a real-time GPU one (fast, low-quality mode), 4096 BC1 can look nearly as soft as 2048 at full quality. Test by dumping the atlas RT vs the compressed texture and diffing.
7. **Anisotropic filtering settings (LOW).** Only affects oblique viewing angles; does not cap mip 0 sharpness head-on. Can add blur on sloped surfaces if Disabled and filter is Bilinear.
8. **Mipmap streaming (LOW).** Runtime-created textures cannot have `streamingMipmaps` set (it is read-only and set in import settings), so streaming budget should not apply. The system loads low mips only for imported streaming textures.
9. **sRGB/linear mismatch (LOW for sharpness).** Wrong colour space changes contrast, not resolution, but wrongly gamma-handled mip generation can lose contrast in small detail.
10. **Texel density vs screen density (LOW-MEDIUM, environmental).** At 1080p, a character head covers perhaps 200-400 px; if the atlas holds ~2048 px for many pieces, a magnified view often exceeds 1 texel per pixel already, so 2x texels is invisible. Check pixels-per-texel at your zoom.

## Details

### 1. Global mipmap limit (`masterTextureLimit` renamed `globalTextureMipmapLimit` in 6000)
- Doc (6000.0): https://docs.unity3d.com/6000.0/Documentation/ScriptReference/QualitySettings-globalTextureMipmapLimit.html . "Only works on 2D textures and 2D texture arrays." Does not apply to: built-in editor resources, run-time textures that are not readable (after Apply with makeNoLongerReadable true), non-persistent editor textures, render targets, terrain masks, virtual-texture instances. Width/height queries return the original size, so `tex.width == 4096` does NOT prove mip 0 is resident.
- Per-texture: `Texture2D.mipmapLimitGroup` (set via constructor) and `ignoreMipmapLimit` https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Texture2D-mipmapLimitGroup.html . Office Hours thread: https://discussions.unity.com/t/office-hours-question-global-texture-mipmap-limit-globaltexturemipmaplimit/1541211
- Behaviour: readable run-time textures follow the limit; "may take a few frames" to apply to existing textures. Unity then holds fewer mips on the GPU, so mip 0 is never sampled.
- Graphics.CopyTexture doc notes mismatched limits between src and dst cause mapping problems; use region overload: https://docs.unity3d.com/ScriptReference/Graphics.CopyTexture.html . A forum report of black textures with nonzero limit: see the Discussions thread linked from the search (2022.3).
- Likelihood: high, because Rogue Trader exposes texture quality in options and a full/half/quarter setting almost certainly maps here (unverified; check the Player log and settings).
- Tests:
  - Read `QualitySettings.globalTextureMipmapLimit` at runtime (UnityExplorer or a UMM mod log line).
  - Read `AtlasTexture.mipmapCount`, `.format`, `.isReadable`, `.mipmapLimitGroup`, `.ignoreMipmapLimit`, `.streamingMipmaps`, `.loadedMipmapLevel`, `.desiredMipmapLevel`, `.calculatedMipmapLevel` (loaded/desired are valid even for non-streaming, partly).
  - Force: set `globalTextureMipmapLimit = 0` and set `AtlasTexture.ignoreMipmapLimit` (needs creation time; Harmony-patch the constructor call or recreate) and compare screenshots.
  - Log `Texture.GetRawTextureData().Length` of the atlas: if it matches 4096 BC format with mips (e.g. BC1 4096 + full chain = ~10.7 MB, BC3/BC7 ~21.3 MB) and the GPU texture is smaller, the limit applied. RenderDoc texture size for the sampled resource gives the truth (see checklist).

### 2. Texture streaming
- Manual: https://docs.unity3d.com/6000.3/Documentation/Manual/TextureStreaming-use.html and API https://docs.unity.cn/Manual/TextureStreaming-API.html . `Texture2D.streamingMipmaps` is read-only at runtime (https://discussions.unity.com/t/texture2d-streamingmipmaps-cannot-be-assigned-to-it-is-read-only/929802); mip streaming of generated textures is not supported (https://discussions.unity.com/t/textures-mip-streaming-for-runtime-generated-textures/729703).
- Manual says textures not driven by a Renderer need `requestedMipmapLevel`; otherwise low mips load. That is for streaming-enabled textures only.
- Test: log `atlas.streamingMipmaps` (expect false), `QualitySettings.streamingMipmapsActive`, `Texture.streamingTextureCount`, `desiredMipmapLevel` vs `loadedMipmapLevel`.

### 3. Anisotropic filtering
- Support article: https://support.unity.com/hc/en-us/articles/210606003 . Quality setting Disable = off for all; Enable = per-texture; Force Enable = all textures. With Forced On, per-texture anisoLevel 0 is ignored (older docs) or raised (1 to 9 become 9). Per-texture `anisoLevel` 1 = no aniso.
- Unity docs say on some APIs enabling aniso also enables trilinear; Metal/Vulkan/OpenGL set separately. Property doc: https://docs.unity.cn/ScriptReference/Texture-anisoLevel.html
- The decompiled RT uses anisoLevel 1 on the RT, but the Texture2D's level is what matters for sampling. Unknown, must read.
- Effect: reduces blur at grazing angles only. Head-on zoom: negligible.
- Test: read `atlas.anisoLevel`, `QualitySettings.anisotropicFiltering`; set 16 and Force Enable.

### 4. Filter mode, mip bias, mip selection
- FilterMode docs (old but valid): Bilinear averages 4 texels; Trilinear additionally blends between mip levels. https://docs.unity3d.com/462/Documentation/ScriptReference/FilterMode.html . In Bilinear, mip level is chosen without blending (point mip filter) (unverified; standard D3D MIN_MAG_LINEAR_MIP_POINT mapping). The chosen level is based on UV derivatives, so under magnification mip 0 is used and the filter is just bilinear.
- Consequence: when magnified past 1 texel per pixel, you see bilinear-interpolated blur no matter the resolution; doubling the texels halves that blur only if the camera is that close. Quantify (see point 10).
- `Texture.mipMapBias` (`mipMapBias`): a positive bias selects blurrier mips earlier. Check `atlas.mipMapBias`; also shader-side `SAMPLE_TEXTURE2D_BIAS` or `_MipBias` in the character shader, and URP/HDRP-style "Texture mip bias" for upscalers (DLSS/FSR set negative bias; an upscaler with a wrong bias can look soft). Check if the game applies a global `Shader.SetGlobalFloat` mip bias.
- Test: set `mipMapBias = -1` or `Trilinear` on the atlas and compare; or use a shader debug that outputs `CalculateLevelOfDetail`.

### 5. Compression: BC1 / BC3 / BC7
- BC1 (DXT1): 4 bpp, 2 endpoints per block, no alpha (1-bit). BC3: same colour as BC1 plus 8-bit alpha block. BC7: 8 bpp, much better; needs compute or slow encoders. A runtime GPU compressor ("DxtCompressorService") typically uses BC1/BC3 with fast endpoint search, producing blocking and chroma loss on thin lines and text. Sharpness at texel level is the first casualty.
- Unity texture format docs list the supported formats; the real-time compression in Unity (`EditorUtility.CompressTexture`/`Texture2D.Compress`) is a low-quality fast path. The game's own compressor is custom, so its quality is its own.
- Test: read `atlas.format` (expect `DXT1`/`DXT5`/`BC7`). Dump the RT with `ReadPixels`/AsyncGPUReadback and the compressed bytes decoded offline; compute PSNR/SSIM of decoded BC vs RT and the sharpness (Laplacian variance) at 2048 vs 4096. If the decoded 4096 is only slightly sharper than decoded 2048, compression is the cap.
- Alpha: if atlas holds packed channels (e.g. smoothness in alpha) and BC1 is used, data may be discarded. Check what channels the atlas pages carry.

### 6. Automatic mip generation quality and RT blit
- `RenderTexture.useMipMap = true` with `autoGenerateMips = true` generates mips with a box filter on `Blit` end/at use (Unity generates when the RT is next sampled or after `Graphics.SetRenderTarget` completes; with explicit `GenerateMips()` otherwise). Box-filter mips are fine but slightly soft; irrelevant under magnification.
- Blit from a source into an RT sub-rect with Bilinear sampling: if the source is larger than the dst rect (source 2x but dst rect not doubled), that is a 2:1 downsample with bilinear = aliasing and loss. Verify dst rect math. Source textures with mips: the custom shader's `tex2D` in a pixel shader samples with derivatives, so it uses an appropriate mip; sampling with `tex2Dlod(…,0)` or a non-mipped source would alias.
- sRGB: an sRGB RT blended/blit with a shader that samples a non-sRGB source (or vice versa) gives contrast shifts, not resolution loss. Mip generation on sRGB RTs: Unity generates in linear when sRGB is declared, which is correct.
- Graphics.CopyTexture requires matching format, dimensions and mip count between src and dst; RT (ARGB32) to compressed Texture2D is NOT valid, which is why the game uses a compressor pass (compute shader writing to a BC-format-compatible RenderTexture e.g. `GraphicsFormat.R32G32B32A32_UInt` 1/4 size then CopyTexture to the BC texture) (unverified, typical). Doc: https://docs.unity3d.com/ScriptReference/Graphics.CopyTexture.html . Mismatched mip counts raise errors (issue tracker https://issuetracker.unity.com/issues/14503/...). Because BC block-copy RT has to cover each mip, the compressor may only process mip 0 and then leave other mips to `Apply`/regeneration; `DxtCompressorServiceNew` might generate mips via a second pass at lower quality. Inspect.
- Test: Harmony-postfix the compressor to log dst `mipmapCount`, format, whether each mip level is written, and the number of dispatches.

### 7. Render scale, upscalers, AA
- If the game has DLSS/FSR/XeSS or TAA (Rogue Trader exposes quality presets; unverified specifics), the rendered image is lower-res and temporally smoothed. Test with upscaler off, AA off, render scale 100% (or supersampled), and with the camera near-clipped at an extreme close-up.
- Test using RenderDoc: look at the character draw's output before post processing.

### 8. Post-processing
- DoF, bloom, film grain, chromatic aberration, sharpen. Toggle each in options or via the game's volume/profile. Compare screenshot crops at pixel level.

### 9. Texel density vs pixel density
- Compute: texels per screen pixel = (atlas_px * uv_span_of_region) / (on-screen px of that region). If region is 512 px of a 2048 atlas and appears 300 px on screen at your zoom, the original is already 1.7 texels/pixel (minified), so 2x gains nothing; only when it is below 1.0 do extra texels matter. At typical 1080p isometric view the head is maybe 100-200 px high.
- Test: a UV checker or a debug shader with texel-density colours; or log the UV rect size per atlas region (known from the atlas generator).

### 10. Other maps dominating
- The character shader samples normal, mask/metallic/roughness and often an emissive/AO map that likely live in separate atlases (or in the same atlas pages). If the mod only upscaled the diffuse page, specular/normal reflect old detail. Test by rendering albedo-only (unlit debug) and comparing 1x vs 2x.

## Debugging checklist (cheapest first)

1. Run the game with the Player log open; grep the header for the Unity version and graphics API (D3D11/12/Vulkan), and for "mipmap" messages.
2. Check in-game graphics options: set texture quality to the highest, turn off TAA/DLSS/FSR, depth of field, film grain; reload the area and compare screenshots at the same camera position.
3. Same-camera A/B screenshot of 1x vs 2x atlas with the camera at max zoom; measure Laplacian variance on a fixed crop. If difference is small, continue.
4. UnityExplorer (or a tiny UMM mod) print for the live `AtlasTexture` and the RT: `width`, `height`, `format`, `mipmapCount`, `isReadable`, `filterMode`, `anisoLevel`, `mipMapBias`, `streamingMipmaps`, `desiredMipmapLevel`, `loadedMipmapLevel`, `ignoreMipmapLimit`, `mipmapLimitGroup` (if accessible via reflection), plus `QualitySettings.globalTextureMipmapLimit`, `anisotropicFiltering`, `streamingMipmapsActive`, `Screen.currentResolution`, and the camera render scale.
5. Force `QualitySettings.globalTextureMipmapLimit = 0`, `anisotropicFiltering = ForceEnable`, `AnisotropicFiltering` 16; set `atlas.mipMapBias = -0.5`, `filterMode = Trilinear`; screenshot again.
6. Harmony postfix on the atlas constructor (`new Texture2D(w,h,format,mipCount,...)`): log the actual arguments; ensure width/height/mips are 4096/12 and that the mod's atlas size patch applied to every code path (including the DXT compressor's own size constants, RT copy rects, and any hard-coded 2048).
7. Dump the atlas pre-compression (RT via `ReadPixels`) and post-compression (decode `GetRawTextureData`) and compare sharpness metrics; if decoded 4096 is no sharper than 2048, compression quality is the cap.
8. RenderDoc capture (Windows, D3D11) of the character draw: inspect the bound `AtlasTexture` resource (size, format, mip count, mips present) and the Texture Viewer at mip 0; check the sampler state (filter, aniso, LOD bias). If the resource shows 2048 with 11 mips while your atlas is 4096, mip limit/streaming is the cause. Also view the pre-post-process target to separate texture softness from post/upscaler softness.
9. Replace character material albedo sampling with a debug shader or point sampling to check effective texel density in screen space.
10. Decide: if cause is the mip limit, patch via Harmony to set `ignoreMipmapLimit` at texture creation; if compression, switch the compressor to BC7/higher-quality path; if upscaler/TAA, document and accept.

## URLs
- https://docs.unity3d.com/6000.0/Documentation/ScriptReference/QualitySettings-globalTextureMipmapLimit.html
- https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Texture2D-mipmapLimitGroup.html
- https://discussions.unity.com/t/office-hours-question-global-texture-mipmap-limit-globaltexturemipmaplimit/1541211
- https://docs.unity3d.com/ScriptReference/Graphics.CopyTexture.html
- https://docs.unity3d.com/6000.3/Documentation/Manual/TextureStreaming-use.html
- https://docs.unity.cn/Manual/TextureStreaming-API.html
- https://discussions.unity.com/t/textures-mip-streaming-for-runtime-generated-textures/729703
- https://discussions.unity.com/t/texture2d-streamingmipmaps-cannot-be-assigned-to-it-is-read-only/929802
- https://support.unity.com/hc/en-us/articles/210606003-How-does-the-Anisotropic-Textures-Quality-Setting-affect-each-texture-s-Aniso-Level
- https://docs.unity.cn/ScriptReference/Texture-anisoLevel.html
- https://docs.unity3d.com/462/Documentation/ScriptReference/FilterMode.html
- https://issuetracker.unity.com/issues/14503/graphicscopytexture-is-called-with-mismatching-mip-counts-when-anti-aliasing-is-used
- Owlcat modding guide / templates: https://github.com/OwlcatOpenSource/RTModificationTemplate and the Steam Workshop modding guide (Unity 6000.0.52f1)

## Gaps
Not fetched or verified: the game's actual Unity build, its quality-option to mip-limit mapping, the compressor's BC format, and the exact bilinear mip selection statement. These are what the checklist step 4 and 8 resolve.
