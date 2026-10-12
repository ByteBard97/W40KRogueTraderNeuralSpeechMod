using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using HarmonyLib;
using Kingmaker;
using Kingmaker.UI.Sound.Base;
using UnityEngine;
using UnityModManager = UnityModManagerNet.UnityModManager;

namespace DialogueFlag;

public static class Main
{
    public const KeyCode GoodKey = KeyCode.G;
    public const KeyCode BadKey = KeyCode.B;

    private const string FlagFile = "flags.jsonl";
    private const string PlayedFile = "played.jsonl";
    private const float FeedbackSeconds = 3f;
    private const int BufferSize = 60;
    private const float MaxPlayingSeconds = 60f;
    private const float CandidateWindowSeconds = 45f;
    private const int FeedbackFont = 28;
    private const float FeedbackY = 0.12f;
    private const float FeedbackHeight = 120f;
    private const float ShadowOffset = 2f;
    private const int PreviewChars = 90;
    private const int MaxTextChars = 600;
    private const string EventPrefix = "ev_";

    public sealed class Played
    {
        public string Event;
        public string Target;
        public string Text;
        public DateTime When;
        public float Realtime;
        public VoiceOverStatus Status;
    }

    public static UnityModManager.ModEntry.ModLogger Log;
    private static string s_Dir;
    private static readonly string s_Session = Guid.NewGuid().ToString("N").Substring(0, 8);
    private static readonly List<Played> s_Buffer = new List<Played>();
    private static string s_Feedback;
    private static Color s_FeedbackColor;
    private static float s_FeedbackUntil;
    private static GUIStyle s_Style;

    public static bool Load(UnityModManager.ModEntry modEntry)
    {
        Log = modEntry.Logger;
        s_Dir = modEntry.Path;
        modEntry.OnFixedGUI = OnFixedGui;
        var harmony = new Harmony(modEntry.Info.Id);
        harmony.PatchAll(Assembly.GetExecutingAssembly());
        AudioDebug.Install(harmony, s_Dir);
        Log.Log($"loaded, session {s_Session}, G = good, B = bad, writing to {Path.Combine(s_Dir, FlagFile)}");
        return true;
    }

    public static void RecordPlayed(string voiceOverSound, string target, VoiceOverStatus status)
    {
        try
        {
            if (string.IsNullOrEmpty(voiceOverSound) || status == null)
                return;
            var played = new Played
            {
                Event = voiceOverSound,
                Target = target,
                Text = CurrentCueText(),
                When = DateTime.Now,
                Realtime = Time.realtimeSinceStartup,
                Status = status
            };
            AudioDebug.RememberEvent(voiceOverSound);
            s_Buffer.Add(played);
            if (s_Buffer.Count > BufferSize)
                s_Buffer.RemoveAt(0);
            Append(PlayedFile, Json(played, null, false));
        }
        catch (Exception e)
        {
            Log.Log($"record failed: {e.Message}");
        }
    }

    private static string CurrentCueText()
    {
        try { return Game.Instance?.DialogController?.CurrentCue?.DisplayText; }
        catch { return null; }
    }

    private static void OnFixedGui(UnityModManager.ModEntry modEntry)
    {
        var current = Event.current;
        if (current.type == EventType.KeyDown && !current.shift && !current.control && !current.alt
            && GUIUtility.keyboardControl == 0)
        {
            if (current.keyCode == BadKey)
                Flag("bad");
            else if (current.keyCode == GoodKey)
                Flag("good");
        }
        if (current.type != EventType.Repaint || Time.realtimeSinceStartup > s_FeedbackUntil)
            return;
        s_Style ??= new GUIStyle(GUI.skin.label)
        {
            fontStyle = FontStyle.Bold,
            alignment = TextAnchor.UpperCenter,
            wordWrap = true,
            fontSize = FeedbackFont
        };
        var area = new Rect(Screen.width * 0.1f, Screen.height * FeedbackY, Screen.width * 0.8f, FeedbackHeight);
        s_Style.normal.textColor = Color.black;
        GUI.Label(new Rect(area.x + ShadowOffset, area.y + ShadowOffset, area.width, area.height), s_Feedback, s_Style);
        s_Style.normal.textColor = s_FeedbackColor;
        GUI.Label(area, s_Feedback, s_Style);
    }

