import json
import math
import struct
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio_server.config import Config  # noqa: E402


def write_wav(path: Path, seconds: float = 0.1, sr: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i / 10))) for i in range(int(sr * seconds))))


def put(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def make_repo(root: Path) -> Config:
    """A tiny fake repo: real speaker Pasqal (2 catalog clips, 1 curated), designed speaker Muaran (2 candidates)."""
    d = root / "data"
    for n in ("E1", "E2"):
        write_wav(d / f"voices/wav/Pasqal/{n}.wav")
    put(d / "voices/catalog.json", {
        "E1": {"event": "E1", "speaker": "Pasqal", "wav": "wav/Pasqal/E1.wav", "duration": 5.0,
               "texts": [{"guid": "g1", "text": "Hello."}]},
        "E2": {"event": "E2", "speaker": "Pasqal", "wav": "wav/Pasqal/E2.wav", "duration": 3.0,
               "texts": [{"guid": "g2", "text": "Bye."}]}})
    put(d / "voices/prompts/prompts.json", {"Pasqal": [{"rank": 1, "event": "E1", "wav": "prompts/Pasqal/01.wav",
                                                        "text": "Hello.", "noise_db": -60.0}]})
    jobs = [
        {"guid": "g1", "speaker": "Pasqal", "text": "Greetings, Rogue Trader.", "voice_source": "prompt_bank",
         "annotation": {"emotion": "neutral", "intensity": 0.25, "pace": "normal", "instruct": "formal"}},
        {"guid": "g2", "speaker": "Pasqal", "text": "Farewell.", "voice_source": "prompt_bank",
         "annotation": {"emotion": "sad", "intensity": 0.5, "pace": "slow", "instruct": None}},
        {"guid": "g3", "speaker": "Muaran", "text": "Welcome aboard.", "voice_source": "fallback", "annotation": {}},
        {"guid": "g4", "speaker": "narrator", "text": "You see a door.", "voice_source": "narrator", "annotation": {}},
    ]
    (d / "render").mkdir(parents=True, exist_ok=True)
    (d / "render/jobs.jsonl").write_text("\n".join(json.dumps(j) for j in jobs) + "\n", encoding="utf-8")
    write_wav(d / "render/export/wav/g1.wav")
    put(d / "render/export/index.json", {"g1": {"wav": "wav/g1.wav"}})
    for c in ("c0.wav", "c1.wav"):
        write_wav(d / f"voice_design/clips/muaran/{c}")
    put(d / "voice_design/design_manifest.json", {"Muaran": {
        "slug": "muaran", "gender": "Female", "role": "officer", "description": "A calm woman.",
        "text": "The augurs report nothing unusual.", "engine": "vox", "candidates": ["c0.wav", "c1.wav"]}})
    put(d / "voice_design/scores.json", {"clips/muaran/c0.wav": {"p_us": 0.2, "top": "england", "p_top": 0.7}})
    put(d / "voice_design/audit.json", {})
    put(root / "tools/fx_lab/scenarios.json", {"scenarios": [{"name": "Clean", "params": {}}]})
    return Config(root=root)


@pytest.fixture
def cfg(tmp_path) -> Config:
    return make_repo(tmp_path)


def make_pool_repo(root: Path) -> Config:
    """make_repo plus unnamed lines, a harness roster, known speakers and a Heinrix prompt bank.

    Unnamed (default_speaker, priority 3) guids: u1,u2 Heinrix (has a bank); u3 Tervantias (no bank); u4 narrator;
    u5-u9 male human; u10-u12 female human; u13,u14 gender unknown (queued); u15 has no roster entry (queued).
    """
    cfg = make_repo(root)
    d = root / "data"
    extra = []
    for i in range(1, 16):
        extra.append({"guid": f"u{i}", "speaker": "default_speaker", "speaker_kind": "default_speaker",
                      "text": f"Unnamed line {i}.", "annotation": None, "priority": 3, "voice_source": "fallback"})
    with open(d / "render/jobs.jsonl", "a", encoding="utf-8") as f:
        for j in extra:
            f.write(json.dumps(j) + "\n")

    def ent(rid, name=None, gender="male", species="human", age="unknown"):
        return {"id": rid, "name": name, "label": rid.title(), "gender": gender, "species": species, "age": age,
                "conf": {"gender": 0.95, "species": 0.95, "age": 0.9}, "evidence": [f"{rid} said something"]}

    def ln(n, key, speaker, conf=1.0, fx=None):
        return {"n": n, "key": key, "speaker": speaker, "conf": {"speaker": conf}, **({"fx": fx} if fx else {})}

    roster = [
        {"conversation": "C1", "roster": [ent("a", "Heinrix"), ent("b", "Tervantias")],
         "lines": [ln(0, "u1", "a"), ln(1, "u2", "a"), ln(2, "u3", "b"), ln(3, "u4", "NARRATOR")]},
        {"conversation": " C2", "roster": [ent("m"), ent("f", gender="female"), ent("q", gender="unknown")],
         "lines": ([ln(0, "u5", "m", fx=["machine"]), ln(1, "u6", "m", fx=["vox_channel", "helmet"]), ln(2, "u7", "m"),
                   ln(3, "u8", "m"), ln(4, "u9", "m")] + [ln(5, "u10", "f", fx=["machine", "machine"]), ln(6, "u11", "f"), ln(7, "u12", "f", fx=["ethereal"])]
                   + [ln(8, "u13", "q"), ln(9, "u14", "q"), ln(10, "u15", "ghost")])},
    ]
    put(d / "npc_profile/roster_35b_all.json", roster)
    put(d / "fx_lab/presets.json", {"Mine": {"dsp": "chain.dsp", "params": {}, "notes": "my preset"}})
    unit = lambda name: {"speaker": {"kind": "unit", "name": name, "gender": "Male"}}
    put(d / "conversations.enGB.json", [{"lines": [unit("Heinrix")] * 5 + [unit("Tervantias the Archmachinator")] * 5}])
    prompts = json.loads((d / "voices/prompts/prompts.json").read_text(encoding="utf-8"))
    prompts["Heinrix"] = []
    put(d / "voices/prompts/prompts.json", prompts)
    return cfg


@pytest.fixture
def pcfg(tmp_path) -> Config:
    return make_pool_repo(tmp_path)
