using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using NeuralSpeechMod.Configuration;

namespace NeuralSpeechMod.Voice;

/// <summary>
/// Maps a companion's blueprint AssetGuid to the speaker name used in the TTS sidecar's prompt
/// bank (data/voices/prompts/prompts.json). Keyed by AssetGuid rather than CharacterName because
/// CharacterName is a localized string - it would break per-character routing the moment anyone
/// plays in a non-enGB locale, even though only enGB voice work has been done so far.
///
/// Generated offline from data/raw/script.json (DialogueExporter's blueprint dump) by
/// cross-referencing each unit's character_name against the known prompt-bank speakers; see the
/// generation snippet referenced from PROJECT_PLAN.md. Ships as a flat file next to the mod DLL,
/// same pattern as Localization/enGB.json.
/// </summary>
internal static class SpeakerMap
{
    private static Dictionary<string, string> s_Map;

    private static Dictionary<string, string> Map
    {
        get
        {
            if (s_Map != null)
                return s_Map;
            s_Map = new Dictionary<string, string>();
            try
            {
                var path = Path.Combine(ModConfigurationManager.Instance?.ModEntry?.Path!, "Voice/speaker_map.json");
                if (File.Exists(path))
                    s_Map = JsonConvert.DeserializeObject<Dictionary<string, string>>(File.ReadAllText(path)) ?? s_Map;
                else
                    Main.Logger?.Warning($"speaker_map.json not found at {path}; per-character voices disabled.");
            }
            catch (System.Exception e)
            {
                Main.Logger?.Warning($"Failed to load speaker_map.json: {e.Message}");
            }
            return s_Map;
        }
    }

    /// <summary>Returns the sidecar speaker name for a blueprint AssetGuid, or null if unmapped.</summary>
    public static string Resolve(string blueprintGuid)
    {
        if (string.IsNullOrEmpty(blueprintGuid))
            return null;
        return Map.TryGetValue(blueprintGuid, out var name) ? name : null;
    }

    /// <summary>Diagnostics only (Main's speech_test.request self-test): one known (guid, name)
    /// pair, so the self-test can exercise SpeakAsCharacter without a live dialog to read
    /// CurrentSpeaker from.</summary>
    public static (string guid, string name)? AnyKnownEntry()
    {
        foreach (var kv in Map)
            return (kv.Key, kv.Value);
        return null;
    }
}