    private static void Flag(string verdict)
    {
        bool bad = verdict == "bad";
        var color = bad ? new Color(1f, 0.3f, 0.3f) : new Color(0.4f, 1f, 0.4f);
        var line = PickLine();
        if (line == null)
        {
            Show("No voice line played yet, nothing flagged", Color.yellow);
            return;
        }
        try
        {
            var candidates = s_Buffer.FindAll(p => Time.realtimeSinceStartup - p.Realtime <= CandidateWindowSeconds);
            Append(FlagFile, Json(line, verdict, true, candidates));
            float ago = Time.realtimeSinceStartup - line.Realtime;
            Show($"{(bad ? "FLAGGED BAD" : "Marked good")}  ({ago.ToString("0", CultureInfo.InvariantCulture)}s ago, {candidates.Count} lines saved for review)\n{Preview(line)}", color);
            Log.Log($"{verdict}: {line.Event}");
        }
        catch (Exception e)
        {
            Show($"Could not save flag: {e.Message}", Color.yellow);
            Log.Log($"flag failed: {e}");
        }
    }

    // Status.IsEnded stays false until Wwise reports a duration, so cap the age and survive a null Player.
    private static bool IsPlaying(Played p)
    {
        if (Time.realtimeSinceStartup - p.Realtime > MaxPlayingSeconds)
            return false;
        try { return !p.Status.IsEnded; }
        catch { return false; }
    }

    // The line still playing wins; otherwise the most recent one.
    private static Played PickLine()
    {
        for (int i = s_Buffer.Count - 1; i >= 0; i--)
            if (IsPlaying(s_Buffer[i]))
                return s_Buffer[i];
        return s_Buffer.Count > 0 ? s_Buffer[s_Buffer.Count - 1] : null;
    }

    private static string Preview(Played line)
    {
        string text = string.IsNullOrEmpty(line.Text) ? line.Event : line.Text;
        return text.Length > PreviewChars ? text.Substring(0, PreviewChars) + "..." : text;
    }

    private static void Show(string message, Color color)
    {
        s_Feedback = message;
        s_FeedbackColor = color;
        s_FeedbackUntil = Time.realtimeSinceStartup + FeedbackSeconds;
    }

    private static void Append(string file, string line)
    {
        File.AppendAllText(Path.Combine(s_Dir, file), line + "\n", new UTF8Encoding(false));
    }

    private static string Json(Played p, string verdict, bool full, List<Played> candidates = null)
    {
        var sb = new StringBuilder("{");
        Field(sb, "ts", p.When.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture));
        Field(sb, "session", s_Session);
        if (verdict != null)
            Field(sb, "verdict", verdict);
        Field(sb, "event", p.Event);
        string guid = p.Event.StartsWith(EventPrefix) ? p.Event.Substring(EventPrefix.Length) : p.Event;
        Field(sb, "guid", guid);
        Field(sb, "target", p.Target);
        Field(sb, "text", p.Text != null && p.Text.Length > MaxTextChars ? p.Text.Substring(0, MaxTextChars) : p.Text);
        if (full)
        {
            sb.Append($"\"heard_s_ago\":{(Time.realtimeSinceStartup - p.Realtime).ToString("0.0", CultureInfo.InvariantCulture)},");
            sb.Append($"\"still_playing\":{(IsPlaying(p) ? "true" : "false")},");
            sb.Append("\"candidates\":[");
            for (int i = 0; candidates != null && i < candidates.Count; i++)
            {
                var c = candidates[i];
                if (i > 0) sb.Append(',');
                sb.Append('{');
                Field(sb, "event", c.Event);
                Field(sb, "text", c.Text);
                sb.Append($"\"ago_s\":{(Time.realtimeSinceStartup - c.Realtime).ToString("0.0", CultureInfo.InvariantCulture)},");
                sb.Append($"\"still_playing\":{(IsPlaying(c) ? "true" : "false")},");
                sb.Length--;
                sb.Append('}');
            }
            sb.Append("],");
        }
        sb.Length--;
        return sb.Append('}').ToString();
    }

    private static void Field(StringBuilder sb, string name, string value)
    {
        sb.Append('"').Append(name).Append("\":");
        if (value == null)
        {
            sb.Append("null,");
            return;
        }
        sb.Append('"');
        foreach (char c in value)
        {
            switch (c)
            {
                case '"': sb.Append("\\\""); break;
                case '\\': sb.Append("\\\\"); break;
                case '\n': sb.Append("\\n"); break;
                case '\r': break;
                case '\t': sb.Append("\\t"); break;
                default:
                    if (c < ' ') sb.Append("\\u").Append(((int)c).ToString("x4"));
                    else sb.Append(c);
                    break;
            }
        }
        sb.Append("\",");
    }
}
