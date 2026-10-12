using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using HarmonyLib;

namespace DialogueFlag;

// Debug trace of the Wwise calls, to find out who posts, stops or mutes voice audio.
// Patches AkSoundEngine by reflection (no compile-time reference) and writes audio_debug.log in the mod folder.
public static class AudioDebug
{
    private const string LogFile = "audio_debug.log";
    private const string EngineType = "AkSoundEngine";
    private const string VoicePrefix = "ev_";
    private const int StackFrames = 7;
    private const int MaxRtpcLines = 300;
    private static readonly string[] PostMethods = { "PostEvent" };
    private static readonly string[] StopMethods = { "StopPlayingID", "StopAll", "ExecuteActionOnEvent" };
    private static readonly string[] BankMethods = { "LoadBank", "UnloadBank" };
    private static readonly string[] RtpcMethods = { "SetRTPCValue" };
    private static readonly string[] OwnerDumpTypes = { "VoiceOverPlayer", "SoundEventsManager", EngineType };

    private static string s_Path;
    private static Harmony s_Harmony;
    private static int s_RtpcLines;
    private static int s_OtherPosts;
    private static bool s_OwnersDumped;
    private static readonly Dictionary<uint, string> s_EventNames = new Dictionary<uint, string>();
    private static readonly Dictionary<string, float> s_LastRtpc = new Dictionary<string, float>();

    // The trace patches every PostEvent and writes a large log, so it only runs when this marker file exists in the mod folder.
    private const string EnableMarker = "audio_debug.on";

    public static void Install(Harmony harmony, string dir)
    {
        if (!File.Exists(Path.Combine(dir, EnableMarker)))
            return;
        s_Harmony = harmony;
        s_Path = Path.Combine(dir, LogFile);
        Write("=== audio debug start ===");
        var engine = AppDomain.CurrentDomain.GetAssemblies()
            .Select(a => a.GetType(EngineType, false)).FirstOrDefault(t => t != null);
        if (engine == null)
        {
            Write("AkSoundEngine type not found, nothing patched");
            return;
        }
        Write($"AkSoundEngine in {engine.Assembly.GetName().Name}");
        ApplyPatch(engine, PostMethods, nameof(PostEventPrefix), nameof(PostEventPostfix));
        ApplyPatch(engine, StopMethods, nameof(StopPrefix), null);
        ApplyPatch(engine, BankMethods, nameof(BankPrefix), null);
        ApplyPatch(engine, RtpcMethods, nameof(RtpcPrefix), null);
    }

    public static void RememberEvent(string name)
    {
        if (!string.IsNullOrEmpty(name))
            s_EventNames[Fnv32(name)] = name;
    }

    private static void ApplyPatch(Type engine, string[] names, string prefix, string postfix)
    {
        foreach (var m in engine.GetMethods(BindingFlags.Public | BindingFlags.Static).Where(m => names.Contains(m.Name)))
        {
            try
            {
                s_Harmony.Patch(m,
                    new HarmonyMethod(typeof(AudioDebug), prefix),
                    postfix == null ? null : new HarmonyMethod(typeof(AudioDebug), postfix));
                Write($"patched {Describe(m)}");
            }
            catch (Exception e)
            {
                Write($"could not patch {Describe(m)}: {e.Message}");
            }
        }
    }

    public static void PostEventPrefix(MethodBase __originalMethod, object[] __args)
    {
        try
        {
            string name = EventName(__args);
            if (name == null || !name.StartsWith(VoicePrefix))
            {
                s_OtherPosts++;
                return;
            }
            DumpOwnersOnce();
            Write($"POST {name} args=[{Args(__args)}]\n    from {Caller()}");
        }
        catch (Exception e) { Write($"prefix failed: {e.Message}"); }
    }

    // Playing id 0 means Wwise rejected the post (event not in a loaded bank, bad game object, ...).
    public static void PostEventPostfix(object[] __args, uint __result)
    {
        try
        {
            string name = EventName(__args);
            if (name == null || !name.StartsWith(VoicePrefix))
                return;
            Write($"  -> playingId {__result}{(__result == 0 ? "  *** REJECTED by Wwise ***" : "")} for {name}");
        }
        catch (Exception e) { Write($"postfix failed: {e.Message}"); }
    }

