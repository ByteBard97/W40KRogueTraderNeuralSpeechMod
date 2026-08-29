using HarmonyLib;
using NeuralSpeechMod.Configuration;
using NeuralSpeechMod.KeyBinds;
using NeuralSpeechMod.Unity;
using NeuralSpeechMod.Unity.Extensions;
using NeuralSpeechMod.Voice;
using System;
using System.Reflection;
using TMPro;
using UnityEngine;
using UnityModManagerNet;

namespace NeuralSpeechMod;

#if DEBUG
[EnableReloading]
#endif
public static class Main
{
    public static UnityModManager.ModEntry.ModLogger Logger;
    public static Settings Settings;
    public static bool Enabled;
    public static string[] FontStyleNames = Enum.GetNames(typeof(FontStyles));

    public static ISpeech Speech;
    private static bool m_Loaded = false;

    private static bool Load(UnityModManager.ModEntry modEntry)
    {
        Debug.Log("Warhammer 40K: Rogue Trader Speech Mod Initializing...");

        Logger = modEntry?.Logger;

        if (!SetSpeech())
            return false;

        Settings = UnityModManager.ModSettings.Load<Settings>(modEntry);
        Hooks.UpdateHoverColor();

        modEntry!.OnToggle = OnToggle;
        modEntry!.OnGUI = OnGui;
        modEntry!.OnSaveGUI = OnSaveGui;

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
