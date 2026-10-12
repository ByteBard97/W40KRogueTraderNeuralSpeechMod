using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using Newtonsoft.Json;
using UnityEngine;
using UnityModManager = UnityModManagerNet.UnityModManager;

namespace AudioTest;

/// <summary>
/// Hotkey test bench for Wwise audio experiments. Reads tests.json from the mod folder; each entry binds one key to one action.
/// Actions: event (post an event), setmedia (hand a .wem file to a source id, then optionally post an event), unsetmedia,
/// loadmembank (load a .bnk file from memory), unloadbank, stopall. Results show on screen and go to audio_test.log.
/// Alt+0 toggles the on-screen key list.
/// </summary>
public static class Main
{
    private const int Alignment = 16;                  // AK_BANK_PLATFORM_DATA_ALIGNMENT, from AkSoundEngine.cs
    private const float StatusSeconds = 8f;
    private const int FontSize = 20;
    private const string TestsFile = "tests.json";
    private const string LogFile = "audio_test.log";
    private const uint CallbackTypes = (uint)(AkCallbackType.AK_EndOfEvent | AkCallbackType.AK_Duration);

    public sealed class Test
    {
        public string Key;          // e.g. "Alt+1"
        public string Label;
        public string Action;       // event | setmedia | unsetmedia | loadmembank | unloadbank | stopall
        public string Event;        // event name, e.g. "ev_<guid>"
        public uint SourceId;       // setmedia / unsetmedia
        public string File;         // wem for setmedia, bnk for loadmembank (relative to the mod folder)
        public bool PostAfter;      // setmedia: post Event afterwards
        public string Bank;         // unloadbank: label given to a previous loadmembank
        [JsonIgnore] public KeyCode Code;
        [JsonIgnore] public bool Alt, Ctrl, Shift;
    }

    private sealed class Loaded { public IntPtr Mem; public uint Size; public uint BankId; }

    private static string s_Dir;
    private static List<Test> s_Tests = new List<Test>();
    private static readonly Dictionary<string, IntPtr> s_Media = new Dictionary<string, IntPtr>();   // setmedia buffers, kept alive
    private static readonly Dictionary<string, Loaded> s_Banks = new Dictionary<string, Loaded>();
    private static string s_Status = "";
    private static float s_StatusUntil;
    private static bool s_ShowKeys = true;
    private static GUIStyle s_Style;
    private static GameObject s_Emitter;
    private static float s_PostedAt;

    public static bool Load(UnityModManager.ModEntry modEntry)
    {
        s_Dir = modEntry.Path;
        modEntry.OnFixedGUI = OnFixedGui;
        LoadTests();
        Log($"loaded, {s_Tests.Count} tests from {Path.Combine(s_Dir, TestsFile)}");
        return true;
    }

    private static void LoadTests()
    {
        s_Tests = new List<Test>();
        string path = Path.Combine(s_Dir, TestsFile);
        if (!File.Exists(path))
            return;
        foreach (var t in JsonConvert.DeserializeObject<List<Test>>(File.ReadAllText(path)))
        {
            if (!ParseKey(t))
            {
                Log($"bad key '{t.Key}' for {t.Label}");
                continue;
            }
            s_Tests.Add(t);
        }
    }

    private static bool ParseKey(Test t)
    {
        foreach (var part in (t.Key ?? "").Split('+'))
        {
            string p = part.Trim();
            if (p.Equals("Alt", StringComparison.OrdinalIgnoreCase)) t.Alt = true;
            else if (p.Equals("Ctrl", StringComparison.OrdinalIgnoreCase)) t.Ctrl = true;
            else if (p.Equals("Shift", StringComparison.OrdinalIgnoreCase)) t.Shift = true;
            else
            {
                if (p.Length == 1 && char.IsDigit(p[0])) p = "Alpha" + p;
                try { t.Code = (KeyCode)Enum.Parse(typeof(KeyCode), p, true); }
                catch { return false; }
            }
        }
        return t.Code != KeyCode.None;
    }

    private static void OnFixedGui(UnityModManager.ModEntry modEntry)
    {
        var e = Event.current;
        if (e.type == EventType.KeyDown && GUIUtility.keyboardControl == 0)
        {
            if (e.alt && e.keyCode == KeyCode.Alpha0)
                s_ShowKeys = !s_ShowKeys;
            else if (e.alt && e.keyCode == KeyCode.Minus)
            {
                LoadTests();
                Show($"reloaded tests.json: {s_Tests.Count} tests");
            }
            else
            {
                foreach (var t in s_Tests)
                {
                    if (e.keyCode == t.Code && e.alt == t.Alt && e.control == t.Ctrl && e.shift == t.Shift)
                    {
                        Run(t);
                        break;
                    }
                }
            }
        }
        if (e.type != EventType.Repaint)
            return;
        s_Style ??= new GUIStyle(GUI.skin.label) { fontSize = FontSize, fontStyle = FontStyle.Bold, wordWrap = true };
        string text = Time.realtimeSinceStartup <= s_StatusUntil ? s_Status + "\n" : "";
        if (s_ShowKeys)
        {
            foreach (var t in s_Tests)
                text += $"{t.Key}: {t.Label}\n";
            text += "Alt+0 hide, Alt+- reload tests.json";
        }
        if (text.Length == 0)
            return;
        var area = new Rect(10f, 10f, Screen.width * 0.6f, Screen.height - 20f);
        s_Style.normal.textColor = Color.black;
        GUI.Label(new Rect(area.x + 2f, area.y + 2f, area.width, area.height), text, s_Style);
        s_Style.normal.textColor = new Color(0.6f, 1f, 0.6f);
        GUI.Label(area, text, s_Style);
    }

