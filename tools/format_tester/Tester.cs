using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace FormatTester;

// The Wwise side: swap banks, push media with SetMedia, post events, and report every AKRESULT and engine message.
internal static class Tester
{
    public sealed class Outcome
    {
        public string Test;
        public string Text;
        public bool Ok;
    }

    private const string InstalledBankName = "w40krt_avio_charvogen.bnk";
    private const string AivoFolder = "W40KRT_AIVOMod";
    private const string SoundbanksFolder = "soundbanks";
    private const int BankIdOffset = 12;      // BKHD chunk: tag, size, version, then the bank id
    private const int MediaAlignment = 16;
    private const int MaxEngineMessages = 6;
    private const float MessageWindowSeconds = 12f;
    private const uint PostFlags = (uint)AkCallbackType.AK_EndOfEvent | (uint)AkCallbackType.AK_Duration;

    private static readonly Dictionary<string, string> Labels = new Dictionary<string, string>
    {
        ["A"] = "Opus, plugin 0x00140001 (AKOPUS_WEM)",
        ["B"] = "Opus, plugin 0x00130001 (AKOPUS)",
        ["C"] = "Opus, cbSize 16, plugin 0x00140001",
        ["D"] = "PCM control (should always play)"
    };

    private static string s_Dir;
    private static JObject s_Tests;
    private static uint s_InstalledId;
    private static bool s_InstalledLoaded = true;
    private static uint s_TestBankId;
    private static bool s_TestBankLoaded;
    private static IntPtr s_MediaMemory;
    private static IntPtr s_MediaAligned;
    private static AkSourceSettingsArray s_MediaSettings;
    private static GameObject s_Emitter;
    private static string s_LastEvent;
    private static float s_PostedAt;
    private static uint s_PlayingId;
    private static int s_MessagesShown;
    private static AkCallbackManager.MonitoringCallback s_PreviousMonitor;

    public static string LastTest { get; private set; }

    public static void Init(string dir)
    {
        s_Dir = dir;
        s_Tests = JObject.Parse(File.ReadAllText(Path.Combine(dir, "tests.json")));
        string installed = Path.GetFullPath(Path.Combine(dir, "..", AivoFolder, SoundbanksFolder, InstalledBankName));
        s_InstalledId = ReadBankId(installed);
        InstallMonitor();
    }

    private static uint ReadBankId(string path)
    {
        using var f = File.OpenRead(path);
        var head = new byte[BankIdOffset + 4];
        if (f.Read(head, 0, head.Length) != head.Length)
            throw new IOException("bank header too short: " + path);
        return BitConverter.ToUInt32(head, BankIdOffset);
    }

    public static string PanelText()
    {
        var sb = new StringBuilder("AUDIO FORMAT TESTER   (* hides this)\n");
        foreach (var kv in Labels)
            sb.Append($"  Keypad {(char)('1' + (kv.Key[0] - 'A'))}  {kv.Key}: {kv.Value}\n");
        sb.Append("  Keypad 5  SetMedia: push line A's audio into line D\n");
        sb.Append("  Keypad 6  UnsetMedia and free it     / replay last\n");
        sb.Append("  Keypad 0  restore the installed bank\n");
        sb.Append("  Keypad +  I heard it      Keypad -  silence\n");
        sb.Append(s_TestBankLoaded ? "STATE: TEST bank loaded, voice lines are off, press 0 when done" : "STATE: installed bank");
        return sb.ToString();
    }

    public static Outcome PlayLine(string id)
    {
        string test = "line " + id + " " + Labels[id];
        var sb = new StringBuilder(test + "\n");
        if (!EnsureTestBank(sb))
            return Finish(test, sb, false);
        return PostAndReport(test, (string)s_Tests["lines"][id], sb);
    }

    public static Outcome Replay()
    {
        if (s_LastEvent == null)
            return Quick("replay", "Nothing to replay yet", false);
        return PostAndReport("replay " + LastTest, s_LastEvent, new StringBuilder("Replaying " + LastTest + "\n"));
    }

