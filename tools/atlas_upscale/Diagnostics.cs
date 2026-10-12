using System;
using System.Collections;
using System.Collections.Generic;
using HarmonyLib;
using Kingmaker.UI.DollRoom;
using Kingmaker.Visual.CharacterSystem;
using UnityEngine;

namespace AtlasUpscale;

/// <summary>
/// Read-only logging that explains why upscaled textures may not show in game. Everything is reflection based and
/// wrapped so a wrong field name logs "n/a" instead of throwing inside the game.
/// </summary>
public static class Diagnostics
{
    private const string NotAvailable = "n/a";
    private const string SizeField = "m_Size";
    private const string SortedField = "m_SortedTextures";
    private const string AntialiasingProperty = "Antialiasing";
    private const string AntialiasingQualityProperty = "AntialiasingQuality";
    private const string CameraDataComponent = "WaaaghAdditionalCameraData";
    private const string CameraField = "m_Camera";

    private static readonly HashSet<CharacterAtlas> s_LoggedAtlases = new();
    private static bool s_LoggedMipCounts;

    public static void LogQuality()
    {
        Safe("quality", () =>
            Main.Log.Log($"quality: level {QualitySettings.GetQualityLevel()} '{QualitySettings.names[QualitySettings.GetQualityLevel()]}', " +
                         $"globalTextureMipmapLimit {QualitySettings.globalTextureMipmapLimit}, anisotropicFiltering {QualitySettings.anisotropicFiltering}, " +
                         $"streamingMipmapsActive {QualitySettings.streamingMipmapsActive}, lodBias {QualitySettings.lodBias}, " +
                         $"screen {Screen.width}x{Screen.height}"));
    }

    public static void LogDollCamera()
    {
        Safe("doll camera", () =>
        {
            var doll = DollCamera.Current;
            if (doll == null)
            {
                Main.Log.Log("doll camera: none active");
                return;
            }
            var camera = AccessTools.Field(typeof(DollCamera), CameraField)?.GetValue(doll) as Camera;
            string target = camera?.targetTexture != null
                ? $"{camera.targetTexture.width}x{camera.targetTexture.height} {camera.targetTexture.format}"
                : "none";
            string antialiasing = NotAvailable;
            var data = doll.GetComponent(CameraDataComponent);
            if (data != null)
            {
                var traverse = Traverse.Create(data);
                antialiasing = $"{traverse.Property(AntialiasingProperty).GetValue()} / {traverse.Property(AntialiasingQualityProperty).GetValue()}";
            }
            Main.Log.Log($"doll camera: pixels {camera?.pixelWidth}x{camera?.pixelHeight}, targetTexture {target}, " +
                         $"dynamicResolution {camera?.allowDynamicResolution}, fov {camera?.fieldOfView:0.#}, antialiasing {antialiasing}");
        });
    }

    public static void LogAtlasCreated(Character character, CharacterAtlas atlas, int requestedSize, CharacterTextureChannel channel)
    {
        if (atlas == null || !s_LoggedAtlases.Add(atlas))
            return;
        Safe("atlas created", () =>
        {
            var size = AccessTools.Field(typeof(CharacterAtlas), SizeField)?.GetValue(atlas);
            Main.Log.Log($"atlas created for '{character.name}' {channel}: requested {requestedSize}, size {size ?? NotAvailable}, " +
                         $"atlasData {character.AtlasData?.name ?? NotAvailable}");
        });
    }

    /// <summary>Per source texture: its size, the atlas rect it lands in, and whether a painted render texture replaces it.</summary>
    public static void LogBuild(CharacterAtlas atlas, EquipmentEntity.PaintedTextures painted)
    {
        Safe("build", () =>
        {
            if (AccessTools.Field(typeof(CharacterAtlas), SortedField)?.GetValue(atlas) is not IEnumerable sorted)
                return;
            string filter = Main.Settings.DumpFilter;
            foreach (CharacterTextureDescription description in sorted)
            {
                var source = description.GetSourceTexture();
                string name = description.GetMainTextureName();
                if (name == null || !name.Contains(filter))
                    continue;
                string rect = source != null && atlas.Rects.TryGetValue(source, out var r) ? $"{r.width}x{r.height} at {r.x},{r.y}" : NotAvailable;
                var active = description.ActiveTexture;
                var paintedRt = painted?.Get(description);
                string paintedText = paintedRt != null ? $"{paintedRt.width}x{paintedRt.height}" : "none";
                Main.Log.Log($"  build {name}: active {active?.width}x{active?.height} ({active?.name}), atlas rect {rect}, painted {paintedText}, " +
                             $"shadowMask {description.UseShadowMask}");
            }
        });
    }

    public static void LogCompressed(Texture2D texture)
    {
        Safe("compressed", () =>
            Main.Log.Log($"compressed atlas: {texture.width}x{texture.height} {texture.format}, mips {texture.mipmapCount}, readable {texture.isReadable}, " +
                         $"filter {texture.filterMode}, aniso {texture.anisoLevel}, mipBias {texture.mipMapBias}, ignoreMipmapLimit {texture.ignoreMipmapLimit}, " +
                         $"mipLimitGroup '{texture.mipmapLimitGroup}', loadedMip {texture.loadedMipmapLevel}, desiredMip {texture.desiredMipmapLevel}"));
    }

    public static void LogMipCounts(Texture2D fresh, Texture2D current)
    {
        if (s_LoggedMipCounts)
            return;
        s_LoggedMipCounts = true;
        Main.Log.Log($"set switch mip counts: new {fresh.mipmapCount} ({fresh.format}) vs current {current.mipmapCount} ({current.format})");
    }

    private static void Safe(string what, Action action)
    {
        try
        {
            action();
        }
        catch (Exception e)
        {
            Main.Log.Log($"diagnostics '{what}' failed: {e.GetType().Name} {e.Message}");
        }
    }
}

[HarmonyPatch(typeof(Character), "GetAtlas")]
internal static class Character_GetAtlas_Diagnostics_Patch
{
    private static void Postfix(Character __instance, CharacterAtlas __result, int atlasSize, CharacterTextureChannel channel) =>
        Diagnostics.LogAtlasCreated(__instance, __result, atlasSize, channel);
}
