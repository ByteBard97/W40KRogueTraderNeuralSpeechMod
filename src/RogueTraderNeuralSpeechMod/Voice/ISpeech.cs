namespace NeuralSpeechMod.Voice;

public interface ISpeech
{
    string GetStatusMessage();
    string[] GetAvailableVoices();
    bool IsSpeaking();
    void SpeakPreview(string text, VoiceType voiceType);
    void SpeakDialog(string text, float delay = 0f);
    void SpeakAs(string text, VoiceType type, float delay = 0f, string cueGuid = null);

    /// <summary>
    /// Speak as the specific character identified by their blueprint AssetGuid, using their own
    /// cloned voice from the prompt bank if one is known; falls back to fallbackVoice otherwise
    /// (e.g. a generic mook with no dedicated voice). cueGuid, when known, looks up an
    /// emotion/pace/instruct annotation for this exact line.
    /// </summary>
    void SpeakAsCharacter(string text, string blueprintGuid, VoiceType fallbackVoice, float delay = 0f, string cueGuid = null);

    void Speak(string text, float delay = 0f);
    void Stop();
}