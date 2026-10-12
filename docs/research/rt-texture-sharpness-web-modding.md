# Why 2x upscaled character textures barely show in Rogue Trader (web research)

Research date 2026-10-11. Web only, nothing in the game install was touched. Nexus pages mostly returned 403 to direct fetch, so several claims come from search-result snippets and are marked as such.

## Summary: likely explanations, ranked

1. **The dollroom/inventory character is rendered at reduced resolution (guess, with one supporting hint).** The RogueTrader_DLSS author lists "Full-resolution rendering on the character doll/inventory screen" under Future Plans, which implies the doll is currently rendered below full resolution (render-texture or render-scale-tied). Output sharpness would then be capped by that RT, not by texture detail. The WotR Upscaler mod (same system family) has a "Character preview size" option with "Original (the game's small texture)", which says the same thing for the sibling game. Likelihood: high.
2. **Mip bias or mip selection.** RT applies a texture mip bias tied to FSR/upscaling; the Enhanced Graphics mod says an over-aggressive mip bias "introduced in an RT patch when they started biasing textures for FSR" made textures soft at lower render scales. If the doll camera uses a lower render scale, the GPU samples a lower mip of your 4096 atlas, which looks like the old 2048 atlas. Also check whether the upscaled atlas actually has a full mip chain, and global Texture Quality / `masterTextureLimit` (guess, not found documented for RT).
3. **TAA and RCAS sharpening softening.** Steam users report RT's default TAA is fuzzy (switching to SMAA "removes the blur"), and the game uses an aggressive RCAS sharpener. Both change fine detail on any texture. Likelihood: medium.
4. **Texture detail is under-resolved by on-screen size.** Zoomed dollroom shows a character perhaps 600-1000 px tall; a UV island of a body part may map to few texels per pixel, so 2048 vs 4096 stops mattering once screen pixels are the limit. Also, Topaz "Recovery" output may not add real high-frequency detail on already-soft sources, and the game's DXT/BC compression of the atlas can erase fine gains (guess).
5. **Your swap not reaching the sampled texture** (atlas is rebuilt at runtime, per-unit slot, cache, or other shader path such as normal/mask maps doing most of the visible work). Verify by capture, see steps.

## Findings

### Existing texture mods
- No dedicated HD/character-texture mod for Rogue Trader turned up. Searches of Nexus listings returned only graphics/DLSS mods and recolor tools. Nexus RT mods listing: https://www.nexusmods.com/games/warhammer40kroguetrader/mods . ReDress (https://www.nexusmods.com/warhammer40kroguetrader/mods/104) is recoloring via masks, not resolution.
- No write-up of anyone doing the CharacterAtlas 4096 trick was found. Nothing found on "CharacterAtlas", "CharacterAtlasData", "DxtCompressorService" anywhere on the web (searched; zero hits). Treat those names as unpublished internals.

### Graphics / sharpness related
- Enhanced Graphics (DLSS Upscaling), Nexus RT mod 184 (snippet, page 403): https://www.nexusmods.com/warhammer40kroguetrader/mods/184 . Claims: fixes over-aggressive mip bias introduced for FSR; the game's RCAS sharpener is disabled under DLSS (adds a sharpness slider); moves some passes after upscaling.
- DLSS Upscaling / OptiScaler variant, mod 447: https://www.nexusmods.com/warhammer40kroguetrader/mods/447 . OptiScaler (https://www.nexusmods.com/site/mods/986) has Force Anisotropic Filtering and Mipmap LOD Bias controls; usable as a diagnostic (override LOD bias to see if sampling changes).
- Source: https://github.com/cstamford/RogueTrader_DLSS (README fetched). Loads via ASI loader (winhttp.dll). Notes cloth not in motion vectors. Future plan quote: "Full-resolution rendering on the character doll/inventory screen." No mip-bias detail in README; the Mod and Native source folders would show exactly which render targets/cameras it touches. Worth reading.
- Steam thread on blurry FSR/TAA: https://steamcommunity.com/app/2186680/discussions/0/4027970229985742169/ . Users: FSR sharpness slider had little effect; switching TAA to SMAA fixed fuzziness.
- "ScalingFix" mod: not found. No documented RT config file capping texture resolution or mip level was found.

