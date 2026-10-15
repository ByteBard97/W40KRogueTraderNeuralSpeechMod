using HarmonyLib;
using Kingmaker.UI.Sound;
using Kingmaker.UI.Sound.Base;
using UnityEngine;

namespace DialogueFlag;

[HarmonyPatch(typeof(VoiceOverPlayer), nameof(VoiceOverPlayer.PlayVoiceOver), typeof(string), typeof(MonoBehaviour))]
public static class PlayByBehaviour
{
    public static void Postfix(string voiceOverSound, MonoBehaviour target, VoiceOverStatus __result)
        => Main.RecordPlayed(voiceOverSound, target != null ? target.gameObject : null, __result);
}

[HarmonyPatch(typeof(VoiceOverPlayer), nameof(VoiceOverPlayer.PlayVoiceOver), typeof(string), typeof(GameObject))]
public static class PlayByObject
{
    public static void Postfix(string voiceOverSound, GameObject target, VoiceOverStatus __result)
        => Main.RecordPlayed(voiceOverSound, target, __result);
}
