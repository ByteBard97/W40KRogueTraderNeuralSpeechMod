using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;
using NeuralSpeechMod.Configuration;

namespace NeuralSpeechMod.Voice;

/// <summary>
/// Looks up the emotion/pace/instruct annotation for a dialogue cue by its localization guid
/// (the same guid as DialogController.CurrentCue.Text.Key), from the merged output of
/// tools/annotate (data/annotations/annotations.enGB.json -> Voice/annotations.enGB.json in the
/// shipped mod, same pattern as speaker_map.json).
///
/// Records are passed through as raw JObjects rather than a hand-written C# schema so this
/// doesn't have to be kept in sync with tools/annotate/schema.py by hand - whatever fields the
/// annotation pipeline produces (emotion, intensity, pace, nonverbal, instruct, ...) are exactly
/// what the sidecar's Annotation pydantic model expects, and unknown/extra fields are ignored on
/// both ends.
/// </summary>
internal static class AnnotationStore
{
    private static Dictionary<string, JObject> s_Map;

    private static Dictionary<string, JObject> Map
    {
        get
        {
            if (s_Map != null)
                return s_Map;
            s_Map = new Dictionary<string, JObject>();
            try
            {
                var path = Path.Combine(ModConfigurationManager.Instance?.ModEntry?.Path!, "Voice/annotations.enGB.json");
                if (File.Exists(path))
                {
                    var obj = JObject.Parse(File.ReadAllText(path));
                    foreach (var prop in obj.Properties())
                        s_Map[prop.Name] = (JObject)prop.Value;
                }
                // Not finding the file is expected until the bulk annotation pass is merged and
                // shipped - lines simply play without prosody annotation until then.
            }
            catch (System.Exception e)
            {
                Main.Logger?.Warning($"Failed to load annotations.enGB.json: {e.Message}");
            }
            return s_Map;
        }
    }

    public static JObject Resolve(string cueGuid)
    {
        if (string.IsNullOrEmpty(cueGuid))
            return null;
        return Map.TryGetValue(cueGuid, out var a) ? a : null;
    }
}
