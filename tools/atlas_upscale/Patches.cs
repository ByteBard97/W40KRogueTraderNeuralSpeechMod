using System.Collections.Generic;
using HarmonyLib;
using Kingmaker.UI.DollRoom;
using Kingmaker.Visual.CharacterSystem;
using UnityEngine;

namespace AtlasUpscale;

[HarmonyPatch(typeof(Character), "GetAtlas")]
internal static class Character_GetAtlas_Patch
{
    private static readonly Dictionary<CharacterAtlasData, CharacterAtlasData> s_Scaled = new();
    private static readonly HashSet<CharacterAtlasData> s_Produced = new();

    private static void Prefix(Character __instance, ref int atlasSize)
    {
        int factor = Main.Settings.Factor;
        if (factor <= 1 || __instance.AtlasData == null)
            return;
        __instance.AtlasData = ScaledData(__instance.AtlasData, factor);
        atlasSize *= factor;
    }

    private static CharacterAtlasData ScaledData(CharacterAtlasData original, int factor)
    {
        if (s_Produced.Contains(original))
            return original;
        if (s_Scaled.TryGetValue(original, out var cached) && cached != null)
            return cached;

        var clone = Object.Instantiate(original);
        clone.name = original.name + "_x" + factor;
        int target = (int)original.targetResolution * factor;
        clone.targetResolution = (CharacterAtlasData.m_AtlasResolution)target;
        foreach (var part in clone.BodyPartsCoords)
        {
            var rect = part.textureRectCoords;
            part.textureRectCoords = new RectInt(rect.x * factor, rect.y * factor, rect.width * factor, rect.height * factor);
            var scaled = part.textureRectCoords;
            part.gpuCoords = new CharacterAtlasData.BodyPartCoords.GpuCoords(
                scaled.x, target - scaled.y - scaled.height, scaled.x + scaled.width, target - scaled.y);
        }
        s_Scaled[original] = clone;
        s_Produced.Add(clone);
        Main.Log.Log($"atlas data {original.name}: {(int)original.targetResolution} -> {target}");
        return clone;
    }
}

[HarmonyPatch(typeof(EquipmentEntity), nameof(EquipmentEntity.RepaintTextures), typeof(EquipmentEntity.PaintedTextures), typeof(int), typeof(int))]
internal static class EquipmentEntity_RepaintTextures_Patch
{
    private static void Prefix(EquipmentEntity __instance)
    {
        if (Main.Settings.Factor <= 1)
            return;
        foreach (var bodyPart in __instance.BodyParts)
        {
            if (bodyPart.Textures == null)
                continue;
            foreach (var description in bodyPart.Textures)
                ScaleDescription(description);
        }
    }

    private static void ScaleDescription(CharacterTextureDescription description)
    {
        if (description == null)
            return;
        description.ActiveTexture = TextureScaler.Scale(description.ActiveTexture);
        description.DiffuseTexture = TextureScaler.Scale(description.DiffuseTexture);
        description.NormalTexture = TextureScaler.Scale(description.NormalTexture);
        description.MaskTexture = TextureScaler.Scale(description.MaskTexture);
    }
}

/// <summary>Widens the character viewer camera's zoom-in limit so fine texture detail can be inspected.</summary>
[HarmonyPatch(typeof(DollCamera), "Start")]
internal static class DollCamera_Start_Patch
{
    private const string MinZoomField = "m_MinZoom";
    private const string MaxZoomField = "m_MaxZoom";
    private const string SensitivityField = "m_SensitivityZoom";

    private static readonly HashSet<DollCamera> s_Done = new();

    private static void Postfix(DollCamera __instance)
    {
        if (!s_Done.Add(__instance))
            return;
        var minField = AccessTools.Field(typeof(DollCamera), MinZoomField);
        var maxField = AccessTools.Field(typeof(DollCamera), MaxZoomField);
        float min = (float)minField.GetValue(__instance);
        float max = (float)maxField.GetValue(__instance);
        float range = Main.Settings.ZoomRange;
        var sensitivityField = AccessTools.Field(typeof(DollCamera), SensitivityField);
        float sensitivity = (float)sensitivityField.GetValue(__instance);
        Main.Log.Log($"viewer camera zoom limits {min:0.###}..{max:0.###}, range x{range:0.##}, wheel sensitivity {sensitivity:0.####} x{Main.Settings.ZoomStep:0.##}");
        sensitivityField.SetValue(__instance, sensitivity * Main.Settings.ZoomStep);
        if (range <= 1f)
            return;
        // Negative values move the camera toward the target: those are the zoom-in side.
        if (min < 0f)
            minField.SetValue(__instance, min * range);
        if (max < 0f)
            maxField.SetValue(__instance, max * range);
    }
}

/// <summary>Keeps a pan offset on the character viewer camera. Offsets are in units of the camera distance.</summary>
public static class ViewerPan
{
    private const string TargetField = "m_CharacterTargetTransform";

    public static Vector2 Offset;

    private const int LoggedNudges = 5;
    private static int s_Logged;

    public static void Nudge(float dx, float dy)
    {
        Offset += new Vector2(dx, dy) * Main.Settings.PanStep;
        if (s_Logged++ < LoggedNudges)
            Main.Log.Log($"pan key received, offset now {Offset.x:0.###},{Offset.y:0.###}");
    }

    public static void Reset() => Offset = Vector2.zero;

    public static void Apply(DollCamera camera)
    {
        if (Offset == Vector2.zero)
            return;
        var target = AccessTools.Field(typeof(DollCamera), TargetField)?.GetValue(camera) as Transform;
        var cameraTransform = camera.transform;
        float distance = target != null ? Vector3.Distance(cameraTransform.position, target.position) : 1f;
        cameraTransform.position += (cameraTransform.right * Offset.x + cameraTransform.up * Offset.y) * distance;
    }
}

[HarmonyPatch(typeof(DollCamera), "DirtyZoom")]
internal static class DollCamera_DirtyZoom_Patch
{
    private static void Postfix(DollCamera __instance) => ViewerPan.Apply(__instance);
}

[HarmonyPatch(typeof(DollCamera), nameof(DollCamera.LookAt))]
internal static class DollCamera_LookAt_Patch
{
    private static void Postfix() => ViewerPan.Reset();
}
