using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEngine;

namespace AtlasUpscale;

/// <summary>
/// Gives every character source texture a size of (original x Factor), so the scaled atlas slots line up.
/// A PNG named like the texture in the mod's Textures folder wins over the plain GPU resize.
/// </summary>
public static class TextureScaler
{
    private const string OverrideFolder = "Textures";
    private const string OverrideExtension = ".png";

    private static readonly Dictionary<Texture2D, Texture2D> s_Scaled = new();
    private static readonly HashSet<Texture2D> s_Produced = new();
    private static readonly List<Entry> s_Entries = new();

    private class Entry
    {
        public string Name;
        public Texture2D Texture;
        public Texture2D Source;
        public bool UsesFile;
        public bool Linear;
        public DateTime LoadedUtc;
    }

    public static Texture2D Scale(Texture2D source)
    {
        if (source == null || Main.Settings.Factor <= 1 || s_Produced.Contains(source))
            return source;
        if (s_Scaled.TryGetValue(source, out var cached) && cached != null)
            return cached;

        int width = source.width * Main.Settings.Factor;
        int height = source.height * Main.Settings.Factor;
        bool linear = !source.isDataSRGB;
        var fromFile = LoadOverride(source.name, width, height, linear);
        var result = fromFile ?? Resize(source, width, height, linear);
        result.name = source.name + "_x" + Main.Settings.Factor;
        s_Scaled[source] = result;
        s_Produced.Add(result);
        s_Entries.Add(new Entry { Name = source.name, Texture = result, Source = source, Linear = linear, LoadedUtc = DateTime.UtcNow, UsesFile = fromFile != null });
        if (Main.Settings.VerboseLog)
            Main.Log.Log($"scaled {source.name} {source.width}x{source.height} -> {width}x{height}");
        return result;
    }

    public const string PlainResizeName = "plain resize";

    private static readonly List<string> s_Variants = new() { PlainResizeName };
    private static int s_Current;

    public static string CurrentVariantName => s_Variants[s_Current];

    /// <summary>Each subfolder of Textures is a texture set. Index 0 is the built-in plain GPU resize.</summary>
    public static void ScanVariants(string preferred)
    {
        s_Variants.Clear();
        s_Variants.Add(PlainResizeName);
        string root = Path.Combine(Main.ModPath, OverrideFolder);
        if (Directory.Exists(root))
        {
            var folders = Directory.GetDirectories(root);
            Array.Sort(folders, StringComparer.OrdinalIgnoreCase);
            foreach (var folder in folders)
                s_Variants.Add(Path.GetFileName(folder));
        }
        int found = s_Variants.IndexOf(preferred);
        s_Current = found >= 0 ? found : (s_Variants.Count > 1 ? 1 : 0);
    }

    private const int ChecksumGrid = 16;
    private const int MaxLoggedTextures = 30;

    /// <summary>Switches to the next or previous set and rewrites the textures that differ, in place.</summary>
    public static void CycleVariant(int step) => SwitchTo((s_Current + step + s_Variants.Count) % s_Variants.Count);

    public static IReadOnlyList<string> VariantNames => s_Variants;

    /// <summary>Switches to a set by folder name (or the plain resize name). Returns false if there is no such set.</summary>
    public static bool SelectVariant(string name)
    {
        int index = s_Variants.FindIndex(v => string.Equals(v, name, StringComparison.OrdinalIgnoreCase));
        if (index < 0)
            return false;
        SwitchTo(index);
        return true;
    }

    private static void SwitchTo(int index)
    {
        var watch = System.Diagnostics.Stopwatch.StartNew();
        s_Current = index;
        int changed = 0, untouched = 0;
        foreach (var entry in s_Entries)
        {
            if (entry.Texture == null || entry.Source == null)
                continue;
            bool hasFile = OverridePath(entry.Name) is { } path && File.Exists(path);
            if (!hasFile && !entry.UsesFile)
            {
                untouched++;
                continue;
            }
            int width = entry.Texture.width;
            int height = entry.Texture.height;
            var fresh = LoadOverride(entry.Name, width, height, entry.Linear) ?? Resize(entry.Source, width, height, entry.Linear);
            Diagnostics.LogMipCounts(fresh, entry.Texture);
            Graphics.CopyTexture(fresh, entry.Texture);
            UnityEngine.Object.Destroy(fresh);
            entry.UsesFile = hasFile;
            entry.LoadedUtc = DateTime.UtcNow;
            changed++;
            if (changed <= MaxLoggedTextures)
                Main.Log.Log($"  {entry.Name} {width}x{height} <- {(hasFile ? "file" : "plain resize")}, checksum {Checksum(entry.Texture)}");
        }
        Main.Log.Log($"texture set '{CurrentVariantName}': {changed} rewritten, {untouched} already plain, {watch.ElapsedMilliseconds} ms");
    }

