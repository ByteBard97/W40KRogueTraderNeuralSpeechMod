using System.Collections.Generic;
using System.IO;
using HarmonyLib;
using Kingmaker.Visual.CharacterSystem;
using UnityEngine;

namespace AtlasUpscale;

/// <summary>
/// Debug aid. After the dump key is pressed, saves the finished diffuse atlas of characters whose textures match a
/// name filter, once before DXT compression and once after, so the two can be compared with the source files.
/// </summary>
public static class AtlasDump
{
    private const string FolderName = "Dump";
    private const string UncompressedField = "m_UncompressedTexture";
    private const float ArmSeconds = 15f;

    private static readonly Dictionary<CharacterAtlas, int> s_Targets = new();
    private static float s_ArmedUntil;
    private static int s_Count;

    /// <summary>True while a dump is armed and an atlas it chose has not been compressed and saved yet.</summary>
    public static bool Pending => Armed && s_Targets.Count > 0;

    private static bool Armed => Time.realtimeSinceStartup < s_ArmedUntil;

    public static void Arm()
    {
        s_Targets.Clear();
        s_Count = 0;
        s_ArmedUntil = Time.realtimeSinceStartup + ArmSeconds;
        Main.Log.Log($"atlas dump armed, filter '{Main.Settings.DumpFilter}', up to {Main.Settings.MaxDumps} atlases");
        Diagnostics.LogQuality();
        Diagnostics.LogDollCamera();
    }

    public static void OnBuilt(CharacterAtlas atlas, EquipmentEntity.PaintedTextures painted)
    {
        if (!Armed || atlas.Channel != CharacterTextureChannel.Diffuse || s_Count >= Main.Settings.MaxDumps)
            return;
        var matches = new List<string>();
        foreach (var pair in atlas.Rects)
        {
            if (pair.Key != null && pair.Key.name.Contains(Main.Settings.DumpFilter))
                matches.Add($"{pair.Key.name} x{pair.Value.x} y{pair.Value.y} w{pair.Value.width} h{pair.Value.height}");
        }
        if (matches.Count == 0)
            return;
        int index = s_Count++;
        s_Targets[atlas] = index;
        Main.Log.Log($"atlas dump #{index}: {matches.Count} matching textures in a {atlas.Rects.Count}-texture atlas");
        foreach (var line in matches)
            Main.Log.Log($"  rect {line}");
        Diagnostics.LogBuild(atlas, painted);
        if (AccessTools.Field(typeof(CharacterAtlas), UncompressedField).GetValue(atlas) is RenderTexture raw)
            Save(raw, $"atlas{index}_raw");
    }

    public static void OnCompressed(CharacterAtlas atlas)
    {
        if (!s_Targets.TryGetValue(atlas, out int index) || atlas.AtlasTexture == null)
            return;
        s_Targets.Remove(atlas);
        Diagnostics.LogCompressed(atlas.AtlasTexture);
        Save(atlas.AtlasTexture, $"atlas{index}_dxt");
    }

    private static void Save(Texture source, string name) => SaveTo(source, Path.Combine(Main.ModPath, FolderName), name);

    /// <summary>Writes any texture as a PNG named {name}_{w}x{h}.png and returns the file path.</summary>
    public static string SaveTo(Texture source, string folder, string name)
    {
        Directory.CreateDirectory(folder);
        int width = source.width;
        int height = source.height;
        var rt = RenderTexture.GetTemporary(width, height, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        Graphics.Blit(source, rt);
        var previous = RenderTexture.active;
        RenderTexture.active = rt;
        var copy = new Texture2D(width, height, TextureFormat.RGBA32, false, false);
        copy.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        copy.Apply();
        RenderTexture.active = previous;
        RenderTexture.ReleaseTemporary(rt);
        string path = Path.Combine(folder, $"{name}_{width}x{height}.png");
        File.WriteAllBytes(path, copy.EncodeToPNG());
        Object.Destroy(copy);
        Main.Log.Log($"saved {path}");
        return path;
    }
}

[HarmonyPatch(typeof(CharacterAtlas), nameof(CharacterAtlas.Build))]
internal static class CharacterAtlas_Build_Dump_Patch
{
    private static void Postfix(CharacterAtlas __instance, EquipmentEntity.PaintedTextures paintedTextures) =>
        AtlasDump.OnBuilt(__instance, paintedTextures);
}

[HarmonyPatch(typeof(CharacterAtlas), nameof(CharacterAtlas.AtlasTexture), MethodType.Setter)]
internal static class CharacterAtlas_AtlasTexture_Dump_Patch
{
    private static void Postfix(CharacterAtlas __instance) => AtlasDump.OnCompressed(__instance);
}