    public static Outcome Restore()
    {
        var sb = new StringBuilder("Restoring the installed bank\n");
        bool ok = true;
        if (s_TestBankLoaded)
            ok &= Check(sb, "UnloadBank(test)", AkSoundEngine.UnloadBank(s_TestBankId, IntPtr.Zero), () => s_TestBankLoaded = false);
        if (!s_InstalledLoaded)
            ok &= Check(sb, "LoadBank(" + InstalledBankName + ")", AkSoundEngine.LoadBank(InstalledBankName, out _), () => s_InstalledLoaded = true);
        else
            sb.Append("installed bank already loaded\n");
        return Finish("restore", sb, ok);
    }

    // Both banks carry the same event ids, so the installed main bank has to go before the test bank can load.
    private static bool EnsureTestBank(StringBuilder sb)
    {
        if (s_TestBankLoaded)
            return true;
        if (s_InstalledLoaded && !Check(sb, "UnloadBank(installed)", AkSoundEngine.UnloadBank(s_InstalledId, IntPtr.Zero), () => s_InstalledLoaded = false))
            return false;
        byte[] data = File.ReadAllBytes(Path.Combine(s_Dir, (string)s_Tests["bank"]));
        IntPtr mem = Marshal.AllocHGlobal(data.Length);
        try
        {
            Marshal.Copy(data, 0, mem, data.Length);
            return Check(sb, $"LoadBankMemoryCopy({data.Length / 1024} KB)", AkSoundEngine.LoadBankMemoryCopy(mem, (uint)data.Length, out s_TestBankId),
                () => s_TestBankLoaded = true);
        }
        finally { Marshal.FreeHGlobal(mem); }
    }

    public static Outcome SetMediaOverride()
    {
        const string test = "SetMedia override";
        var sb = new StringBuilder(test + ": line D's event should say line A's words if this works\n");
        if (s_TestBankLoaded)
        {
            sb.Append("(test bank is loaded, restoring the installed bank first)\n");
            sb.Append("  " + Restore().Text.Replace("\n", "\n  ") + "\n");
        }
        if (s_MediaSettings != null)
            sb.Append("(media from an earlier SetMedia is still set, press 6 first)\n");
        var cfg = s_Tests["setmedia"];
        byte[] wem = File.ReadAllBytes(Path.Combine(s_Dir, (string)cfg["wem"]));
        s_MediaMemory = Marshal.AllocHGlobal(wem.Length + MediaAlignment);
        s_MediaAligned = new IntPtr((s_MediaMemory.ToInt64() + MediaAlignment - 1) & ~(long)(MediaAlignment - 1));
        Marshal.Copy(wem, 0, s_MediaAligned, wem.Length);
        s_MediaSettings = new AkSourceSettingsArray(1);
        s_MediaSettings[0].sourceID = (uint)cfg["sourceId"];
        s_MediaSettings[0].pMediaMemory = s_MediaAligned;
        s_MediaSettings[0].uMediaSize = (uint)wem.Length;
        if (!Check(sb, $"SetMedia(source {(uint)cfg["sourceId"]}, {wem.Length / 1024} KB)", AkSoundEngine.SetMedia(s_MediaSettings, 1), null))
        {
            FreeMedia();
            return Finish(test, sb, false);
        }
        return PostAndReport(test, (string)cfg["event"], sb);
    }

    public static Outcome UnsetMedia()
    {
        const string test = "UnsetMedia";
        var sb = new StringBuilder(test + "\n");
        if (s_MediaSettings == null)
            return Quick(test, "No SetMedia is active", false);
        var result = AkSoundEngine.UnsetMedia(s_MediaSettings, 1);
        if (result == AKRESULT.AK_ResourceInUse)
        {
            sb.Append("UnsetMedia -> AK_ResourceInUse: a voice was using it and has been stopped.\nRelease is pending, press 6 again in a moment (memory kept until then)\n");
            return Finish(test, sb, true);
        }
        bool ok = Check(sb, "UnsetMedia", result, null);
        if (ok)
            FreeMedia();
        else
            sb.Append("memory kept: the engine may still be using it\n");
        return Finish(test, sb, ok);
    }

