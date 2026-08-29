using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;

namespace NeuralSpeechMod.Voice;

/// <summary>
/// Plays a WAV file straight to the OS audio device, bypassing Unity's audio engine entirely.
/// Rogue Trader is a Wwise title that ships with Unity's own audio disabled
/// (globalgamemanagers: AudioManager.m_DisableAudio = true, confirmed via UnityPy inspection) -
/// AudioSource/AudioClip are silent no-ops here, so playback has to go around Unity, not through
/// it. On Windows (including under Proton/Wine, where winmm.dll is one of the most completely
/// reimplemented system DLLs) this uses the classic MCI waveaudio device, which gives a real
/// play/stop/status API for free. macOS and native Linux builds shell out to the platform's own
/// player instead.
/// </summary>
internal static class NativeAudioPlayer
{
    [DllImport("winmm.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern int mciSendString(string command, StringBuilder returnBuffer, int returnLength, IntPtr callback);

    private const string MciAlias = "rtneuraltts";
    private static Process s_ExternalProcess;
    private static string s_LastWavPath;

    public static void Play(string wavPath)
    {
        Stop();
        // The previous file's device/process is now closed, so it's safe to delete - each call
        // gets its own temp file (see NeuralVoiceUnity), so this is the only place anything
        // cleans them up. Best-effort: a failed delete just leaves a few KB behind.
        if (s_LastWavPath != null && s_LastWavPath != wavPath)
        {
            try { System.IO.File.Delete(s_LastWavPath); }
            catch { /* still locked somewhere, or already gone - fine either way */ }
        }
        s_LastWavPath = wavPath;

        switch (Application.platform)
        {
            case RuntimePlatform.WindowsPlayer:
            case RuntimePlatform.WindowsEditor:
                PlayViaMci(wavPath);
                break;
            case RuntimePlatform.OSXPlayer:
            case RuntimePlatform.OSXEditor:
                TryPlayViaProcess("afplay", $"\"{wavPath}\"");
                break;
            default:
                // Native Linux (no Wine underneath): PulseAudio first, ALSA fallback.
                if (!TryPlayViaProcess("paplay", $"\"{wavPath}\""))
                    TryPlayViaProcess("aplay", $"\"{wavPath}\"");
                break;
        }
    }

    public static bool IsPlaying()
    {
        if (Application.platform is RuntimePlatform.WindowsPlayer or RuntimePlatform.WindowsEditor)
        {
            var buf = new StringBuilder(64);
            mciSendString($"status {MciAlias} mode", buf, buf.Capacity, IntPtr.Zero);
            return buf.ToString().Trim().Equals("playing", StringComparison.OrdinalIgnoreCase);
        }
        return s_ExternalProcess is { HasExited: false };
    }

    public static void Stop()
    {
        var buf = new StringBuilder(64);
        mciSendString($"stop {MciAlias}", buf, buf.Capacity, IntPtr.Zero);
        mciSendString($"close {MciAlias}", buf, buf.Capacity, IntPtr.Zero);
        if (s_ExternalProcess is { HasExited: false })
        {
            try { s_ExternalProcess.Kill(); }
            catch { /* already exiting */ }
        }
        s_ExternalProcess = null;
    }

    private static void PlayViaMci(string wavPath)
    {
        var buf = new StringBuilder(128);
        var openRc = mciSendString($"open \"{wavPath}\" type waveaudio alias {MciAlias}", buf, buf.Capacity, IntPtr.Zero);
        var playRc = mciSendString($"play {MciAlias}", buf, buf.Capacity, IntPtr.Zero);
        UnityEngine.Debug.Log($"NativeAudioPlayer: MCI open rc={openRc} play rc={playRc} ({wavPath})");
    }

    private static bool TryPlayViaProcess(string exe, string args)
    {
        try
        {
            s_ExternalProcess = Process.Start(new ProcessStartInfo
            {
                FileName = exe,
                Arguments = args,
                UseShellExecute = false,
                CreateNoWindow = true,
            });
            return s_ExternalProcess != null;
        }
        catch (System.Exception e)
        {
            UnityEngine.Debug.LogWarning($"NativeAudioPlayer: failed to launch '{exe} {args}': {e.Message}");
            return false;
        }
    }
}
