using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Kingmaker.Blueprints;
using Kingmaker.DialogSystem;
using Kingmaker.DialogSystem.Blueprints;
using Kingmaker.Localization;
using Newtonsoft.Json;

namespace DialogueExporter;

/// <summary>
/// Loads every blueprint in blueprints-pack.bbp and writes the dialogue graph to JSON:
///   dialogs  - BlueprintDialog: entry cues, type, narrator flag
///   nodes    - every BlueprintCueBase / BlueprintAnswerBase with text keys and outgoing edges
///   units    - every BlueprintUnit referenced as a speaker/listener/portrait (name, gender, race)
/// Text is exported as both the localization key (stable id) and the current-locale string.
/// Conversation ordering/grouping is left to the offline tooling, which walks the edges.
/// </summary>
public sealed class Exporter
{
    private readonly string m_OutDir;
    private readonly Action<string> m_Status;
    private readonly Dictionary<string, BlueprintUnit> m_Units = new();

    public string Summary { get; private set; } = "";

    public Exporter(string outDir, Action<string> status)
    {
        m_OutDir = outDir;
        m_Status = status;
    }

    public void Run()
    {
        var cache = ResourcesLibrary.BlueprintsCache;
        var guids = cache.m_LoadedBlueprints.Keys.ToList();
        Main.Log($"Blueprint TOC has {guids.Count} entries; loading all (this takes a while)...");

        var dialogs = new List<BlueprintDialog>();
        var nodes = new List<SimpleBlueprint>();
        int loaded = 0, failed = 0;
        foreach (var guid in guids)
        {
            SimpleBlueprint bp;
            try
            {
                bp = cache.Load(guid);
            }
            catch (Exception ex)
            {
                failed++;
                if (failed <= 20) Main.Log($"load failed {guid}: {ex.Message}");
                continue;
            }
            loaded++;
            if (loaded % 10000 == 0)
                m_Status($"loaded {loaded}/{guids.Count} blueprints");

            switch (bp)
            {
                case BlueprintDialog d: dialogs.Add(d); break;
                case BlueprintCueBase c: nodes.Add(c); break;
                case BlueprintAnswerBase a: nodes.Add(a); break;
            }
        }
        Main.Log($"Loaded {loaded} blueprints ({failed} failed): {dialogs.Count} dialogs, {nodes.Count} dialogue nodes.");

        var path = Path.Combine(m_OutDir, "script.json");
        var tmp = path + ".tmp";
        using (var sw = new StreamWriter(tmp, false, new UTF8Encoding(false)))
        using (var w = new JsonTextWriter(sw) { Formatting = Formatting.None })
        {
            w.WriteStartObject();
            Prop(w, "format", "rt-dialogue-export/1");
            Prop(w, "exported_at", DateTime.UtcNow.ToString("o"));
            Prop(w, "locale", LocalizationManager.Instance?.CurrentLocale.ToString());
            Prop(w, "blueprint_count", loaded);

            w.WritePropertyName("dialogs");
            w.WriteStartArray();
            foreach (var d in dialogs) WriteDialog(w, d);
            w.WriteEndArray();

            w.WritePropertyName("nodes");
            w.WriteStartObject();
            foreach (var n in nodes)
            {
                w.WritePropertyName(n.AssetGuid);
                WriteNode(w, n);
            }
            w.WriteEndObject();

            w.WritePropertyName("units");
            w.WriteStartObject();
            foreach (var u in m_Units.Values)
            {
                w.WritePropertyName(u.AssetGuid);
                WriteUnit(w, u);
            }
            w.WriteEndObject();

            w.WriteEndObject();
        }
        if (File.Exists(path)) File.Delete(path);
        File.Move(tmp, path);

        Summary = $"{dialogs.Count} dialogs, {nodes.Count} nodes, {m_Units.Count} units -> {path}";
    }

    // ---- dialogs -------------------------------------------------------------------------------

    private void WriteDialog(JsonTextWriter w, BlueprintDialog d)
    {
        w.WriteStartObject();
        Prop(w, "guid", d.AssetGuid);
        Prop(w, "name", d.name);
        Prop(w, "type", d.Type.ToString());
        Prop(w, "is_narrator_text", d.IsNarratorText);
        Prop(w, "turn_player", d.TurnPlayer);
        WriteText(w, "description", d.Description);
        WriteSelection(w, "first_cue", d.FirstCue);
        Prop(w, "comment", d.Comment);
        w.WriteEndObject();
    }

    // ---- nodes ---------------------------------------------------------------------------------

    private void WriteNode(JsonTextWriter w, SimpleBlueprint bp)
    {
        w.WriteStartObject();
        Prop(w, "guid", bp.AssetGuid);
        Prop(w, "name", bp.name);
        switch (bp)
        {
            case BlueprintCue cue: WriteCue(w, cue); break;
            case BlueprintCheck check: WriteCheck(w, check); break;
            case BlueprintCueSequence seq: WriteSequence(w, seq); break;
            case BlueprintBookPage page: WriteBookPage(w, page); break;
            case BlueprintAnswer answer: WriteAnswer(w, answer); break;
            case BlueprintAnswersList list: WriteAnswersList(w, list); break;
            default: Prop(w, "type", bp.GetType().Name); break;
        }
        if (bp is BlueprintScriptableObject bso)
            Prop(w, "comment", bso.Comment);
        w.WriteEndObject();
    }

