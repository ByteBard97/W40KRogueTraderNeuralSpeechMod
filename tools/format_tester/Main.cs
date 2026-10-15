using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using UnityModManager = UnityModManagerNet.UnityModManager;

namespace FormatTester;

// Hotkeys that try audio formats in the running game and print what happened on screen.
// Keypad 1 to 4 play the four test lines (swapping the installed main bank for the small test bank first),
// 5 and 6 try SetMedia / UnsetMedia, 0 puts the installed bank back, + and - record whether you heard it.
public static class Main
{
    private static readonly KeyCode[] LineKeys = { KeyCode.Keypad1, KeyCode.Keypad2, KeyCode.Keypad3, KeyCode.Keypad4 };
    private static readonly string[] LineIds = { "A", "B", "C", "D" };
    public const KeyCode SetMediaKey = KeyCode.Keypad5;
    public const KeyCode UnsetMediaKey = KeyCode.Keypad6;
    public const KeyCode RestoreKey = KeyCode.Keypad0;
    public const KeyCode ReplayKey = KeyCode.KeypadDivide;
    public const KeyCode HeardKey = KeyCode.KeypadPlus;
    public const KeyCode SilentKey = KeyCode.KeypadMinus;
    public const KeyCode PanelKey = KeyCode.KeypadMultiply;

    private const float ReportSeconds = 20f;
    private const int ReportFont = 22;
    private const int PanelFont = 15;
    private const float ReportY = 0.08f;
    private const float PanelWidth = 560f;
    private const float PanelHeight = 230f;
    private const float Margin = 12f;
    private const float ShadowOffset = 2f;
    private const string ResultsFile = "results.jsonl";

    public static UnityModManager.ModEntry.ModLogger Log;
    private static string s_Dir;
    private static string s_Report = "";
    private static Color s_ReportColor = Color.white;
    private static float s_ReportUntil;
    private static bool s_ShowPanel = true;
    private static GUIStyle s_ReportStyle;
    private static GUIStyle s_PanelStyle;

    public static bool Load(UnityModManager.ModEntry modEntry)
    {
        Log = modEntry.Logger;
        s_Dir = modEntry.Path;
        modEntry.OnFixedGUI = OnFixedGui;
        try
        {
            Tester.Init(s_Dir);
            Log.Log("loaded, keypad 1-4 lines, 5 SetMedia, 6 UnsetMedia, 0 restore, + heard, - silent, * panel");
        }
        catch (Exception e)
        {
            Log.Log($"init failed: {e}");
            Show("Format tester init failed: " + e.Message, Color.red);
        }
        return true;
    }

    public static void Show(string text, Color color)
    {
        s_Report = text;
        s_ReportColor = color;
        s_ReportUntil = Time.realtimeSinceStartup + ReportSeconds;
    }

    // Wwise callbacks append lines to the report that is already on screen.
    public static void Append(string line)
    {
        s_Report += "\n" + line;
        s_ReportUntil = Time.realtimeSinceStartup + ReportSeconds;
    }

    public static void Record(string kind, string test, string detail)
    {
        try
        {
            var sb = new StringBuilder("{");
            sb.Append("\"ts\":\"").Append(DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture)).Append("\",");
            sb.Append("\"kind\":\"").Append(Esc(kind)).Append("\",\"test\":\"").Append(Esc(test)).Append("\",\"detail\":\"").Append(Esc(detail)).Append("\"}");
            File.AppendAllText(Path.Combine(s_Dir, ResultsFile), sb.ToString() + "\n", new UTF8Encoding(false));
        }
        catch (Exception e) { Log.Log($"could not write results: {e.Message}"); }
    }

    private static string Esc(string s) =>
        (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "").Replace("\n", "\\n");

    private static void OnFixedGui(UnityModManager.ModEntry modEntry)
    {
        var current = Event.current;
        if (current.type == EventType.KeyDown && GUIUtility.keyboardControl == 0)
            HandleKey(current.keyCode);
        if (current.type == EventType.Repaint)
            Draw();
    }

    private static void HandleKey(KeyCode key)
    {
        try
        {
            int line = Array.IndexOf(LineKeys, key);
            if (line >= 0) Report(Tester.PlayLine(LineIds[line]));
            else if (key == SetMediaKey) Report(Tester.SetMediaOverride());
            else if (key == UnsetMediaKey) Report(Tester.UnsetMedia());
            else if (key == RestoreKey) Report(Tester.Restore());
            else if (key == ReplayKey) Report(Tester.Replay());
            else if (key == HeardKey) Verdict("heard");
            else if (key == SilentKey) Verdict("silent");
            else if (key == PanelKey) s_ShowPanel = !s_ShowPanel;
        }
        catch (Exception e)
        {
            Log.Log($"key {key} failed: {e}");
            Show($"{key} threw: {e.GetType().Name}: {e.Message}", Color.red);
        }
    }

    private static void Report(Tester.Outcome o)
    {
        if (o == null) return;
        Show(o.Text, o.Ok ? new Color(0.5f, 1f, 0.5f) : new Color(1f, 0.45f, 0.45f));
        Record("test", o.Test, o.Text);
        Log.Log(o.Text.Replace("\n", " | "));
    }

    private static void Verdict(string verdict)
    {
        string test = Tester.LastTest;
        if (test == null)
        {
            Show("Nothing tested yet, nothing recorded", Color.yellow);
            return;
        }
        Record("verdict", test, verdict);
        Show($"Recorded: {test} -> {verdict.ToUpperInvariant()}", verdict == "heard" ? new Color(0.5f, 1f, 0.5f) : Color.yellow);
        Log.Log($"verdict {test}: {verdict}");
    }

    private static void Draw()
    {
        s_ReportStyle ??= new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold, alignment = TextAnchor.UpperCenter, wordWrap = true, fontSize = ReportFont };
        s_PanelStyle ??= new GUIStyle(GUI.skin.label) { alignment = TextAnchor.UpperLeft, fontSize = PanelFont };
        if (Time.realtimeSinceStartup <= s_ReportUntil)
        {
            var area = new Rect(Screen.width * 0.1f, Screen.height * ReportY, Screen.width * 0.8f, Screen.height * 0.5f);
            Shadowed(area, s_Report, s_ReportStyle, s_ReportColor);
        }
        if (s_ShowPanel)
        {
            var area = new Rect(Margin, Screen.height - PanelHeight - Margin, PanelWidth, PanelHeight);
            Shadowed(area, Tester.PanelText(), s_PanelStyle, new Color(0.85f, 0.85f, 0.85f));
        }
    }

    private static void Shadowed(Rect area, string text, GUIStyle style, Color color)
    {
        style.normal.textColor = Color.black;
        GUI.Label(new Rect(area.x + ShadowOffset, area.y + ShadowOffset, area.width, area.height), text, style);
        style.normal.textColor = color;
        GUI.Label(area, text, style);
    }
}