    private static void Run(Test t)
    {
        try
        {
            switch (t.Action)
            {
                case "event": Post(t); break;
                case "setmedia": SetMedia(t); break;
                case "unsetmedia": UnsetMedia(t); break;
                case "loadmembank": LoadMemBank(t); break;
                case "unloadbank": UnloadBank(t); break;
                case "stopall": AkSoundEngine.StopAll(); Show($"{t.Label}: stopped all"); break;
                default: Show($"{t.Label}: unknown action '{t.Action}'"); break;
            }
        }
        catch (Exception ex)
        {
            Show($"{t.Label}: EXCEPTION {ex.GetType().Name}: {ex.Message}");
        }
    }

    private static GameObject Emitter()
    {
        if (s_Emitter == null)
        {
            s_Emitter = new GameObject("AudioTestEmitter");
            UnityEngine.Object.DontDestroyOnLoad(s_Emitter);
        }
        var cam = Camera.main;
        if (cam != null)
            s_Emitter.transform.position = cam.transform.position;   // sit on the listener so it is heard at full level
        return s_Emitter;
    }

    private static void Post(Test t)
    {
        s_PostedAt = Time.realtimeSinceStartup;
        string label = t.Label;
        uint id = AkSoundEngine.PostEvent(t.Event, Emitter(), CallbackTypes, (cookie, type, info) =>
        {
            if (type == AkCallbackType.AK_Duration && info is AkDurationCallbackInfo d)
                Log($"{label}: duration {d.fDuration:0.00}s (estimated {d.fEstimatedDuration:0.00}s)");
            else if (type == AkCallbackType.AK_EndOfEvent)
                Show($"{label}: event ended after {Time.realtimeSinceStartup - s_PostedAt:0.00}s");
        }, null);
        Show($"{label}: PostEvent {t.Event} -> playing id {id}{(id == 0 ? "  (0 = FAILED, event not found)" : "")}");
    }

    private static IntPtr Aligned(byte[] data, out IntPtr raw)
    {
        raw = Marshal.AllocHGlobal(data.Length + Alignment);
        long start = (raw.ToInt64() + Alignment - 1) & ~(long)(Alignment - 1);
        var p = new IntPtr(start);
        Marshal.Copy(data, 0, p, data.Length);
        return p;
    }

    private static void SetMedia(Test t)
    {
        byte[] data = File.ReadAllBytes(Path.Combine(s_Dir, t.File));
        var aligned = Aligned(data, out var raw);
        s_Media[t.Label + "#" + t.SourceId] = raw;   // never freed during the session: Wwise keeps the pointer
        using (var arr = new AkSourceSettingsArray(1))
        {
            arr[0].sourceID = t.SourceId;
            arr[0].pMediaMemory = aligned;
            arr[0].uMediaSize = (uint)data.Length;
            var r = AkSoundEngine.SetMedia(arr, 1);
            Show($"{t.Label}: SetMedia source {t.SourceId} ({data.Length} bytes) -> {r}");
        }
        if (t.PostAfter && !string.IsNullOrEmpty(t.Event))
            Post(t);
    }

    private static void UnsetMedia(Test t)
    {
        using (var arr = new AkSourceSettingsArray(1))
        {
            arr[0].sourceID = t.SourceId;
            var r = AkSoundEngine.UnsetMedia(arr, 1);
            Show($"{t.Label}: UnsetMedia source {t.SourceId} -> {r}");
        }
    }

    private static void LoadMemBank(Test t)
    {
        byte[] data = File.ReadAllBytes(Path.Combine(s_Dir, t.File));
        var aligned = Aligned(data, out var raw);
        var r = AkSoundEngine.LoadBankMemoryView(aligned, (uint)data.Length, out uint bankId);
        s_Banks[t.Label] = new Loaded { Mem = aligned, Size = (uint)data.Length, BankId = bankId };
        s_Media[t.Label + "#bank"] = raw;
        Show($"{t.Label}: LoadBankMemoryView {data.Length} bytes -> {r}, bank id {bankId}");
    }

    private static void UnloadBank(Test t)
    {
        if (!s_Banks.TryGetValue(t.Bank, out var b))
        {
            Show($"{t.Label}: no bank loaded under '{t.Bank}'");
            return;
        }
        var r = AkSoundEngine.UnloadBank(b.BankId, b.Mem, 0);
        Show($"{t.Label}: UnloadBank {b.BankId} -> {r}");
    }

    private static void Show(string text)
    {
        s_Status = text;
        s_StatusUntil = Time.realtimeSinceStartup + StatusSeconds;
        Log(text);
    }

    private static void Log(string text)
    {
        try { File.AppendAllText(Path.Combine(s_Dir, LogFile), DateTime.Now.ToString("HH:mm:ss") + " " + text + "\n"); }
        catch { }
    }
}
