using HarmonyLib;
using Kingmaker.UI.MVVM.View.NetLobby.PC;
using NeuralSpeechMod.Unity.Extensions;
using UnityEngine;

namespace NeuralSpeechMod.Patches;

[HarmonyPatch]
public static class NetLobbyCreateJoinPartPCView_Patch
{
    [HarmonyPatch(typeof(NetLobbyCreateJoinPartPCView), nameof(NetLobbyCreateJoinPartPCView.BindViewImplementation))]
    [HarmonyPostfix]
    public static void AddDescriptionHook(NetLobbyCreateJoinPartPCView __instance)
    {
        if (!Main.Enabled)
            return;

#if DEBUG
        Debug.Log($"{nameof(NetLobbyCreateJoinPartPCView)}_BindViewImplementation_Postfix");
#endif

        __instance.m_NeedSameRegionAndCoopVerDescription.HookupTextToSpeech();
    }
}