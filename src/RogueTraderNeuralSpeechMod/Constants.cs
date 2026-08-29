using System;
using System.IO;

namespace NeuralSpeechMod;

public static class Constants
{
    public const string NEURAL_VOICE_NAME = "NeuralVoice";
    public const string SETTINGS_PREFIX = "bytebard97.neuralspeechmod";
    public const string NARRATOR_COLOR_CODE = "3c2d0a";

    public static readonly string LOCAL_LOW_PATH = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData)) + "Low";
}
