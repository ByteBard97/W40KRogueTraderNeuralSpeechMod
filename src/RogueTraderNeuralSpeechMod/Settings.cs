using UnityModManagerNet;

namespace NeuralSpeechMod;

public class Settings : UnityModManager.ModSettings
{
    public bool LogVoicedLines = false;

    // Which of the 4 fixed sidecar voice slots (narrator/GenericFemale/GenericMale/Protagonist,
    // see Voice/NeuralSpeech.cs) SpeakDialog routes to. Unlike upstream there is no per-voice
    // rate/pitch/volume or an installed-voice picker: the sidecar owns those knobs via
    // per-line annotation (data/lexicon, data/annotations), not user sliders.
    public bool UseGenderSpecificVoices = true;
    public bool UseProtagonistSpecificVoice = true;

    public bool AutoPlay = false;
    public bool AutoPlayIgnoreVoice = false;

    public bool ColorOnHover = false;
    public float HoverColorR = 0f;
    public float HoverColorG = 0f;
    public float HoverColorB = 0f;
    public float HoverColorA = 1f;

    public bool FontStyleOnHover = true;
    public bool[] FontStyles = [false, false, false, true, false, false, false, false, false, false, false];

    public bool InterruptPlaybackOnPlay = true;
    public bool PlaybackBarks = true;
    public bool PlaybackBarkOnlyIfSilence = true;
    public bool PlaybackBarksInVicinity = false;
    public bool ShowNotificationOnPlaybackStop = true;

    public bool ShowPlaybackOfDialogAnswers = true;
    public bool SayDialogAnswerNumber = false;
    public bool DialogAnswerColorOnHover = true;
    public float DialogAnswerHoverColorR = 0.15f;
    public float DialogAnswerHoverColorG = 0.75f;
    public float DialogAnswerHoverColorB = 0.75f;

    public bool AutoStopPlaybackOnLoading = false;

    public override void Save(UnityModManager.ModEntry modEntry)
    {
        Save(this, modEntry);
    }
}
