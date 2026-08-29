using HarmonyLib;
using Kingmaker;
using Kingmaker.Blueprints.Base;
using Kingmaker.Code.UI.MVVM.VM.Bark;
using Kingmaker.EntitySystem.Entities;
using Kingmaker.EntitySystem.Entities.Base;
using Kingmaker.GameModes;
using Kingmaker.Mechanics.Entities;
using NeuralSpeechMod.Voice;
using System;
using UnityEngine;

namespace NeuralSpeechMod.Patches;

[HarmonyPatch]
public class BarkPlayer_Patch
{
    [HarmonyPatch(typeof(BarkPlayer), nameof(BarkPlayer.Bark), typeof(Entity), typeof(string), typeof(float), typeof(string), typeof(BaseUnitEntity), typeof(bool), typeof(string), typeof(Color))]
    [HarmonyPostfix]
    public static void Bark(Entity entity, string text, float duration = -1f, string voiceOver = null, BaseUnitEntity interactUser = null, bool synced = true, string overrideName = null, Color overrideNameColor = default(Color))
    {
        if (!BarkExtensions.PlayBark())
            return;

#if DEBUG
        Debug.Log($"{nameof(BarkPlayer)}_Bark_Postfix");
#endif

        BarkExtensions.DoBark(entity, text, voiceOver);
    }

    [HarmonyPatch(typeof(BarkPlayer), nameof(BarkPlayer.BarkExploration), typeof(Entity), typeof(string), typeof(float), typeof(string))]
    [HarmonyPostfix]
    public static void BarkExploration_1(Entity entity, string text, float duration = -1f, string voiceOver = null)
    {
        if (!BarkExtensions.PlayBark())
            return;

#if DEBUG
        Debug.Log($"{nameof(BarkPlayer)}_BarkExploration_1_Postfix");
#endif

        BarkExtensions.DoBark(entity, text, voiceOver);
    }

    [HarmonyPatch(typeof(BarkPlayer), nameof(BarkPlayer.BarkExploration), typeof(Entity), typeof(string), typeof(string), typeof(float), typeof(string))]
    [HarmonyPostfix]
    public static void BarkExploration_2(Entity entity, string text, string encyclopediaLink, float duration = -1f, string voiceOver = null)
    {
        if (!BarkExtensions.PlayBark())
            return;

#if DEBUG
        Debug.Log($"{nameof(BarkPlayer)}_BarkExploration_2_Postfix");
#endif

        BarkExtensions.DoBark(entity, text, voiceOver);
    }
}

public static class BarkExtensions
{
    public static bool PlayBark()
    {
        if (!Main.Enabled)
            return false;

        if (!Main.Settings!.PlaybackBarks)
            return false;

        // Don't play barks if we are in a dialog.
        if (Game.Instance == null || Game.Instance.IsModeActive(GameModeType.Dialog))
            return false;

        switch (Main.Settings.PlaybackBarkOnlyIfSilence)
        {
            case true when Main.Speech?.IsSpeaking() == true:
            case true when Game.Instance.DialogController?.CurrentCue != null:
                return false;
        }

        if (!Main.Settings.PlaybackBarksInVicinity)
        {
            var stackTrace = Environment.StackTrace;
            if (stackTrace.Contains("UnitsProximityController.TickOnUnit") ||
                stackTrace.Contains("Cutscenes.Commands.CommandBark"))
                return false;
        }

        return true;
    }

    public static void DoBark(Entity entity, string text, string voiceOver)
    {
        if (!string.IsNullOrWhiteSpace(voiceOver))
            return;

        SpeakBark(text, entity);
    }

    public static void SpeakBark(string text, Entity entity)
    {
        AbstractUnitEntity unitEntity = entity as LightweightUnitEntity ?? entity as AbstractUnitEntity;
        if (unitEntity == null)
        {
            SpeakBark(text);
            return;
        }

        var guid = unitEntity.Blueprint?.AssetGuid;
        if (!string.IsNullOrEmpty(guid))
        {
            Main.Speech?.SpeakAsCharacter(text, guid, VoiceTypeFor(unitEntity.Gender));
            return;
        }
        SpeakBark(text, unitEntity.Gender);
    }

    private static VoiceType VoiceTypeFor(Gender? gender) => gender switch
    {
        Gender.Male => VoiceType.Male,
        Gender.Female => VoiceType.Female,
        _ => VoiceType.Narrator,
    };

    public static void SpeakBark(string text, Gender? gender = null)
    {
#if DEBUG
        Debug.LogFormat("SpeakBark as {0}", gender.HasValue ? gender : "Narrator");
#endif
        Main.Speech?.SpeakAs(text, VoiceTypeFor(gender));
    }
}
