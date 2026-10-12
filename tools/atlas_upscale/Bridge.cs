using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Reflection;
using System.Text;
using System.Threading;
using HarmonyLib;
using Kingmaker.Settings;
using Kingmaker.UI.DollRoom;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace AtlasUpscale;

/// <summary>
/// Local command bridge. An HTTP listener on 127.0.0.1 turns requests like /shot?name=a into commands that run on the
/// Unity main thread, one at a time. Every command returns a JSON object once its effect has actually happened.
/// </summary>
public static class Bridge
{
    private const string Version = "0.1";
    private const string ShotsFolder = "Shots";
    private const string CameraField = "m_Camera";
    private const string DirtyZoomMethod = "DirtyZoom";
    private const int RequestTimeoutMs = 180000;
    private const int RebuildMinFrames = 3;
    private const int RebuildMaxFrames = 90;
    private const int RebuildSettleFrames = 20;
    private const int DumpMinFrames = 10;
    private const int MaxWaitFrames = 3600;
    private const string DefaultShotName = "shot";

    private static readonly ConcurrentQueue<Job> s_Jobs = new();
    private static HttpListener s_Listener;
    private static bool s_Busy;

    private class Job
    {
        public string Command;
        public Dictionary<string, string> Args;
        public string Result;
        public readonly ManualResetEventSlim Done = new(false);
    }

    public static void Start()
    {
        try
        {
            string prefix = $"http://127.0.0.1:{Main.Settings.BridgePort}/";
            s_Listener = new HttpListener();
            s_Listener.Prefixes.Add(prefix);
            s_Listener.Start();
            var host = new GameObject("AtlasUpscaleBridge") { hideFlags = HideFlags.HideAndDontSave };
            UnityEngine.Object.DontDestroyOnLoad(host);
            host.AddComponent<BridgeRunner>();
            var thread = new Thread(Listen) { IsBackground = true, Name = "AtlasUpscaleBridge" };
            thread.Start();
            Main.Log.Log($"bridge listening on {prefix} (version {Version})");
        }
        catch (Exception e)
        {
            Main.Log.Log($"bridge failed to start: {e.GetType().Name} {e.Message}");
        }
    }

    private static void Listen()
    {
        while (s_Listener != null && s_Listener.IsListening)
        {
            try
            {
                var context = s_Listener.GetContext();
                ThreadPool.QueueUserWorkItem(_ => Handle(context));
            }
            catch (Exception)
            {
                return;
            }
        }
    }

    private static void Handle(HttpListenerContext context)
    {
        string body;
        int status = 200;
        try
        {
            var job = new Job
            {
                Command = context.Request.Url.AbsolutePath.Trim('/').ToLowerInvariant(),
                Args = ParseQuery(context.Request.Url.Query)
            };
            s_Jobs.Enqueue(job);
            if (job.Done.Wait(RequestTimeoutMs))
                body = job.Result;
            else
            {
                status = 504;
                body = Fail("timed out waiting for the game");
            }
        }
        catch (Exception e)
        {
            status = 500;
            body = Fail($"{e.GetType().Name} {e.Message}");
        }
        try
        {
            var bytes = Encoding.UTF8.GetBytes(body);
            context.Response.StatusCode = status;
            context.Response.ContentType = "application/json";
            context.Response.OutputStream.Write(bytes, 0, bytes.Length);
            context.Response.Close();
        }
        catch (Exception)
        {
            // client went away
        }
    }

