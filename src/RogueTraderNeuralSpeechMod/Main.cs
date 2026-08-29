using HarmonyLib;
using NeuralSpeechMod.Configuration;
using NeuralSpeechMod.KeyBinds;
using NeuralSpeechMod.Unity;
using NeuralSpeechMod.Unity.Extensions;
using NeuralSpeechMod.Voice;
using System;
using System.IO;
using System.Reflection;
using TMPro;
using UnityEngine;
using UnityModManagerNet;

namespace NeuralSpeechMod;

#if DEBUG
[EnableReloading]
#endif
/// <summary>
/// Control files in the mod directory (unattended runtime self-test, mirrors DialogueExporter's
/// export.request pattern):
///   speech_test.request - if present, run a playback self-test a few seconds after load
///                          (SpeakPreview as narrator, then SpeakAsCharacter if a companion voice
///                          is known); writes speech_test_result.txt; "quit" in its content exits
///                          the game afterward. Exists because the whole point of this test is to
///                          get evidence into a file/log without a human needing to be listening.
/// </summary>
public static class Main
{
    public static UnityModManager.ModEntry.ModLogger Logger;
    public static Settings Settings;
    public static bool Enabled;
    public static string[] FontStyleNames = Enum.GetNames(typeof(FontStyles));

    public static ISpeech Speech;
    private static bool m_Loaded = false;
    private static string s_ModDir;
    private static float s_TestWaitSeconds;
    private static int s_TestState; // 0 = idle/not requested, 1 = running, 2 = done, 3 = quitting
    private static float s_QuitCountdown;

    private static bool Load(UnityModManager.ModEntry modEntry)
    {
        Debug.Log("Warhammer 40K: Rogue Trader Speech Mod Initializing...");

        Logger = modEntry?.Logger;
        s_ModDir = modEntry?.Path;

        if (!SetSpeech())
            return false;

        Settings = UnityModManager.ModSettings.Load<Settings>(modEntry);
        Hooks.UpdateHoverColor();

        modEntry!.OnToggle = OnToggle;
        modEntry!.OnGUI = OnGui;
        modEntry!.OnSaveGUI = OnSaveGui;
        modEntry!.OnUpdate = OnUpdate;

        var harmony = new Harmony(modEntry.Info?.Id);
        harmony.PatchAll(Assembly.GetExecutingAssembly());

        ModConfigurationManager.Build(harmony, modEntry, Constants.SETTINGS_PREFIX);
        SetUpSettings();
        harmony.CreateClassProcessor(typeof(SettingsUIPatches)).Patch();

        Logger?.Log(Speech?.GetStatusMessage());

        var availableVoices = Speech?.GetAvailableVoices();
        if (availableVoices == null || availableVoices.Length == 0)
        {
            Logger?.Warning("No available voices found! Disabling mod!");
            return false;
        }

        Debug.Log("Warhammer 40K: Rogue Trader Speech Mod Initialized!");
        m_Loaded = true;
        return true;
    }

    private static void OnUpdate(UnityModManager.ModEntry modEntry, float dt)
    {
        if (s_TestState == 3)
        {
            // Main-thread countdown before quitting, so the sidecar's two async requests have
            // time to land - Application.Quit() must run from here, not a background continuation.
            s_QuitCountdown -= dt;
            if (s_QuitCountdown <= 0f)
                Application.Quit();
            return;
        }

        if (!m_Loaded || s_TestState != 0)
            return;

        var requestFile = Path.Combine(s_ModDir, "speech_test.request");
        if (!File.Exists(requestFile))
            return;

        // Give the sidecar/mod a moment to settle after load before firing test requests.
        s_TestWaitSeconds += dt;
        if (s_TestWaitSeconds < 3f)
            return;

        s_TestState = 1;
        var quit = File.ReadAllText(requestFile).IndexOf("quit", StringComparison.OrdinalIgnoreCase) >= 0;
        RunSpeechSelfTest(requestFile, quit);
    }

    private static void RunSpeechSelfTest(string requestFile, bool quitAfter)
    {
        var log = new System.Text.StringBuilder();
        log.AppendLine($"[{DateTime.Now:O}] Neural speech self-test starting.");
        log.AppendLine($"Sidecar status: {Speech?.GetStatusMessage()}");

        Speech?.SpeakPreview("This is a test of the neural narrator voice.", VoiceType.Narrator);
        log.AppendLine("Fired SpeakPreview(narrator).");

        var known = SpeakerMap.AnyKnownEntry();
        if (known.HasValue)
        {
            Speech?.SpeakAsCharacter("This is a test of a specific companion voice.", known.Value.guid, VoiceType.Narrator);
            log.AppendLine($"Fired SpeakAsCharacter(guid={known.Value.guid}, name={known.Value.name}).");
        }
        else
        {
            log.AppendLine("No known speaker_map entries loaded - SpeakAsCharacter not exercised.");
        }

        log.AppendLine($"Wrote {log.Length} chars of test log. Check Player.log for NativeAudioPlayer MCI/process lines and the sidecar's own log for /synth requests.");

        try
        {
            File.WriteAllText(Path.Combine(s_ModDir, "speech_test_result.txt"), log.ToString());
        }
        catch (Exception e)
        {
            Logger?.Warning($"Could not write speech_test_result.txt: {e.Message}");
        }

        if (File.Exists(requestFile))
            File.Delete(requestFile);

        if (quitAfter)
        {
            s_QuitCountdown = 25f;
            s_TestState = 3;
        }
        else
        {
            s_TestState = 2;
        }
    }

    private static void SetUpSettings()
    {
        if (ModConfigurationManager.Instance.GroupedSettings.TryGetValue("main", out _))
            return;

        ModConfigurationManager.Instance.GroupedSettings.Add("main", [new PlaybackStop(), new ToggleBarks()]);
    }

    private static bool SetSpeech()
    {
        // Unlike upstream (SAPI on Windows, `say` on macOS, unsupported elsewhere), the sidecar
        // is a local HTTP server, so the same backend works on every platform UMM runs on.
        Speech = new NeuralSpeech();
        SpeechExtensions.AddUiElements<NeuralVoiceUnity>(Constants.NEURAL_VOICE_NAME);
        return true;
    }

    private static bool OnToggle(UnityModManager.ModEntry modEntry, bool value)
    {
        Enabled = value;
        return true;
    }

    private static void OnGui(UnityModManager.ModEntry modEntry)
    {
        if (m_Loaded)
            MenuGUI.OnGui();
    }

    private static void OnSaveGui(UnityModManager.ModEntry modEntry)
    {
        Hooks.UpdateHoverColor();
        Settings?.Save(modEntry);
    }
}
