using System.Text.RegularExpressions;

namespace NeuralSpeechMod.Voice;

/// <summary>
/// Basic text cleanup before a line is sent to the sidecar. Pronunciation substitution is NOT
/// done here - it lives once, server-side, in data/lexicon/lexicon.json (see
/// src/TtsSidecar/lexicon.py), so the C# mod and any future backend share one lexicon instead of
/// each carrying their own copy. Unlike the upstream SAPI version, this does not lowercase text:
/// neural TTS models are trained on natural casing and it doesn't help pronunciation here.
/// </summary>
public static class PhoneticDictionary
{
    private static readonly Regex DatePattern = new(@"([0-9]{2})\/([0-9]{2})\/([0-9]{4})");

    public static string PrepareText(this string text)
    {
        text = text.Replace("\"", "");
        text = text.Replace("\r\n", ". ");
        text = text.Replace("\n", ". ");
        text = text.Replace("\r", ". ");
        text = text.Trim();
        return DatePattern.Replace(text, "$1 / $2 / $3");
    }
}