### Sibling game (Pathfinder: WotR, same Owlcat renderer lineage)
- WotR Upscaler (DLAA/DLSS/FSR/XeSS), https://www.nexusmods.com/pathfinderwrathoftherighteous/mods/1205 (snippet only). Has "Character preview size" for inventory and character creation: Original (game's small texture), Follow the upscaler (default), Size on screen (sharpest, heaviest). Also automatic mip bias, SMAA/FXAA off under DLSS/TAA. Strong evidence the inventory preview is a small render target by default in Owlcat games. The mod author would be a good person to ask which RT/camera is involved.
- GOG thread, inventory character looks sharp for a moment after equipment swap, then blurs: https://www.gog.com/forum/pathfinder_wrath_of_the_righteous/blurry_graphics_on_profile_pics . No cause given. Speculation (mine): consistent with the doll re-rendering at a different scale or mip/atlas state, or a temporal effect settling. Worth checking in your setup: does your mod look sharper right after an equipment change?
- Owlcat modding template (WotR): https://github.com/OwlcatOpenSource/WrathModificationTemplate (Unity 2019.4, Owlcat/Lit shader). Not RT's Unity 6.

### Modding tooling
- RT ships its own UnityModManager and an OwlcatModificationManager; Ctrl+F10 opens UMM; mods go in `%USERPROFILE%/AppData/LocalLow/Owlcat Games/Warhammer 40000 Rogue Trader/UnityModManager/` (Steam discussions: https://steamcommunity.com/app/2186680/discussions/0/600768571255055020 , modding guide https://steamcommunity.com/workshop/discussions/18446744073709551615/4027970580221500367/?appid=2186680). Reddit post by xADDBx "Modding in Rogue Trader" exists (r/RogueTraderCRPG, 2023-12-07) but could not be fetched.
- Generic workflow (from a Rogue Legacy 2 guide, https://www.nexusmods.com/roguelegacy2/articles/2): ILSpy/dnSpy on Assembly-CSharp for patch targets, AssetStudio for bundles. Nothing RT-specific on Harmony, AssetStudio, UABE, AssetRipper or RenderDoc was found; they are generic Unity tools.
- Custom portraits are a separate system (PNG files in LocalLow Portraits folders); irrelevant to the atlas.

## Verified vs guessed
- Verified (quoted from sources): the DLSS repo's "full-resolution doll" future-plan line; the Enhanced Graphics mip-bias/RCAS claims (from snippets); WotR Upscaler's small default character preview (snippet); TAA blur reports.
- Guesses: that the RT doll uses a reduced RT or lower mip; that DXT compression or limited screen pixels mask the gain; anything about masterTextureLimit.
- Nothing exists for: CharacterAtlas internals, an RT HD character texture mod, a texture-resolution config file, RT-specific RenderDoc/AssetStudio guides.

## Debugging steps worth trying
1. RenderDoc (Proton/Linux works with DXVK/Vulkan; capture on the dollroom view). Find the draw call for the character, inspect the bound diffuse texture: size (4096?), mip count, format, and which mip the pixel shader's sampled region corresponds to. Also check the dimensions of the render target the doll draws into versus the swapchain.
2. Change in-game render scale / upscaler settings and watch the dollroom; if sharpness tracks render scale, it is a RT-size/mip-bias issue. Try TAA off (SMAA) to remove temporal softening.
3. Try OptiScaler or the Enhanced Graphics mod to set mip LOD bias to a negative value and force 16x AF; compare. Read cstamford's source for the doll camera/RT handling.
4. In your Harmony mod, log the atlas Texture2D: width, height, mipmapCount, format, filterMode, anisoLevel, `QualitySettings.globalTextureMipmapLimit` (Unity 6; formerly masterTextureLimit). Set `mipMapBias = -1` and `anisoLevel = 16` on the atlas and compare.
5. Exaggeration test: write a high-contrast fine checkerboard or a loud tint into the 4096 atlas for one character. If the pattern appears blurred or averaged in game, resolution is being lost downstream (RT size, mip); if it does not appear, the swap is not what is sampled.
6. Patch the dollroom render texture to a larger size (find the RT in Assembly-CSharp via ILSpy) to test hypothesis 1 directly.
7. Check that the upscaled atlas is compressed from the upscaled source (BC7 rather than DXT1 if possible) and has mips regenerated, not copied from the old atlas.
8. Ask the authors of Enhanced Graphics (Nexus mod 184 / 447) or the WotR Upscaler author about the doll render path.
