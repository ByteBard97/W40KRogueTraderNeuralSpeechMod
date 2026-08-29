using Kingmaker;
using Kingmaker.Blueprints.Base;
using NeuralSpeechMod.Unity;
using System.Text.RegularExpressions;

namespace NeuralSpeechMod.Voice;

/// <summary>
/// ISpeech backend for the local TTS sidecar (src/TtsSidecar). Replaces upstream's
/// platform-gated WindowsSpeech/AppleSpeech (SAPI/`say`) with one HTTP client that works
/// identically on Windows, Linux and macOS - the whole point of the fork.
///
/// v0.1 scope: routes through the same four VoiceType categories the ~25 upstream Harmony
/// patches already call (Narrator/Female/Male/Protagonist), mapped to fixed sidecar speaker
/// names. Per-character voices (Heinrix speaking as Heinrix, not as "generic male") and
/// emotion-annotation lookup are the next increment: they need a new ISpeech entry point that
/// takes a speaker/cue GUID instead of a VoiceType, which the call sites (Dialog_Patch,
/// BarkPlayer_Patch, DialogAnswerBaseView_Patch) already have available from
/// DialogController.CurrentSpeaker / the entity passed to BarkPlayer.Bark.
///
/// Text preparation deliberately does NOT do the upstream mid-line narrator/dialogue voice
/// switch (the <i><color=#NARRATOR_COLOR_CODE>...) - for v0.1 a line plays in one voice; splitting
/// belongs here once per-character routing lands, since only then does "switch voice mid-line"
/// mean something more precise than Narrator-vs-dialog.
/// </summary>
public class NeuralSpeech : ISpeech
{
    private static readonly Regex TagPattern = new(@"<[^>]+>");

    private static string SpeakerFor(VoiceType type) => type switch
    {
        VoiceType.Narrator => "narrator",
        VoiceType.Female => "GenericFemale",
        VoiceType.Male => "GenericMale",
        VoiceType.Protagonist => "Protagonist",
        _ => "narrator",
    };

    public string GetStatusMessage() => NeuralVoiceUnity.GetStatusMessage();

    public string[] GetAvailableVoices() => new[]
    {
        "narrator#Narrator", "GenericFemale#Female", "GenericMale#Male", "Protagonist#Protagonist",
    };

    public bool IsSpeaking() => NeuralVoiceUnity.IsSpeaking;

    public void SpeakPreview(string text, VoiceType voiceType)
    {
        if (string.IsNullOrEmpty(text))
        {
            Main.Logger?.Warning("No text to speak!");
            return;
        }
        text = TagPattern.Replace(text.PrepareText(), "");
        NeuralVoiceUnity.Speak(text, SpeakerFor(voiceType));
    }

    public void SpeakDialog(string text, float delay = 0f)
    {
        if (string.IsNullOrEmpty(text))
        {
            Main.Logger?.Warning("No text to speak!");
            return;
        }
        // Matches upstream: gender-specific routing for dialog lines is gated behind this
        // setting; UseProtagonistSpecificVoice only affects SpeakAs call sites (player answers).
        var cueGuid = Game.Instance?.DialogController?.CurrentCue?.Text?.Key;
        var speaker = Game.Instance?.DialogController?.CurrentSpeaker;
        var guid = speaker?.Blueprint?.AssetGuid;
        if (!string.IsNullOrEmpty(guid) && SpeakerMap.Resolve(guid) != null)
        {
            SpeakAsCharacter(text, guid, VoiceType.Narrator, delay, cueGuid);
            return;
        }

        if (Main.Settings?.UseGenderSpecificVoices != true)
        {
            SpeakAs(text, VoiceType.Narrator, delay, cueGuid);
            return;
        }
        SpeakAs(text, ResolveCurrentSpeakerVoice(), delay, cueGuid);
    }

    public void SpeakAsCharacter(string text, string blueprintGuid, VoiceType fallbackVoice, float delay = 0f, string cueGuid = null)
    {
        if (string.IsNullOrEmpty(text))
        {
            Main.Logger?.Warning("No text to speak!");
            return;
        }
        text = TagPattern.Replace(text.PrepareText(), "");
        var resolved = SpeakerMap.Resolve(blueprintGuid) ?? SpeakerFor(fallbackVoice);
        NeuralVoiceUnity.Speak(text, resolved, delay, cueGuid);
    }

    /// <summary>
    /// Same resolution upstream's WindowsSpeech.CombinedDialogVoiceStart did: no current speaker
    /// (or no gender) -> Narrator; the player character -> Protagonist; otherwise by gender.
    /// </summary>
    private static VoiceType ResolveCurrentSpeakerVoice()
    {
        var speaker = Game.Instance?.DialogController?.CurrentSpeaker;
        if (speaker == null)
            return VoiceType.Narrator;
        if (speaker.IsMainCharacter)
            return VoiceType.Protagonist;
        return speaker.Gender switch
        {
            Gender.Female => VoiceType.Female,
            Gender.Male => VoiceType.Male,
            _ => VoiceType.Narrator,
        };
    }

    public void SpeakAs(string text, VoiceType voiceType, float delay = 0f, string cueGuid = null)
    {
        if (string.IsNullOrEmpty(text))
        {
            Main.Logger?.Warning("No text to speak!");
            return;
        }
        text = TagPattern.Replace(text.PrepareText(), "");
        NeuralVoiceUnity.Speak(text, SpeakerFor(voiceType), delay, cueGuid);
    }

    public void Speak(string text, float delay = 0f)
    {
        SpeakAs(text, VoiceType.Narrator, delay);
    }

    public void Stop() => NeuralVoiceUnity.Stop();
}
