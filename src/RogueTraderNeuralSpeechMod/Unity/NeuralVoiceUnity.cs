using System;
using System.Collections;
using System.IO;
using System.Text;
using Newtonsoft.Json.Linq;
using NeuralSpeechMod.Voice;
using UnityEngine;
using UnityEngine.Networking;

namespace NeuralSpeechMod.Unity;

/// <summary>
/// Talks to the local TTS sidecar (src/TtsSidecar, default http://127.0.0.1:8765) and plays the
/// result via NativeAudioPlayer.
///
/// This does NOT use Unity's AudioSource/AudioClip: Rogue Trader ships with Unity's own audio
/// engine disabled (globalgamemanagers: AudioManager.m_DisableAudio = true - confirmed directly
/// via UnityPy, not the AIVOMod Wwise-bank evidence, which only proves Wwise's own path works).
/// UnityWebRequest itself is unaffected (it's networking, not audio), so this class still uses a
/// coroutine to fetch bytes from the sidecar asynchronously; only the final "play the WAV" step
/// is handed off to NativeAudioPlayer, which talks to the OS audio device directly.
/// </summary>
public class NeuralVoiceUnity : MonoBehaviour
{
    private const string SIDECAR_URL = "http://127.0.0.1:8765";

    private static NeuralVoiceUnity s_Instance;
    private static UnityWebRequest s_CurrentRequest;
    private static string s_LastError;

    private void Start()
    {
        if (s_Instance != null)
        {
            Destroy(gameObject);
            return;
        }
        s_Instance = this;
    }

    public static bool IsSpeaking => NativeAudioPlayer.IsPlaying();

    public static void Speak(string text, string speaker, float delay = 0f, string cueGuid = null)
    {
        if (s_Instance == null)
        {
            Main.Logger?.Warning("NeuralVoiceUnity not initialized yet, dropping line.");
            return;
        }
        s_Instance.StartCoroutine(SpeakCoroutine(text, speaker, delay, cueGuid));
    }

    private static IEnumerator SpeakCoroutine(string text, string speaker, float delay, string cueGuid)
    {
        if (Main.Settings != null && Main.Settings.InterruptPlaybackOnPlay && IsSpeaking)
            Stop();

        if (delay > 0f)
            yield return new WaitForSeconds(delay);

        var bodyObj = new JObject { ["text"] = text, ["speaker"] = speaker };
        if (!string.IsNullOrEmpty(cueGuid))
        {
            bodyObj["cue_guid"] = cueGuid;
            var annotation = AnnotationStore.Resolve(cueGuid);
            if (annotation != null)
                bodyObj["annotation"] = annotation;
        }
        var body = bodyObj.ToString(Newtonsoft.Json.Formatting.None);
        using var req = new UnityWebRequest(SIDECAR_URL + "/synth", UnityWebRequest.kHttpVerbPOST)
        {
            uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(body)) { contentType = "application/json" },
            downloadHandler = new DownloadHandlerBuffer(),
        };
        s_CurrentRequest = req;

        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            s_LastError = req.error;
            Main.Logger?.Warning($"Sidecar request failed ({req.responseCode}): {req.error}");
            yield break;
        }

        s_LastError = null;
        // Unique filename per request: two lines can be in flight at once (e.g. a bark firing
        // while a dialogue line is still playing), and MCI holds its wave file open for the
        // duration of playback - a shared fixed path caused a real IOException: Sharing
        // violation race, caught by an in-game self-test before this fix went out.
        var wavPath = Path.Combine(Path.GetTempPath(), $"rt_neural_tts_{Guid.NewGuid():N}.wav");
        File.WriteAllBytes(wavPath, req.downloadHandler.data);
        NativeAudioPlayer.Play(wavPath);
    }

    public static void Stop()
    {
        if (s_CurrentRequest is { isDone: false })
            s_CurrentRequest.Abort();
        NativeAudioPlayer.Stop();
    }

    public static string GetStatusMessage() =>
        s_LastError == null ? "Neural speech sidecar OK" : $"Sidecar error: {s_LastError} (is the sidecar running on {SIDECAR_URL}?)";
}
