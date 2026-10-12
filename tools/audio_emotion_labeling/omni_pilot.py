"""Pilot 2: forced-choice emotion FAMILY labeling with Qwen2.5-Omni-7B (thinker only, 4-bit).

  HF_HOME=/media/geoff/Elements/hf_cache_omni .venv-omni/bin/python omni_pilot.py single --mode audio
  ... single --mode audio+text
  ... pair --n 20
Outputs go to data/audio_llm_pilot2/. Constrained decoding = argmax over the first-token
logits of the family names after the assistant prefix '{"family": "' (names chosen to have
distinct first tokens, asserted at load). A free-generation pass with strict-JSON parse
and one retry measures the parse-failure rate an unconstrained pipeline would see.
"""
from __future__ import annotations
import argparse, json, re, time, random
from pathlib import Path
import librosa, torch
from families import FAMILIES, FAMILY_OF, DESCRIPTIONS

ROOT = Path(__file__).resolve().parent.parent.parent
VOICES = ROOT / "data/voices"
OUT = ROOT / "data/audio_llm_pilot2"
MODEL_ID = "Qwen/Qwen2.5-Omni-7B"
SYSTEM = ("You are Qwen, a virtual human developed by the Qwen Team, Alibaba Group, capable of "
          "perceiving auditory and visual inputs, as well as generating text and speech.")
PREFIX = '{"family": "'
FAMS = list(FAMILIES)


def load():
    from transformers import (Qwen2_5OmniThinkerForConditionalGeneration, Qwen2_5OmniProcessor,
                               BitsAndBytesConfig)
    proc = Qwen2_5OmniProcessor.from_pretrained(MODEL_ID)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_quant_type="nf4",
                             llm_int8_skip_modules=["audio_tower", "visual", "lm_head"])
    model = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(
        MODEL_ID, quantization_config=bnb, device_map={"": 0}, dtype=torch.bfloat16)
    model.eval()
    tok = proc.tokenizer
    first = {f: tok.encode(f, add_special_tokens=False)[0] for f in FAMS}
    assert len(set(first.values())) == len(FAMS), f"first tokens collide: {first}"
    return model, proc, first


def family_block() -> str:
    return "\n".join(f'- "{f}": {DESCRIPTIONS[f]}' for f in FAMS)


def single_prompt(transcript: str | None) -> str:
    s = ("You hear one line spoken by Abelard, an older, formal ship's seneschal in a sci-fi RPG. "
         "Judge only HOW it is delivered (tone of voice, pace, energy), not what is said.\n")
    if transcript:
        s += f'Transcript of the line: "{transcript}"\n'
    s += ("Choose the single best delivery family:\n" + family_block() +
          '\nAnswer with strict JSON only, exactly: {"family": "<one of the names above>"}')
    return s


def build(proc, audios, text, prefix=""):
    content = [{"type": "audio", "audio": "x"} for _ in audios] + [{"type": "text", "text": text}]
    conv = [{"role": "system", "content": [{"type": "text", "text": SYSTEM}]},
            {"role": "user", "content": content}]
    chat = proc.apply_chat_template(conv, add_generation_prompt=True, tokenize=False) + prefix
    return proc(text=chat, audio=audios, return_tensors="pt", padding=True)


def to_dev(inputs, model):
    return {k: (v.to(model.device, torch.bfloat16) if v.is_floating_point() else v.to(model.device))
            for k, v in inputs.items()}


@torch.no_grad()
def constrained(model, proc, first, audios, text):
    inp = to_dev(build(proc, audios, text, PREFIX), model)
    logits = model(**inp).logits[0, -1].float()
    ids = torch.tensor([first[f] for f in FAMS], device=logits.device)
    lp = torch.log_softmax(logits[ids], -1).cpu().tolist()
    return FAMS[max(range(len(FAMS)), key=lambda i: lp[i])], dict(zip(FAMS, [round(x, 3) for x in lp]))


@torch.no_grad()
def free(model, proc, audios, text, max_new=24):
    inp = to_dev(build(proc, audios, text), model)
    out = model.generate(**inp, max_new_tokens=max_new, do_sample=False)
    return proc.batch_decode(out[:, inp["input_ids"].shape[1]:], skip_special_tokens=True)[0]


