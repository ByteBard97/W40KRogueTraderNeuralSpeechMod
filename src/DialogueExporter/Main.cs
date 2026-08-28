using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Kingmaker.Blueprints;
using UnityEngine;
using UnityModManagerNet;

namespace DialogueExporter;

/// <summary>
/// UMM entry point. Waits until the game's blueprint cache has opened blueprints-pack.bbp, then runs
/// <see cref="Exporter"/> once on a background thread. Output goes to &lt;mod dir&gt;/export/.
///
/// Control files in the mod directory:
///   export.request  - if present, export runs even when script.json already exists; if its content
///                     contains "quit", the game exits after the export finishes (for unattended runs).
/// </summary>
public static class Main
{
    public static UnityModManager.ModEntry.ModLogger Logger;
    public static bool Enabled = true;
    public static string ModDir;

    private static int s_State; // 0 = waiting, 1 = running, 2 = done
    private static float s_WaitSeconds;
    private static string s_Status = "waiting for blueprint cache";

    private static bool Load(UnityModManager.ModEntry modEntry)
    {
        Logger = modEntry.Logger;
        ModDir = modEntry.Path;
        modEntry.OnToggle = (_, value) => { Enabled = value; return true; };
        modEntry.OnUpdate = OnUpdate;
        modEntry.OnGUI = OnGui;
        UnityMainThread.Ensure();
        Log("DialogueExporter loaded.");
        return true;
    }

    private static void OnGui(UnityModManager.ModEntry modEntry)
    {
        GUILayout.Label($"Status: {s_Status}");
        if (s_State != 1 && GUILayout.Button("Export now", GUILayout.Width(150)))
            StartExport(quitAfter: false);
    }

    private static void OnUpdate(UnityModManager.ModEntry modEntry, float dt)
    {
        if (!Enabled || s_State != 0)
            return;

        if (ResourcesLibrary.BlueprintsCache?.m_PackFile == null)
            return;

        // Give the game a few seconds after the cache opens so we don't compete with startup loading.
        s_WaitSeconds += dt;
        if (s_WaitSeconds < 5f)
            return;

        var requestFile = Path.Combine(ModDir, "export.request");
        var outputFile = Path.Combine(ModDir, "export", "script.json");
        var requested = File.Exists(requestFile);
        if (!requested && File.Exists(outputFile))
        {
            s_State = 2;
            s_Status = "script.json already exists; create export.request to re-export";
            Log(s_Status);
            return;
        }

        var quit = requested && File.ReadAllText(requestFile).IndexOf("quit", StringComparison.OrdinalIgnoreCase) >= 0;
        StartExport(quit);
    }

    private static void StartExport(bool quitAfter)
    {
        if (Interlocked.CompareExchange(ref s_State, 1, s_State) == 1)
            return;
        s_State = 1;
        s_Status = "exporting...";
        var outDir = Path.Combine(ModDir, "export");
        Directory.CreateDirectory(outDir);

        Task.Run(() =>
        {
            try
            {
                var exporter = new Exporter(outDir, status => s_Status = status);
                exporter.Run();
                s_Status = $"done: {exporter.Summary}";
                Log(s_Status);
                var requestFile = Path.Combine(ModDir, "export.request");
                if (File.Exists(requestFile))
                    File.Delete(requestFile);
            }
            catch (Exception ex)
            {
                s_Status = "FAILED: " + ex.Message;
                Log(s_Status);
                Log(ex.ToString());
            }
            finally
            {
                s_State = 2;
                if (quitAfter)
                    UnityMainThread.Run(() => { Log("Quitting game after export."); Application.Quit(); });
            }
        });
    }

    public static void Log(string message)
    {
        Logger?.Log(message);
        Debug.Log("[DialogueExporter] " + message);
    }
}

/// <summary>Minimal main-thread dispatcher (Application.Quit must run on the Unity thread).</summary>
internal class UnityMainThread : MonoBehaviour
{
    private static UnityMainThread s_Instance;
    private static readonly System.Collections.Generic.Queue<Action> s_Queue = new();

    public static void Run(Action action)
    {
        lock (s_Queue) s_Queue.Enqueue(action);
    }

    public static void Ensure()
    {
        if (s_Instance != null) return;
        var go = new GameObject("DialogueExporter.MainThread");
        DontDestroyOnLoad(go);
        s_Instance = go.AddComponent<UnityMainThread>();
    }

    private void Update()
    {
        lock (s_Queue)
        {
            while (s_Queue.Count > 0)
                s_Queue.Dequeue()();
        }
    }
}