    /// <summary>Sum over a sparse grid of pixels. Different image content gives a different number.</summary>
    private static string Checksum(Texture2D texture)
    {
        try
        {
            long sum = 0;
            for (int gy = 0; gy < ChecksumGrid; gy++)
            for (int gx = 0; gx < ChecksumGrid; gx++)
            {
                var pixel = (Color32)texture.GetPixel(texture.width * gx / ChecksumGrid, texture.height * gy / ChecksumGrid);
                sum = sum * 31 + pixel.r * 65536 + pixel.g * 256 + pixel.b;
            }
            return (sum & 0xFFFFFF).ToString("X6");
        }
        catch (Exception)
        {
            return "unreadable";
        }
    }

    private static string OverridePath(string name)
    {
        if (s_Current == 0)
            return null;
        return Path.Combine(Main.ModPath, OverrideFolder, s_Variants[s_Current], name + OverrideExtension);
    }

    /// <summary>Re-reads override PNGs that changed on disk into the already scaled textures. Returns how many changed.</summary>
    public static int RefreshOverrides()
    {
        int changed = 0;
        foreach (var entry in s_Entries)
        {
            if (entry.Texture == null)
                continue;
            string path = OverridePath(entry.Name);
            if (path == null || !File.Exists(path) || File.GetLastWriteTimeUtc(path) <= entry.LoadedUtc)
                continue;
            var fresh = LoadOverride(entry.Name, entry.Texture.width, entry.Texture.height, entry.Linear);
            if (fresh == null)
                continue;
            Graphics.CopyTexture(fresh, entry.Texture);
            UnityEngine.Object.Destroy(fresh);
            entry.LoadedUtc = DateTime.UtcNow;
            changed++;
            Main.Log.Log($"reloaded {entry.Name}");
        }
        return changed;
    }

    private static Texture2D Resize(Texture src, int width, int height, bool linear)
    {
        var rt = RenderTexture.GetTemporary(width, height, 0, RenderTextureFormat.ARGB32,
            linear ? RenderTextureReadWrite.Linear : RenderTextureReadWrite.sRGB);
        var previousFilter = src.filterMode;
        src.filterMode = FilterMode.Bilinear;
        Graphics.Blit(src, rt);
        src.filterMode = previousFilter;
        var texture = ReadBack(rt, width, height, linear);
        RenderTexture.ReleaseTemporary(rt);
        return texture;
    }

    private static Texture2D LoadOverride(string name, int width, int height, bool linear)
    {
        string path = OverridePath(name);
        if (path == null || !File.Exists(path))
            return null;
        var loaded = new Texture2D(2, 2, TextureFormat.RGBA32, true, linear);
        if (!DecodeImage(loaded, File.ReadAllBytes(path)))
        {
            UnityEngine.Object.Destroy(loaded);
            return null;
        }
        if (loaded.width == width && loaded.height == height)
            return loaded;
        var fitted = Resize(loaded, width, height, linear);
        UnityEngine.Object.Destroy(loaded);
        return fitted;
    }

    // Called by reflection: the ReadOnlySpan overload of ImageConversion.LoadImage does not resolve on net48.
    private static readonly MethodInfo s_LoadImage = typeof(ImageConversion).GetMethod(
        "LoadImage", new[] { typeof(Texture2D), typeof(byte[]), typeof(bool) });

    private static bool DecodeImage(Texture2D target, byte[] bytes) =>
        (bool)s_LoadImage.Invoke(null, new object[] { target, bytes, false });

    private static Texture2D ReadBack(RenderTexture rt, int width, int height, bool linear)
    {
        var previous = RenderTexture.active;
        RenderTexture.active = rt;
        var texture = new Texture2D(width, height, TextureFormat.RGBA32, true, linear);
        texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        texture.Apply(true, false);
        RenderTexture.active = previous;
        return texture;
    }
}
