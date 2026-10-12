import json

from prerendered import load_index, lookup


def make_export(root, speaker, entries, write_wavs=True):
    ex = root / speaker / "export"
    (ex / "wav").mkdir(parents=True)
    for g, e in entries.items():
        if write_wavs:
            (ex / e["wav"]).write_bytes(b"RIFF")
    (ex / "index.json").write_text(json.dumps(entries))


def test_lookup_serves_matching_text_only(tmp_path):
    make_export(tmp_path, "Abelard", {"g1": {"wav": "wav/g1.wav", "text": "Hello  there", "emotion": "warm",
                                              "voice_score": 1.0, "flags": []}})
    idx = load_index(tmp_path)
    assert lookup(idx, "g1", "Hello there").name == "g1.wav"      # whitespace-insensitive
    assert lookup(idx, "g1", "Hello there!") is None             # edited line -> live synthesis
    assert lookup(idx, "other", "Hello there") is None
    assert lookup(idx, None, "Hello there") is None
    assert idx["g1"]["speaker"] == "Abelard"


def test_missing_wav_and_bad_index_are_skipped(tmp_path):
    make_export(tmp_path, "A", {"g1": {"wav": "wav/g1.wav", "text": "x"}}, write_wavs=False)
    (tmp_path / "B" / "export").mkdir(parents=True)
    (tmp_path / "B/export/index.json").write_text("{not json")
    assert load_index(tmp_path) == {}
    assert load_index(tmp_path / "nonexistent") == {}


def test_fx_export_overrides_raw_render_and_winners_override_both(tmp_path):
    for sub, wav in (("export", "raw"), ("export_fx", "fx")):
        d = tmp_path / "render" / sub / "wav"
        d.mkdir(parents=True)
        (d / "g1.wav").write_bytes(wav.encode())
        (tmp_path / "render" / sub / "index.json").write_text(
            json.dumps({"g1": {"wav": "wav/g1.wav", "text": "x", "match": "guid", "speaker": "Muaran"}}))
    idx = load_index(tmp_path / "bon", tmp_path / "render")
    assert idx["g1"]["wav"].read_bytes() == b"fx"
    make_export(tmp_path / "bon", "Abelard", {"g1": {"wav": "wav/g1.wav", "text": "x"}})
    assert load_index(tmp_path / "bon", tmp_path / "render")["g1"]["wav"].read_bytes() == b"RIFF"