    private void WriteCue(JsonTextWriter w, BlueprintCue cue)
    {
        Prop(w, "type", "cue");
        WriteText(w, "text", cue.Text);
        WriteText(w, "description", cue.Description);
        Prop(w, "is_narrator_text", cue.IsNarratorText);
        Prop(w, "animation", cue.Animation.ToString());
        Prop(w, "turn_speaker", cue.TurnSpeaker);
        Prop(w, "show_once", cue.ShowOnce);
        var speaker = cue.Speaker;
        if (speaker != null)
        {
            Prop(w, "speaker_guid", Unit(speaker.Blueprint));
            Prop(w, "speaker_portrait_guid", Unit(speaker.SpeakerPortrait));
            Prop(w, "no_speaker", speaker.NoSpeaker);
        }
        Prop(w, "listener_guid", Unit(cue.Listener));
        WriteRefs(w, "answers", cue.Answers.Select(r => r?.Get()));
        WriteSelection(w, "continue", cue.Continue);
        Prop(w, "soul_mark_shift", cue.SoulMarkShift?.Direction.ToString());
    }

    private void WriteCheck(JsonTextWriter w, BlueprintCheck check)
    {
        Prop(w, "type", "check");
        Prop(w, "stat", check.Type.ToString());
        Prop(w, "difficulty", check.Difficulty.ToString());
        Prop(w, "hidden", check.Hidden);
        Prop(w, "success", check.Success?.AssetGuid);
        Prop(w, "fail", check.Fail?.AssetGuid);
    }

    private void WriteSequence(JsonTextWriter w, BlueprintCueSequence seq)
    {
        Prop(w, "type", "sequence");
        WriteRefs(w, "cues", seq.Cues.Select(r => r?.Get()));
        WriteSelection(w, "exit_continue", seq.Exit?.Continue);
    }

    private void WriteBookPage(JsonTextWriter w, BlueprintBookPage page)
    {
        Prop(w, "type", "book_page");
        WriteRefs(w, "cues", page.Cues.Select(r => r?.Get()));
        WriteRefs(w, "answers", page.Answers.Select(r => r?.Get()));
    }

    private void WriteAnswer(JsonTextWriter w, BlueprintAnswer answer)
    {
        Prop(w, "type", "answer");
        WriteText(w, "text", answer.Text);
        WriteText(w, "description", answer.Description);
        Prop(w, "show_once", answer.ShowOnce);
        if (answer.HasShowCheck)
            Prop(w, "show_check_stat", answer.ShowCheck.Type.ToString());
        WriteSelection(w, "next", answer.NextCue);
        Prop(w, "soul_mark_shift", answer.SoulMarkShift?.Direction.ToString());
    }

    private void WriteAnswersList(JsonTextWriter w, BlueprintAnswersList list)
    {
        Prop(w, "type", "answers_list");
        Prop(w, "show_once", list.ShowOnce);
        WriteRefs(w, "answers", list.Answers.Select(r => r?.Get()));
    }

    // ---- units ---------------------------------------------------------------------------------

    private string Unit(BlueprintUnit unit)
    {
        if (unit == null) return null;
        m_Units[unit.AssetGuid] = unit;
        return unit.AssetGuid;
    }

    private static void WriteUnit(JsonTextWriter w, BlueprintUnit u)
    {
        w.WriteStartObject();
        Prop(w, "guid", u.AssetGuid);
        Prop(w, "name", u.name);
        string charName = null, nameKey = null;
        try
        {
            charName = u.CharacterName;
            nameKey = u.LocalizedName?.String?.Key;
        }
        catch (Exception) { /* some units have no localized name asset */ }
        Prop(w, "character_name", charName);
        Prop(w, "character_name_key", nameKey);
        Prop(w, "gender", u.Gender.ToString());
        Prop(w, "race", u.Race?.name);
        w.WriteEndObject();
    }

    // ---- helpers -------------------------------------------------------------------------------

    private static void WriteText(JsonTextWriter w, string prop, LocalizedString s)
    {
        if (s == null) return;
        var key = s.Key;
        if (string.IsNullOrEmpty(key)) key = s.Shared?.String?.Key;
        if (string.IsNullOrEmpty(key)) return;
        Prop(w, prop + "_key", key);
        string text = null;
        try { text = s.Text; } catch (Exception) { /* missing string */ }
        Prop(w, prop, text);
    }

    private static void WriteSelection(JsonTextWriter w, string prop, CueSelection sel)
    {
        if (sel == null || sel.Cues == null || sel.Cues.Count == 0) return;
        w.WritePropertyName(prop);
        w.WriteStartObject();
        Prop(w, "strategy", sel.Strategy.ToString());
        WriteRefs(w, "cues", sel.Cues.Select(r => r?.Get()));
        w.WriteEndObject();
    }

    private static void WriteRefs(JsonTextWriter w, string prop, IEnumerable<SimpleBlueprint> bps)
    {
        var guids = bps.Where(b => b != null).Select(b => b.AssetGuid).ToList();
        if (guids.Count == 0) return;
        w.WritePropertyName(prop);
        w.WriteStartArray();
        foreach (var g in guids) w.WriteValue(g);
        w.WriteEndArray();
    }

    private static void Prop(JsonTextWriter w, string name, string value)
    {
        if (value == null) return;
        w.WritePropertyName(name);
        w.WriteValue(value);
    }

    private static void Prop(JsonTextWriter w, string name, bool value)
    {
        w.WritePropertyName(name);
        w.WriteValue(value);
    }

    private static void Prop(JsonTextWriter w, string name, int value)
    {
        w.WritePropertyName(name);
        w.WriteValue(value);
    }
}