    public static void StopPrefix(MethodBase __originalMethod, object[] __args)
        => Write($"STOP {__originalMethod.Name}({Args(__args)})\n    from {Caller()}");

    public static void BankPrefix(MethodBase __originalMethod, object[] __args)
        => Write($"BANK {__originalMethod.Name}({Args(__args)})");

    public static void RtpcPrefix(object[] __args)
    {
        try
        {
            if (__args.Length < 2 || s_RtpcLines >= MaxRtpcLines)
                return;
            string key = __args[0]?.ToString() ?? "?";
            float value = Convert.ToSingle(__args[1], CultureInfo.InvariantCulture);
            if (s_LastRtpc.TryGetValue(key, out float last) && Math.Abs(last - value) < 0.01f)
                return;
            s_LastRtpc[key] = value;
            s_RtpcLines++;
            Write($"RTPC {key} = {value.ToString("0.##", CultureInfo.InvariantCulture)}");
        }
        catch { }
    }

    // Who has patched the voice path, in apply order: owners of prefixes and postfixes per method.
    private static void DumpOwnersOnce()
    {
        if (s_OwnersDumped)
            return;
        s_OwnersDumped = true;
        Write($"non-voice PostEvent calls so far: {s_OtherPosts}");
        foreach (var m in Harmony.GetAllPatchedMethods().Where(m => OwnerDumpTypes.Contains(m.DeclaringType?.Name)))
        {
            var info = Harmony.GetPatchInfo(m);
            Write($"patched {Describe(m)}: prefixes [{Owners(info.Prefixes)}] postfixes [{Owners(info.Postfixes)}] " +
                  $"transpilers [{Owners(info.Transpilers)}] finalizers [{Owners(info.Finalizers)}]");
        }
        Write("loaded mod assemblies: " + string.Join(", ", AppDomain.CurrentDomain.GetAssemblies()
            .Select(a => a.GetName().Name).Where(n => n.IndexOf("AIVO", StringComparison.OrdinalIgnoreCase) >= 0
                || n.IndexOf("Speech", StringComparison.OrdinalIgnoreCase) >= 0 || n.IndexOf("Voice", StringComparison.OrdinalIgnoreCase) >= 0)));
    }

    private static string Owners(IEnumerable<Patch> patches)
        => string.Join(" ", patches.Select(p => $"{p.owner}:{p.PatchMethod.DeclaringType?.Name}.{p.PatchMethod.Name}(prio {p.priority})"));

    // First frames outside Harmony and this class, with their assemblies: tells which mod posted.
    private static string Caller()
    {
        var frames = new StackTrace(2, false).GetFrames() ?? new StackFrame[0];
        var parts = new List<string>();
        foreach (var f in frames)
        {
            var m = f.GetMethod();
            var type = m?.DeclaringType;
            if (type == null || type.Assembly == typeof(AudioDebug).Assembly || type.Namespace == "HarmonyLib"
                || (m.Name ?? "").StartsWith("DMD<"))
                continue;
            parts.Add($"{type.Assembly.GetName().Name}!{type.Name}.{m.Name}");
            if (parts.Count >= StackFrames)
                break;
        }
        return string.Join(" < ", parts);
    }

    private static string EventName(object[] args)
    {
        if (args == null || args.Length == 0)
            return null;
        if (args[0] is string s)
            return s;
        if (args[0] is uint id)
            return s_EventNames.TryGetValue(id, out var n) ? n : "id:" + id;
        return null;
    }

    private static string Args(object[] args)
        => args == null ? "" : string.Join(", ", args.Select(a => a == null ? "null" : Shorten(a.ToString())));

    private static string Shorten(string s) => s.Length > 80 ? s.Substring(0, 80) + "..." : s;

    private static string Describe(MethodBase m)
        => $"{m.DeclaringType?.Name}.{m.Name}({string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name))})";

    private static uint Fnv32(string name)
    {
        uint h = 2166136261;
        foreach (char c in name.ToLowerInvariant())
            h = unchecked(h * 16777619) ^ c;
        return h;
    }

    private static void Write(string line)
    {
        try
        {
            File.AppendAllText(s_Path, DateTime.Now.ToString("HH:mm:ss.fff", CultureInfo.InvariantCulture) + " " + line + "\n",
                new UTF8Encoding(false));
        }
        catch { }
    }
}