    private static void FreeMedia()
    {
        s_MediaSettings?.Dispose();
        s_MediaSettings = null;
        if (s_MediaMemory != IntPtr.Zero)
            Marshal.FreeHGlobal(s_MediaMemory);
        s_MediaMemory = IntPtr.Zero;
    }

    private static Outcome PostAndReport(string test, string evt, StringBuilder sb)
    {
        s_LastEvent = evt;
        s_PostedAt = Time.realtimeSinceStartup;
        s_MessagesShown = 0;
        s_PlayingId = AkSoundEngine.PostEvent(evt, Emitter(), PostFlags, OnEvent, test);
        bool ok = s_PlayingId != 0;
        sb.Append(ok ? $"PostEvent({evt}) -> playing id {s_PlayingId}\nListen now, then + (heard) or - (silent)\n"
                     : $"PostEvent({evt}) FAILED (playing id 0): the event is not loaded\n");
        return Finish(test, sb, ok);
    }

    private static void OnEvent(object cookie, AkCallbackType type, AkCallbackInfo info)
    {
        float t = Time.realtimeSinceStartup - s_PostedAt;
        if (type == AkCallbackType.AK_Duration && info is AkDurationCallbackInfo d)
            Main.Append($"  engine: media found, duration {d.fDuration / 1000f:0.00}s (media id {d.mediaID}, streaming {d.bStreaming})");
        else if (type == AkCallbackType.AK_EndOfEvent)
            Main.Append($"  engine: event ended {t:0.00}s after posting" + (t < 0.3f ? "  <- ended at once, probably nothing played" : ""));
    }

    private static GameObject Emitter()
    {
        if (s_Emitter == null)
        {
            s_Emitter = new GameObject("FormatTesterEmitter");
            UnityEngine.Object.DontDestroyOnLoad(s_Emitter);
        }
        var cam = Camera.main;
        if (cam != null)
            s_Emitter.transform.position = cam.transform.position;
        return s_Emitter;
    }

    private static bool Check(StringBuilder sb, string what, AKRESULT result, Action onSuccess)
    {
        bool ok = result == AKRESULT.AK_Success;
        sb.Append($"{what} -> {result}{(ok ? "" : "  <- FAILED")}\n");
        if (ok)
            onSuccess?.Invoke();
        return ok;
    }

    private static Outcome Finish(string test, StringBuilder sb, bool ok)
    {
        LastTest = test;
        return new Outcome { Test = test, Text = sb.ToString().TrimEnd(), Ok = ok };
    }

    private static Outcome Quick(string test, string text, bool ok) =>
        new Outcome { Test = test, Text = text, Ok = ok };

    // Wwise explains most failures through its monitoring channel (unknown plugin, bad header, media not found).
    private static void InstallMonitor()
    {
        var field = typeof(AkCallbackManager).GetField("m_MonitoringCB", BindingFlags.NonPublic | BindingFlags.Static);
        s_PreviousMonitor = field?.GetValue(null) as AkCallbackManager.MonitoringCallback;
        AkCallbackManager.SetMonitoringCallback(AkMonitorErrorLevel.ErrorLevel_All, OnMonitor);
    }

    private static void OnMonitor(AkMonitorErrorCode code, AkMonitorErrorLevel level, uint playingId, ulong gameObj, string msg)
    {
        s_PreviousMonitor?.Invoke(code, level, playingId, gameObj, msg);
        bool recent = Time.realtimeSinceStartup - s_PostedAt < MessageWindowSeconds;
        if (!recent || s_MessagesShown >= MaxEngineMessages || (playingId != s_PlayingId && level != AkMonitorErrorLevel.ErrorLevel_Error))
            return;
        s_MessagesShown++;
        Main.Append($"  Wwise {level}/{code}: {msg}");
        Main.Record("wwise", LastTest ?? "", $"{level}/{code}: {msg}");
    }
}