    private static Dictionary<string, string> ParseQuery(string query)
    {
        var args = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pair in query.TrimStart('?').Split(new[] { '&' }, StringSplitOptions.RemoveEmptyEntries))
        {
            int eq = pair.IndexOf('=');
            string key = Uri.UnescapeDataString(eq < 0 ? pair : pair.Substring(0, eq));
            args[key] = eq < 0 ? "" : Uri.UnescapeDataString(pair.Substring(eq + 1).Replace('+', ' '));
        }
        return args;
    }

    // ---- main thread side ----

    internal static void Pump(MonoBehaviour runner)
    {
        if (s_Busy || !s_Jobs.TryDequeue(out var job))
            return;
        s_Busy = true;
        runner.StartCoroutine(Run(job));
    }

    private static IEnumerator Run(Job job)
    {
        var steps = Execute(job);
        while (true)
        {
            bool more;
            try
            {
                more = steps.MoveNext();
            }
            catch (Exception e)
            {
                Main.SuppressLabel = false;
                job.Result = Fail($"{e.GetType().Name} {e.Message}");
                break;
            }
            if (!more)
                break;
            yield return steps.Current;
        }
        job.Result ??= Fail("command produced no result");
        s_Busy = false;
        job.Done.Set();
    }

    private static IEnumerator Execute(Job job)
    {
        switch (job.Command)
        {
            case "ping": job.Result = Ok(("version", Version)); return Empty();
            case "state": job.Result = State(); return Empty();
            case "shot": return Shot(job);
            case "wait": return Wait(job);
            case "texture_set": return TextureSet(job);
            case "dump_atlas": return DumpAtlas(job);
            case "zoom": job.Result = Zoom(job); return Empty();
            case "pan": job.Result = Pan(job); return Empty();
            case "aa": job.Result = Antialiasing(job); return Empty();
            case "timescale": job.Result = TimeScale(job); return Empty();
            case "ui_list": job.Result = UiList(job); return Empty();
            case "ui_click": return UiClick(job);
            default:
                job.Result = Fail($"unknown command '{job.Command}'. Commands: ping state shot wait texture_set dump_atlas zoom pan aa timescale ui_list ui_click");
                return Empty();
        }
    }

    private static IEnumerator Empty()
    {
        yield break;
    }

    private static IEnumerator Wait(Job job)
    {
        int frames = Mathf.Clamp(IntArg(job, "frames", 1), 0, MaxWaitFrames);
        for (int i = 0; i < frames; i++)
            yield return null;
        job.Result = Ok(("frames", frames));
    }

    private static IEnumerator Shot(Job job)
    {
        string name = job.Args.TryGetValue("name", out var n) && n.Length > 0 ? n : DefaultShotName;
        bool label = IntArg(job, "label", 0) != 0;
        bool doll = IntArg(job, "doll", 0) != 0;
        string folder = Path.Combine(Main.ModPath, ShotsFolder);
        Directory.CreateDirectory(folder);
        Main.SuppressLabel = !label;
        yield return null;
        yield return new WaitForEndOfFrame();
        string path;
        if (doll)
        {
            var target = DollCameraComponent()?.targetTexture;
            if (target == null)
            {
                Main.SuppressLabel = false;
                job.Result = Fail("no doll camera render texture (open a character screen first)");
                yield break;
            }
            path = AtlasDump.SaveTo(target, folder, name + "_doll");
        }
        else
        {
            var texture = ScreenCapture.CaptureScreenshotAsTexture();
            path = Path.Combine(folder, $"{name}_{texture.width}x{texture.height}.png");
            File.WriteAllBytes(path, texture.EncodeToPNG());
            UnityEngine.Object.Destroy(texture);
        }
        Main.SuppressLabel = false;
        job.Result = Ok(("path", path), ("set", TextureScaler.CurrentVariantName));
    }

    private static IEnumerator TextureSet(Job job)
    {
        string name = job.Args.TryGetValue("name", out var n) ? n : null;
        if (name == null && !job.Args.ContainsKey("step"))
        {
            job.Result = Ok(("current", TextureScaler.CurrentVariantName), ("sets", string.Join(",", TextureScaler.VariantNames)));
            yield break;
        }
        if (name != null)
        {
            if (!TextureScaler.SelectVariant(name))
            {
                job.Result = Fail($"no texture set '{name}'. Sets: {string.Join(", ", TextureScaler.VariantNames)}");
                yield break;
            }
        }
        else
            TextureScaler.CycleVariant(IntArg(job, "step", 1));
        Main.Settings.Variant = TextureScaler.CurrentVariantName;
        Main.Settings.Save(Main.Entry);
        Reloader.Apply();
        int frames = 0;
        bool timedOut = false;
        yield return WaitUntilRebuilt(() => !Reloader.AllMerged() || frames < RebuildMinFrames, () => frames++, () => timedOut = true, RebuildMaxFrames);
        for (int i = 0; i < RebuildSettleFrames; i++)
            yield return null;
        job.Result = Ok(("set", TextureScaler.CurrentVariantName), ("frames", frames), ("timedOut", timedOut));
    }

    private static IEnumerator DumpAtlas(Job job)
    {
        string folder = Path.Combine(Main.ModPath, "Dump");
        var started = DateTime.UtcNow;
        AtlasDump.Arm();
        Reloader.Apply();
        int frames = 0;
        bool timedOut = false;
        yield return WaitUntilRebuilt(() => !Reloader.AllMerged() || AtlasDump.Pending || frames < DumpMinFrames, () => frames++, () => timedOut = true, RebuildMaxFrames);
        for (int i = 0; i < RebuildSettleFrames; i++)
            yield return null;
        var files = new List<string>();
        if (Directory.Exists(folder))
        {
            foreach (var file in Directory.GetFiles(folder, "*.png"))
            {
                if (File.GetLastWriteTimeUtc(file) >= started.AddSeconds(-1))
                    files.Add(file);
            }
        }
        job.Result = Ok(("files", string.Join("|", files)), ("frames", frames), ("timedOut", timedOut));
    }

    private static IEnumerator WaitUntilRebuilt(Func<bool> keepWaiting, Action tick, Action onTimeout, int maxFrames)
    {
        int waited = 0;
        while (keepWaiting())
        {
            if (++waited > maxFrames)
            {
                onTimeout();
                yield break;
            }
            tick();
            yield return null;
        }
    }

    private static string Zoom(Job job)
    {
        var doll = DollCamera.Current;
        if (doll == null)
            return Fail("no doll camera (open a character screen first)");
        string mode = job.Args.TryGetValue("mode", out var m) ? m.ToLowerInvariant() : "";
        if (job.Args.ContainsKey("value"))
        {
            doll.ZoomNormalized = FloatArg(job, "value", 1f);
            AccessTools.Method(typeof(DollCamera), DirtyZoomMethod)?.Invoke(doll, null);
            return Ok(("zoomNormalized", doll.ZoomNormalized));
        }
        switch (mode)
        {
            case "min": doll.ZoomMin(); break;
            case "max": doll.ZoomMax(); break;
            case "reset": doll.ResetZoom(); break;
            case "": break;
            default: return Fail("zoom mode must be min, max or reset, or pass value=0..1 (0 is the closest limit, which with this mod goes through the character; 1 is the game's default view)");
        }
        return Ok(("zoomNormalized", doll.ZoomNormalized));
    }

    private static string Pan(Job job)
    {
        var doll = DollCamera.Current;
        if (doll == null)
            return Fail("no doll camera (open a character screen first)");
        if (IntArg(job, "reset", 0) != 0)
            ViewerPan.Reset();
        else
            ViewerPan.Offset = new Vector2(FloatArg(job, "x", ViewerPan.Offset.x), FloatArg(job, "y", ViewerPan.Offset.y));
        AccessTools.Method(typeof(DollCamera), DirtyZoomMethod)?.Invoke(doll, null);
        return Ok(("x", ViewerPan.Offset.x), ("y", ViewerPan.Offset.y));
    }

    /// <summary>Changes the game's own anti-aliasing option. The camera helper copies it onto the cameras every frame.</summary>
    private static string Antialiasing(Job job)
    {
        var controller = SettingsController.Instance?.GraphicsSettingsController;
        if (controller == null)
            return Fail("settings controller not ready");
        if (!job.Args.TryGetValue("mode", out var text))
            return Ok(("aa", controller.AntialiasingMode.ToString()), ("quality", controller.AntialiasingQuality.ToString()));
        if (!Enum.TryParse<AntialiasingMode>(text, true, out var mode))
            return Fail("mode must be off, smaa or taa");
        object entity = FindAntialiasingEntity(controller);
        if (entity == null)
            return Fail("could not find the anti-aliasing settings entry");
        var set = entity.GetType().GetMethod("SetTempValue", BindingFlags.Public | BindingFlags.Instance);
        if (set == null)
        {
            var names = new List<string>();
            foreach (var method in entity.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance))
                names.Add(method.Name);
            return Fail("no SetTempValue on the setting; methods: " + string.Join(",", names));
        }
        set.Invoke(entity, new object[] { mode });
        SettingsController.Instance.ConfirmAllTempValues();
        return Ok(("aa", controller.AntialiasingMode.ToString()), ("requested", mode.ToString()));
    }

    private static object FindAntialiasingEntity(object controller)
    {
        foreach (var field in controller.GetType().GetFields(BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance))
        {
            var holder = field.GetValue(controller);
            var entity = holder?.GetType().GetField("AntialiasingMode")?.GetValue(holder);
            if (entity != null)
                return entity;
        }
        return null;
    }

    /// <summary>Freezes or resumes game time (idle animations) so screenshots of one pose can be compared.</summary>
    private static string TimeScale(Job job)
    {
        if (job.Args.ContainsKey("value"))
            Time.timeScale = Mathf.Clamp(FloatArg(job, "value", 1f), 0f, 4f);
        return Ok(("timeScale", Time.timeScale));
    }

    // ---- ui ----

    private const int MaxUiItems = 200;
    private const string TextProperty = "text";

    /// <summary>Anything on screen that reacts to a pointer click: uGUI selectables and the game's own button components.</summary>
    private static List<Component> ActiveSelectables(string filter)
    {
        var result = new List<Component>();
        foreach (var behaviour in UnityEngine.Object.FindObjectsOfType<MonoBehaviour>())
        {
            if (behaviour == null || !behaviour.isActiveAndEnabled || behaviour is not IPointerClickHandler)
                continue;
            if (behaviour is Selectable selectable && !selectable.interactable)
                continue;
            if (filter.Length > 0 && Describe(behaviour).IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0)
                continue;
            result.Add(behaviour);
        }
        return result;
    }

    private static string PathOf(Transform transform)
    {
        var builder = new StringBuilder(transform.name);
        for (var parent = transform.parent; parent != null; parent = parent.parent)
            builder.Insert(0, parent.name + "/");
        return builder.ToString();
    }

    private static string LabelOf(Component selectable)
    {
        var parts = new List<string>();
        foreach (var component in selectable.GetComponentsInChildren<Component>(false))
        {
            if (component == null || component is Transform)
                continue;
            var property = component.GetType().GetProperty(TextProperty, BindingFlags.Public | BindingFlags.Instance);
            if (property?.PropertyType == typeof(string) && property.GetValue(component) is string text && text.Trim().Length > 0)
                parts.Add(text.Trim().Replace('\n', ' '));
        }
        return string.Join(" / ", parts);
    }

    private static string Describe(Component selectable) => PathOf(selectable.transform) + " " + LabelOf(selectable);

    private static string UiList(Job job)
    {
        string filter = job.Args.TryGetValue("filter", out var f) ? f : "";
        var lines = new List<string>();
        var items = ActiveSelectables(filter);
        for (int i = 0; i < items.Count && i < MaxUiItems; i++)
        {
            var rect = items[i].transform as RectTransform;
            string where = "";
            if (rect != null)
            {
                var corners = new Vector3[4];
                rect.GetWorldCorners(corners);
                var center = (corners[0] + corners[2]) / 2f;
                where = $" @{center.x:0},{Screen.height - center.y:0}";
            }
            lines.Add($"{i}: {PathOf(items[i].transform)} [{LabelOf(items[i])}]{where}");
        }
        return Ok(("count", items.Count), ("items", string.Join("\n", lines)));
    }

    private static IEnumerator UiClick(Job job)
    {
        string filter = job.Args.TryGetValue("match", out var f) ? f : "";
        if (filter.Length == 0)
        {
            job.Result = Fail("ui_click needs match=<text or path fragment>; use ui_list to see what is clickable");
            yield break;
        }
        var items = ActiveSelectables(filter);
        var exact = items.FindAll(item => PathOf(item.transform).EndsWith(filter, StringComparison.OrdinalIgnoreCase));
        if (exact.Count == 1)
            items = exact;
        int pick = IntArg(job, "index", -1);
        if (items.Count == 0)
        {
            job.Result = Fail($"nothing clickable matches '{filter}'");
            yield break;
        }
        if (items.Count > 1 && pick < 0)
        {
            var names = new List<string>();
            for (int i = 0; i < items.Count && i < 15; i++)
                names.Add($"{i}: {PathOf(items[i].transform)} [{LabelOf(items[i])}]");
            job.Result = Fail($"{items.Count} matches for '{filter}', pass index=N. " + string.Join("; ", names));
            yield break;
        }
        var target = items[Mathf.Max(pick, 0)];
        var data = new PointerEventData(EventSystem.current) { button = PointerEventData.InputButton.Left, clickCount = 1 };
        ExecuteEvents.Execute(target.gameObject, data, ExecuteEvents.pointerEnterHandler);
        ExecuteEvents.Execute(target.gameObject, data, ExecuteEvents.pointerDownHandler);
        ExecuteEvents.Execute(target.gameObject, data, ExecuteEvents.pointerUpHandler);
        ExecuteEvents.Execute(target.gameObject, data, ExecuteEvents.pointerClickHandler);
        int frames = Mathf.Clamp(IntArg(job, "wait", 10), 0, MaxWaitFrames);
        for (int i = 0; i < frames; i++)
            yield return null;
        job.Result = Ok(("clicked", PathOf(target.transform)), ("label", LabelOf(target)));
    }

    private static string State()
    {
        string dollInfo = "none";
        var doll = DollCamera.Current;
        if (doll != null)
        {
            var target = DollCameraComponent()?.targetTexture;
            dollInfo = $"zoom {doll.ZoomNormalized:0.###}, target {(target != null ? $"{target.width}x{target.height} {target.format}" : "none")}";
        }
        var graphics = SettingsController.Instance?.GraphicsSettingsController;
        return Ok(
            ("version", Version),
            ("textureSet", TextureScaler.CurrentVariantName),
            ("textureSets", string.Join(",", TextureScaler.VariantNames)),
            ("qualityLevel", QualitySettings.names[QualitySettings.GetQualityLevel()]),
            ("mipmapLimit", QualitySettings.globalTextureMipmapLimit),
            ("aa", graphics?.AntialiasingMode.ToString() ?? "n/a"),
            ("aaQuality", graphics?.AntialiasingQuality.ToString() ?? "n/a"),
            ("screen", $"{Screen.width}x{Screen.height}"),
            ("doll", dollInfo),
            ("pan", $"{ViewerPan.Offset.x:0.###},{ViewerPan.Offset.y:0.###}"),
            ("modPath", Main.ModPath));
    }

    private static Camera DollCameraComponent()
    {
        var doll = DollCamera.Current;
        return doll == null ? null : AccessTools.Field(typeof(DollCamera), CameraField)?.GetValue(doll) as Camera;
    }

    // ---- json ----

    private static int IntArg(Job job, string key, int fallback) =>
        job.Args.TryGetValue(key, out var text) && int.TryParse(text, out var value) ? value : fallback;

    private static float FloatArg(Job job, string key, float fallback) =>
        job.Args.TryGetValue(key, out var text) && float.TryParse(text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var value) ? value : fallback;

    private static string Fail(string message) => "{\"ok\":false,\"error\":" + Quote(message) + "}";

    private static string Ok(params (string key, object value)[] fields)
    {
        var builder = new StringBuilder("{\"ok\":true");
        foreach (var (key, value) in fields)
        {
            builder.Append(',').Append(Quote(key)).Append(':');
            switch (value)
            {
                case bool flag: builder.Append(flag ? "true" : "false"); break;
                case int or long: builder.Append(value); break;
                case float number: builder.Append(number.ToString("0.#####", System.Globalization.CultureInfo.InvariantCulture)); break;
                default: builder.Append(Quote(value?.ToString() ?? "")); break;
            }
        }
        return builder.Append('}').ToString();
    }

    private static string Quote(string text)
    {
        var builder = new StringBuilder("\"");
        foreach (char c in text)
        {
            switch (c)
            {
                case '"': builder.Append("\\\""); break;
                case '\\': builder.Append("\\\\"); break;
                case '\n': builder.Append("\\n"); break;
                case '\r': break;
                case '\t': builder.Append("\\t"); break;
                default: builder.Append(c); break;
            }
        }
        return builder.Append('"').ToString();
    }
}

/// <summary>Hidden component that hands queued bridge commands to the main thread each frame.</summary>
internal class BridgeRunner : MonoBehaviour
{
    private void Update() => Bridge.Pump(this);
}
