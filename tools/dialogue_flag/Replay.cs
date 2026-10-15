using System;
using Kingmaker.UI.Sound;
using Kingmaker.UI.Sound.Base;
using UnityEngine;

namespace DialogueFlag;

// Replays lines from the played-line buffer through the game's own VoiceOverPlayer, so a replay has the same bus,
// speaker position and volume settings as the original and can be compared with it by ear.
internal static class Replay
{
    public const KeyCode BackKey = KeyCode.Keypad7;
    public const KeyCode AgainKey = KeyCode.Keypad8;
    public const KeyCode ForwardKey = KeyCode.Keypad9;
    public const KeyCode LastTwoKey = KeyCode.Keypad5;
    public const KeyCode ChainKey = KeyCode.KeypadEnter;

    private const float GapSeconds = 0.4f;
    private const float MaxLineSeconds = 60f;
    private const int NoCursor = -1;

    private static int s_Cursor = NoCursor;
    private static Main.Played s_LatestAtCursor;
    private static VoiceOverStatus s_Status;
    private static float s_StartedAt;
    private static float s_NextAt;
    private static bool s_Chain;

    // While true the played-line hook ignores new lines, so a replay does not add itself to the history.
    public static bool Suppress { get; private set; }

    public static bool HandleKey(KeyCode key)
    {
        switch (key)
        {
            case BackKey: Step(-1); return true;
            case ForwardKey: Step(1); return true;
            case AgainKey: s_Chain = false; PlayCursor(); return true;
            case LastTwoKey: StartChain(Main.s_Buffer.Count - 2); return true;
            case ChainKey: StartChain(Cursor()); return true;
            default: return false;
        }
    }

    // New lines from the game start a fresh walk back from the latest line.
    private static int Cursor()
    {
        var buf = Main.s_Buffer;
        if (buf.Count == 0 || buf[buf.Count - 1] != s_LatestAtCursor)
        {
            s_Cursor = NoCursor;
            s_LatestAtCursor = buf.Count > 0 ? buf[buf.Count - 1] : null;
        }
        return s_Cursor == NoCursor ? buf.Count - 1 : s_Cursor;
    }

    private static void Step(int delta)
    {
        s_Chain = false;
        int target = Cursor() + delta;
        if (target < 0 || target >= Main.s_Buffer.Count)
        {
            Main.Show(target < 0 ? "Start of the history, nothing earlier" : "That is the latest line", Color.yellow);
            return;
        }
        s_Cursor = target;
        PlayCursor();
    }

    private static void StartChain(int from)
    {
        if (from < 0 || from >= Main.s_Buffer.Count)
        {
            Main.Show("Not enough lines played yet", Color.yellow);
            return;
        }
        Cursor();
        s_Cursor = from;
        s_Chain = true;
        PlayCursor();
    }

    public static void Tick()
    {
        if (!s_Chain || Time.realtimeSinceStartup < s_NextAt || StillPlaying())
            return;
        if (s_Cursor + 1 >= Main.s_Buffer.Count)
        {
            s_Chain = false;
            return;
        }
        s_Cursor++;
        PlayCursor();
    }

    private static bool StillPlaying()
    {
        if (s_Status == null || Time.realtimeSinceStartup - s_StartedAt > MaxLineSeconds)
            return false;
        try { return !s_Status.IsEnded; }
        catch { return false; }
    }

    private static void PlayCursor()
    {
        try
        {
            var line = Main.s_Buffer[s_Cursor];
            StopEverything();
            Suppress = true;
            try { s_Status = VoiceOverPlayer.PlayVoiceOver(line.Event, line.TargetObject); }
            finally { Suppress = false; }
            s_StartedAt = Time.realtimeSinceStartup;
            s_NextAt = s_StartedAt + GapSeconds;
            string where = $"{s_Cursor + 1}/{Main.s_Buffer.Count}" + (s_Chain ? " (playing on)" : "");
            if (s_Status == null)
            {
                s_Chain = false;
                Main.Show($"Replay {where} would not start: {line.Event}", Color.red);
                return;
            }
            Main.Show($"Replay {where}  {line.Target}\n{Main.Preview(line)}", new Color(0.6f, 0.85f, 1f));
        }
        catch (Exception e)
        {
            s_Chain = false;
            Main.Show("Replay failed: " + e.Message, Color.red);
            Main.Log.Log($"replay failed: {e}");
        }
    }

    private static void StopEverything()
    {
        try { s_Status?.Stop(); } catch { }
        foreach (var p in Main.s_Buffer)
        {
            if (!Main.IsPlaying(p)) continue;
            try { p.Status.Stop(); } catch { }
        }
    }
}
