using UnityEngine;
using UnityModManager = UnityModManagerNet.UnityModManager;

namespace AtlasUpscale;

public class Settings : UnityModManager.ModSettings
{
    /// <summary>Linear size multiplier for the character atlas and its source textures. 1 disables the mod.</summary>
    public int Factor = 2;

    /// <summary>Log every texture the mod replaces.</summary>
    public bool VerboseLog = false;

    /// <summary>Watch the Textures folder and rebuild characters when a PNG changes.</summary>
    public bool AutoReload = true;

    /// <summary>Key that switches to the next texture set. Hold Shift for the previous one.</summary>
    public KeyCode HotKey = KeyCode.F8;

    /// <summary>Keep the texture set name on screen instead of only after a switch.</summary>
    public bool AlwaysShowLabel = false;

    /// <summary>Name of the texture set in use, remembered between sessions.</summary>
    public string Variant = "";

    /// <summary>Label font size in points.</summary>
    public int LabelFontSize = 52;

    /// <summary>Label vertical position as a fraction of the screen height, 0 at the top.</summary>
    public float LabelY = 0.82f;

    /// <summary>Multiplier on how far the character viewer camera can zoom in. 1 keeps the game's own limit.</summary>
    public float ZoomRange = 2.5f;

    /// <summary>Scale on the mouse wheel zoom sensitivity. Smaller means finer steps.</summary>
    public float ZoomStep = 0.3f;

    /// <summary>How far one arrow key press pans the view, as a fraction of the camera distance.</summary>
    public float PanStep = 0.04f;

    /// <summary>Key that saves the finished character atlas to the mod's Dump folder (debug).</summary>
    public KeyCode DumpKey = KeyCode.F9;

    /// <summary>Only atlases containing a texture whose name contains this text are dumped.</summary>
    public string DumpFilter = "Idira";

    /// <summary>Most atlases saved per key press.</summary>
    public int MaxDumps = 3;

    /// <summary>Run the local command bridge (HTTP on 127.0.0.1) so a tool can screenshot and drive the game.</summary>
    public bool BridgeEnabled = true;

    /// <summary>Port of the command bridge. Localhost only.</summary>
    public int BridgePort = 8951;

    public override void Save(UnityModManager.ModEntry modEntry) => Save(this, modEntry);
}
