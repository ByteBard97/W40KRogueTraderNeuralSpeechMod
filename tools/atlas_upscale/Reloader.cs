using System.Collections;
using HarmonyLib;
using Kingmaker.Visual.CharacterSystem;
using UnityEngine;

namespace AtlasUpscale;

/// <summary>Makes live characters repaint and re-merge their atlas after a texture file changed.</summary>
public static class Reloader
{
    private const string PaintedTexturesField = "m_EquipmentEntitiesTextures";
    private const string PaintIndicesField = "m_PaintIndices";
    private const string TexturesMapField = "m_TexturesMap";
    private const string OverlaysMergedName = "OverlaysMerged";

    public static void Apply()
    {
        int count = 0;
        foreach (var character in Object.FindObjectsOfType<Character>())
        {
            ClearPaintCache(character);
            SetOverlaysMerged(character, false);
            count++;
        }
        Main.Log.Log($"queued atlas rebuild for {count} characters");
    }

    /// <summary>False while any live character still has to re-merge its atlas.</summary>
    public static bool AllMerged()
    {
        foreach (var character in Object.FindObjectsOfType<Character>())
        {
            var traverse = Traverse.Create(character);
            object value = traverse.Field(OverlaysMergedName).FieldExists()
                ? traverse.Field(OverlaysMergedName).GetValue()
                : traverse.Property(OverlaysMergedName).GetValue();
            if (value is bool merged && !merged)
                return false;
        }
        return true;
    }

    private static void ClearPaintCache(Character character)
    {
        var painted = AccessTools.Field(typeof(Character), PaintedTexturesField)?.GetValue(character);
        if (painted == null)
            return;
        (AccessTools.Field(painted.GetType(), PaintIndicesField)?.GetValue(painted) as IDictionary)?.Clear();
        var map = AccessTools.Field(painted.GetType(), TexturesMapField)?.GetValue(painted) as IDictionary;
        if (map == null)
            return;
        foreach (var texture in map.Values)
            (texture as RenderTexture)?.Release();
        map.Clear();
    }

    private static void SetOverlaysMerged(Character character, bool value)
    {
        var traverse = Traverse.Create(character);
        if (traverse.Field(OverlaysMergedName).FieldExists())
            traverse.Field(OverlaysMergedName).SetValue(value);
        else
            traverse.Property(OverlaysMergedName).SetValue(value);
    }
}