def parse(raw: str, options=FAMS):
    m = re.search(r'\{\s*"[a-z_]+"\s*:\s*"([a-zA-Z_ ]+)"\s*\}', raw)
    if m and m.group(1) in options:
        return m.group(1)
    return None


def load_gt():
    cur = json.loads((VOICES / "emotion_banks/curation.json").read_text())["Abelard"]
    cat = json.loads((VOICES / "catalog.json").read_text())
    gt = {}
    for e, r in cur.items():
        if r.get("emotion"):
            texts = cat[e].get("texts") or []
            gt[e] = {"word": r["emotion"], "family": FAMILY_OF[r["emotion"]], "wav": cat[e]["wav"],
                     "text": texts[0]["text"] if texts else None}
    return gt


def audio(wav):
    return librosa.load(str(VOICES / wav), sr=16000, mono=True)[0]


def run_single(args):
    model, proc, first = load()
    gt = load_gt()
    events = list(gt)[: args.limit or None]
    rows = []
    for i, e in enumerate(events):
        g = gt[e]
        text = single_prompt(g["text"] if args.mode == "audio+text" else None)
        a = audio(g["wav"])
        t0 = time.monotonic()
        pred, lp = constrained(model, proc, first, [a], text)
        raw = free(model, proc, [a], text)
        p1 = parse(raw)
        raw2 = None
        p2 = p1
        if p1 is None:
            raw2 = free(model, proc, [a], text + "\nRespond with ONLY the JSON object, nothing else.")
            p2 = parse(raw2)
        rows.append({"event": e, "human_word": g["word"], "human_family": g["family"],
                     "constrained_pred": pred, "logprobs": lp, "free_raw": raw, "free_parse": p1,
                     "retry_raw": raw2, "retry_parse": p2, "latency_s": round(time.monotonic() - t0, 2)})
        print(i, e, g["family"], pred, repr(raw[:50]), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = args.mode.replace("+", "_")
    (OUT / f"single_{tag}.json").write_text(json.dumps(rows, indent=1))


def run_pair(args):
    model, proc, first = load()
    gt = load_gt()
    rnd = random.Random(0)
    evs = list(gt)
    rows = []
    tries = 0
    while len(rows) < args.n and tries < 2000:
        tries += 1
        ref, same, diff = rnd.sample(evs, 3)
        if not (gt[ref]["family"] == gt[same]["family"] != gt[diff]["family"]):
            same = next((x for x in evs if x != ref and gt[x]["family"] == gt[ref]["family"]), None)
            if same is None or gt[diff]["family"] == gt[ref]["family"] or diff in (ref, same):
                continue
        swap = rnd.random() < 0.5
        A, B = (diff, same) if swap else (same, diff)
        text = ("You will hear three clips of the same character. First the REFERENCE clip, then "
                "CLIP A, then CLIP B. Which of A or B is closer to the reference in emotional "
                'delivery (tone, energy, pace)? Answer strict JSON only: {"closer": "A"} or {"closer": "B"}')
        auds = [audio(gt[x]["wav"]) for x in (ref, A, B)]
        raw = free(model, proc, auds, text, max_new=16)
        m = re.search(r'"closer"\s*:\s*"([AB])"', raw)
        # constrained too
        inp = to_dev(build(proc, auds, text, '{"closer": "'), model)
        with torch.no_grad():
            lg = model(**inp).logits[0, -1].float()
        tk = proc.tokenizer
        ia, ib = tk.encode("A", add_special_tokens=False)[0], tk.encode("B", add_special_tokens=False)[0]
        cpred = "A" if lg[ia] > lg[ib] else "B"
        truth = "A" if A == same else "B"
        rows.append({"ref": ref, "A": A, "B": B, "truth": truth, "free_raw": raw,
                     "free_pred": m.group(1) if m else None, "constrained_pred": cpred,
                     "ref_family": gt[ref]["family"], "diff_family": gt[diff]["family"]})
        print(len(rows), truth, cpred, repr(raw), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pair.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("single"); s.add_argument("--mode", choices=["audio", "audio+text"], required=True)
    s.add_argument("--limit", type=int, default=0)
    p = sub.add_parser("pair"); p.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    run_single(a) if a.cmd == "single" else run_pair(a)
