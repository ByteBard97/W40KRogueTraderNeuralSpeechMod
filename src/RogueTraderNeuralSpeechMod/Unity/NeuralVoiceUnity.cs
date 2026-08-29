using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace NeuralSpeechMod.Unity;

/// <summary>
/// Talks to the local TTS sidecar (src/TtsSidecar, default http://127.0.0.1:8765) and plays the
/// result. UnityWebRequestMultimedia.GetAudioClip(..., AudioType.WAV) does the WAV decode - the
/// sidecar always returns 16-bit PCM mono WAV, which is exactly what that decoder expects, so no
/// manual header parsing is needed here.
///
/// NOTE: this assumes Unity's own audio engine (AudioSource/AudioClip) is active for this game.
/// RT is a Wwise title; if that turns out to be disabled (the open spike in PROJECT_PLAN.md),
/// this class is the one that gets swapped for a Wwise external-source player - the ISpeech
/// abstraction (NeuralSpeech.cs) does not need to change.
/// </summary>
public class NeuralVoiceUnity : MonoBehaviour
{
    private const string SIDECAR_URL = "http://127.0.0.1:8765";

    private static NeuralVoiceUnity s_Instance;
    private static AudioSource s_AudioSource;
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
        s_AudioSource = gameObject.AddComponent<AudioSource>();
        s_AudioSource.playOnAwake = false;
    }

    public static bool IsSpeaking => s_AudioSource != null && s_AudioSource.isPlaying;

    public static void Speak(string text, string speaker, float delay = 0f)
    {
        if (s_Instance == null)
        {
            Main.Logger?.Warning("NeuralVoiceUnity not initialized yet, dropping line.");
            return;
        }
        s_Instance.StartCoroutine(SpeakCoroutine(text, speaker, delay));
    }

    private static IEnumerator SpeakCoroutine(string text, string speaker, float delay)
    {
        if (Main.Settings != null && Main.Settings.InterruptPlaybackOnPlay && IsSpeaking)
            Stop();

        if (delay > 0f)
            yield return new WaitForSeconds(delay);

        var body = "{\"text\":" + JsonString(text) + ",\"speaker\":" + JsonString(speaker) + "}";
        using var req = UnityWebRequestMultimedia.GetAudioClip(SIDECAR_URL + "/synth", AudioType.WAV);
        req.method = UnityWebRequest.kHttpVerbPOST;
        req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(body)) { contentType = "application/json" };
        s_CurrentRequest = req;

        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            s_LastError = req.error;
            Main.Logger?.Warning($"Sidecar request failed ({req.responseCode}): {req.error}");
            yield break;
        }

        s_LastError = null;
        var clip = DownloadHandlerAudioClip.GetContent(req);
        if (s_AudioSource == null)
            yield break;
        s_AudioSource.clip = clip;
        s_AudioSource.Play();
    }

    public static void Stop()
    {
        if (s_CurrentRequest is { isDone: false })
            s_CurrentRequest.Abort();
        if (s_AudioSource != null)
            s_AudioSource.Stop();
    }

    public static string GetStatusMessage() =>
        s_LastError == null ? "Neural speech sidecar OK" : $"Sidecar error: {s_LastError} (is the sidecar running on {SIDECAR_URL}?)";

    private static string JsonString(string s) => "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
}
