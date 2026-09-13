import json

from diff_cache_vs_production import merge_cache_dirs


def _write_cache_file(path, text_key, emotion):
    path.write_text(json.dumps({
        "conv": "c", "model": "test",
        "lines": [{"guid": text_key, "emotion": emotion, "intensity": 0.5,
                   "pace": "normal", "nonverbal": [], "instruct": "x", "text_hash": "abc123"}],
    }), encoding="utf-8")


def test_merge_cache_dirs_is_reexported_and_later_dir_wins(tmp_path):
    # diff_cache_vs_production.py imports merge_cache_dirs from annotate rather than
    # defining its own - this just confirms the import/re-export actually works and
    # behaves identically to Task 2 Step 1's tests on the original.
    d1, d2 = tmp_path / "cache1", tmp_path / "cache2"
    d1.mkdir()
    d2.mkdir()
    _write_cache_file(d1 / "conv1.json", "key1", "neutral")
    _write_cache_file(d2 / "conv1.json", "key1", "angry")
    merged, _ = merge_cache_dirs([d1, d2])
    assert merged["key1"]["emotion"] == "angry"
