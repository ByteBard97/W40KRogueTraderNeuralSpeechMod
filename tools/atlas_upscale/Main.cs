using System.Reflection;
using HarmonyLib;
using UnityEngine;
using UnityModManager = UnityModManagerNet.UnityModManager;

namespace AtlasUpscale;

public static class Main
{
    public const int MinFactor = 1;
    public const int MaxFactor = 4;

    public static Settings Settings;
    public static UnityModManager.ModEntry.ModLogger Log;
    public static string ModPath;
    public static UnityModManager.ModEntry Entry;

    /// <summary>Hides the on-screen texture set label, for clean screenshots.</summary>
    public static bool SuppressLabel;

    private const float PollSeconds = 1f;
    private const float LabelSeconds = 3f;
    private const float LabelWidth = 1.0f;
    private const float LabelHeightPerPoint = 1.5f;
    public const int MinLabelFont = 16;
    public const int MaxLabelFont = 120;
    public const float MinZoomRange = 1f;
    public const float MaxZoomRange = 6f;
    private const float ShadowOffset = 2f;

    private static Harmony s_Harmony;
    private static float s_NextPoll;
    private static float s_LabelUntil;
    private static GUIStyle s_LabelStyle;

    public static bool Load(UnityModManager.ModEntry modEntry)
    {
        Log = modEntry.Logger;
        ModPath = modEntry.Path;
        Entry = modEntry;
        Settings = UnityModManager.ModSettings.Load<Settings>(modEntry);
        Settings.Factor = Mathf.Clamp(Settings.Factor, MinFactor, MaxFactor);
        modEntry.OnGUI = OnGui;
        modEntry.OnUpdate = OnUpdate;
        modEntry.OnFixedGUI = OnFixedGui;
        TextureScaler.ScanVariants(Settings.Variant);
        modEntry.OnSaveGUI = _ => Settings.Save(modEntry);
        s_Harmony = new Harmony(modEntry.Info.Id);
        s_Harmony.PatchAll(Assembly.GetExecutingAssembly());
        Diagnostics.LogQuality();
        if (Settings.BridgeEnabled)
            Bridge.Start();
        Log.Log($"loaded, factor {Settings.Factor}, texture set '{TextureScaler.CurrentVariantName}'");
        return true;
    }

    private static void OnUpdate(UnityModManager.ModEntry modEntry, float dt)
    {
        if (!Settings.AutoReload || Time.unscaledTime < s_NextPoll)
            return;
        s_NextPoll = Time.unscaledTime + PollSeconds;
        if (TextureScaler.RefreshOverrides() > 0)
            Reloader.Apply();
    }

    private static void OnFixedGui(UnityModManager.ModEntry modEntry)
    {
        var current = Event.current;
        if (current.type == EventType.KeyDown && current.keyCode == Settings.HotKey)
        {
            TextureScaler.CycleVariant(current.shift ? -1 : 1);
            Settings.Variant = TextureScaler.CurrentVariantName;
            Settings.Save(modEntry);
            Reloader.Apply();
            s_LabelUntil = Time.realtimeSinceStartup + LabelSeconds;
            current.Use();
        }
        if (current.type == EventType.KeyDown && current.keyCode == Settings.DumpKey)
        {
            AtlasDump.Arm();
            Reloader.Apply();
            current.Use();
        }
        if (current.type == EventType.KeyDown && HandlePanKey(current))
            current.Use();
        if (SuppressLabel || current.type != EventType.Repaint || (!Settings.AlwaysShowLabel && Time.realtimeSinceStartup > s_LabelUntil))
            return;
        s_LabelStyle ??= new GUIStyle(GUI.skin.label)
        {
            fontStyle = FontStyle.Bold,
            alignment = TextAnchor.UpperCenter
        };
        s_LabelStyle.fontSize = Settings.LabelFontSize;
        string text = $"Texture set: {TextureScaler.CurrentVariantName}   ({Settings.HotKey})";
        float height = Settings.LabelFontSize * LabelHeightPerPoint;
        var area = new Rect(0f, Screen.height * Settings.LabelY, Screen.width * LabelWidth, height);
        s_LabelStyle.normal.textColor = Color.black;
        GUI.Label(new Rect(area.x + ShadowOffset, area.y + ShadowOffset, area.width, area.height), text, s_LabelStyle);
        s_LabelStyle.normal.textColor = Color.yellow;
        GUI.Label(area, text, s_LabelStyle);
    }

    private static bool HandlePanKey(Event current)
    {
        switch (current.keyCode)
        {
            case KeyCode.LeftArrow: ViewerPan.Nudge(1f, 0f); return true;
            case KeyCode.RightArrow: ViewerPan.Nudge(-1f, 0f); return true;
            case KeyCode.UpArrow: ViewerPan.Nudge(0f, -1f); return true;
            case KeyCode.DownArrow: ViewerPan.Nudge(0f, 1f); return true;
            case KeyCode.Home: ViewerPan.Reset(); return true;
            default: return false;
        }
    }

    private static void OnGui(UnityModManager.ModEntry modEntry)
    {
        GUILayout.Label("Changes apply after restarting the game. Memory use grows with the square of the factor.");
        GUILayout.BeginHorizontal();
        GUILayout.Label($"Factor: {Settings.Factor}", GUILayout.Width(100));
        Settings.Factor = Mathf.RoundToInt(GUILayout.HorizontalSlider(Settings.Factor, MinFactor, MaxFactor, GUILayout.Width(200)));
        GUILayout.EndHorizontal();
        Settings.VerboseLog = GUILayout.Toggle(Settings.VerboseLog, "Verbose log");
        Slider("Label size", ref Settings.LabelFontSize, MinLabelFont, MaxLabelFont);
        Slider("Label height", ref Settings.LabelY, 0f, 0.95f);
        Slider("Wheel zoom step (smaller is finer)", ref Settings.ZoomStep, 0.05f, 1f);
        Slider("Arrow key pan step", ref Settings.PanStep, 0.005f, 0.2f);
        Slider("Viewer zoom range (restart screen)", ref Settings.ZoomRange, MinZoomRange, MaxZoomRange);
        Settings.AutoReload = GUILayout.Toggle(Settings.AutoReload, "Reload changed texture files automatically");
        Settings.AlwaysShowLabel = GUILayout.Toggle(Settings.AlwaysShowLabel, "Always show the texture set name");
        GUILayout.Label($"Texture set: {TextureScaler.CurrentVariantName}. Press {Settings.HotKey} in game to switch (Shift for previous).");
        if (GUILayout.Button("Rebuild characters now", GUILayout.Width(200)))
        {
            TextureScaler.RefreshOverrides();
            Reloader.Apply();
        }
    }

    private static void Slider(string label, ref int value, int min, int max)
    {
        GUILayout.BeginHorizontal();
        GUILayout.Label($"{label}: {value}", GUILayout.Width(300));
        value = Mathf.RoundToInt(GUILayout.HorizontalSlider(value, min, max, GUILayout.Width(200)));
        GUILayout.EndHorizontal();
    }

    private static void Slider(string label, ref float value, float min, float max)
    {
        GUILayout.BeginHorizontal();
        GUILayout.Label($"{label}: {value:0.00}", GUILayout.Width(300));
        value = GUILayout.HorizontalSlider(value, min, max, GUILayout.Width(200));
        GUILayout.EndHorizontal();
    }
}
