using HarmonyLib;
using Kingmaker.UI.MVVM.View.NetLobby.Base;
using NeuralSpeechMod.Unity.Extensions;
using UnityEngine;

namespace NeuralSpeechMod.Patches;

[HarmonyPatch]
public static class NetLobbyTutorialBlockView_Patch
{
    [HarmonyPatch(typeof(NetLobbyTutorialBlockView), nameof(NetLobbyTutorialBlockView.BindViewImplementation))]
    [HarmonyPostfix]
    public static void AddTutorialHooks(NetLobbyTutorialBlockView __instance)
    {
        if (!Main.Enabled)
            return;

#if DEBUG
        Debug.Log($"{nameof(NetLobbyTutorialBlockView)}_BindViewImplementation_Postfix");
#endif

        __instance.m_BlockDescription.HookupTextToSpeech();
    }
}