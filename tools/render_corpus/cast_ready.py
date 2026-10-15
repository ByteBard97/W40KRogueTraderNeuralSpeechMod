#!/usr/bin/env python3
"""Render cast characters as their voices become ready, without waiting for the rest.

  python3 tools/render_corpus/cast_ready.py [--once] [--interval 60] [--dry-run] [--status]

A character is READY when (1) the Casting page has assigned a BG3 voice (data/studio/casting.json) and (2) that voice's reference clips have
been rebuilt and pass the quality check (catalog refs_quality "good" or "ok"). Each tick the driver, for every newly ready character:
  1. registers the voice in the prompt bank (the studio's casting.register_one; prompts.json is backed up first),
  2. plans ALL of that character's lines in the new voice (plan_voiceless.build with only=...) into data/render/cast_jobs/<batch>.jsonl,
  3. leaves the file where the queue server (run `cast`, started with --watch data/render/cast_jobs) picks it up and workers render it.
It then stitches whatever finished into data/render/cast-stitched (stitch_mixed, one clip per cue), which night_build.py overlays last.
State is data/studio/cast_render.json. A character whose assignment changes after rendering is reported, not re-rendered
automatically (re-rendering would race the stitched take); decide that with the user.
The GPU workers are started by the driver once there is work: the 4070 always, the 5080 only while the game is closed and
data/render/cast_no_local does not exist (create that file to keep this machine free; delete it to give the 5080 back).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/studio/server"))

RUN = "cast"
PORT = 8952
TOKEN = "valtok"
GOOD = ("good", "ok")
MAX_CHARS = 1200


def read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def paths(root: Path) -> dict[str, Path]:
    return {"casting": root / "data/studio/casting.json", "catalog": root / "data/bg3_voices/catalog.json",
            "state": root / "data/studio/cast_render.json", "batches": root / "data/render/cast_jobs",
            "all": root / "data/render/jobs_cast_all.jsonl", "jobs": root / "data/render/jobs.jsonl"}


def ready(root: Path = ROOT) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """[(character, bg3 slug)] whose voice is assigned and has a good reference; and why the others are not ready."""
    p = paths(root)
    assigned = read(p["casting"], {}).get("assignments", {})
    catalog = {v["slug"]: v for v in read(p["catalog"], [])}
    ok, waiting = [], {}
    for sp, a in assigned.items():
        v = catalog.get(a["bg3"])
        if v is None:
            waiting[sp] = "voice not in the catalog"
        elif v.get("refs_quality") not in GOOD:
            waiting[sp] = f"reference not rebuilt yet ({v.get('refs_quality') or 'not checked'})"
        elif not (root / v["refs"][0]["wav"]).is_file():
            waiting[sp] = "reference file missing"
        else:
            ok.append((sp, a["bg3"]))
    return ok, waiting


def queue_up(port: int = PORT) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=3)
        return True
    except OSError:
        return False


def ensure_queue(root: Path = ROOT) -> None:
    if queue_up():
        return
    log = open(root / "data/render/overnight/queue8952.log", "ab")
    subprocess.Popen([sys.executable, str(root / "tools/render_corpus/queue_server.py"), "--run", RUN, "--jobs", "none",
                      "--watch", str(paths(root)["batches"]), "--port", str(PORT), "--token", TOKEN],
                     stdout=log, stderr=log, start_new_session=True, cwd=root)
    time.sleep(3)


WIN_PS1 = r"""$cmd = 'cmd.exe /c cd /d C:\Users\geoff\rt-tts\repo && C:\Users\geoff\rt-tts\.venv-vox\Scripts\python.exe -u tools\render_corpus\worker.py --server http://%(ip)s:%(port)d --engine voxcpm2 --token %(tok)s --name win-4070 --asr-model openai/whisper-small --pipeline >> C:\Users\geoff\rt-tts\worker-cast.log 2>&1'
(Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$cmd}).ReturnValue
"""
WIN_LIST = r"""Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like '*worker.py*:%(port)d*' } | ForEach-Object { $_.ProcessId }
"""
WHEN_FREE_FILE = "data/render/cast_local_when_free"   # while this file exists the 5080 worker starts only when the GPU is free, checked every 30 minutes
CHECK_FILE = "data/render/cast_local_last_check"
CHECK_EVERY_S = 1800
FREE_MIB_NEEDED = 11500       # what the worker needs on the 5080: VoxCPM2 plus Whisper (about 10.5 GB) with a little room
IDLE_UTIL_PCT = 20
NO_LOCAL_FILE = "data/render/cast_no_local"      # create this file to keep the driver from starting the 5080 worker (the machine is needed for other work)
LAN_IP = "192.168.0.200"
LOCAL_PY = "/home/geoff/anaconda3/envs/roguetts/bin/python3"


def sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def game_running() -> bool:
    return bool(sh("pgrep -f '[Z]:.*WH40KRT.exe'").strip())


def win_run(script: str, root: Path) -> str:
    f = root / "data/render/overnight/_cast_win.ps1"
    f.write_text(script % {"ip": LAN_IP, "port": PORT, "tok": TOKEN}, encoding="utf-8")
    sh(f"scp -q {f} win-gpu:C:/Users/geoff/rt-tts/_cast_win.ps1")
    return sh("ssh -o ConnectTimeout=10 win-gpu 'powershell -NoProfile -File C:\\Users\\geoff\\rt-tts\\_cast_win.ps1'")


def gpu_free(samples: int = 3, gap_s: float = 2.0) -> tuple[bool, str]:
    """Is the local GPU free for our worker: enough memory left and nobody keeping it busy (utilisation averaged over a few samples)?"""
    used = total = 0
    utils = []
    for i in range(samples):
        out = sh("nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits").strip().split("\n")[0]
        try:
            used, total, u = (int(x) for x in out.split(","))
        except ValueError:
            return False, "could not read nvidia-smi"
        utils.append(u)
        if i < samples - 1:
            time.sleep(gap_s)
    free, avg = total - used, sum(utils) / len(utils)
    ok = free >= FREE_MIB_NEEDED and avg < IDLE_UTIL_PCT
    return ok, f"{free} MiB free of {total}, utilisation {avg:.0f}%"


def marker_settings(root: Path) -> dict:
    """The wait-for-free marker may hold JSON: {"not_before": "2026-10-12T22:55:00", "every_s": 600} (an empty file means the defaults)."""
    try:
        return json.loads((root / WHEN_FREE_FILE).read_text() or "{}")
    except (OSError, ValueError):
        return {}


def check_due(root: Path, now: float | None = None) -> bool:
    """True when the free-GPU check is due: not before the marker's `not_before`, then every `every_s` seconds (default 30 minutes)."""
    now = time.time() if now is None else now
    cfg = marker_settings(root)
    if cfg.get("not_before") and now < time.mktime(time.strptime(cfg["not_before"], "%Y-%m-%dT%H:%M:%S")):
        return False
    f = root / CHECK_FILE
    last = float(f.read_text()) if f.is_file() else 0.0
    if now - last < float(cfg.get("every_s", CHECK_EVERY_S)):
        return False
    f.write_text(str(now))
    return True


def local_gate(root: Path) -> tuple[bool, str]:
    """May the 5080 worker start now, and what to log about it."""
    if (root / NO_LOCAL_FILE).exists():
        return False, "5080 paused (cast_no_local exists)"
    if game_running():
        return False, "the game is running"
    if (root / WHEN_FREE_FILE).exists():
        if not check_due(root):
            return False, "waiting for the next free-GPU check (see data/render/cast_local_when_free)"
        ok, why = gpu_free()
        return (True, f"GPU free again ({why}): starting the 5080 worker") if ok else (False, f"GPU still busy ({why})")
    return True, ""


MIN_FREE_GIB = 8.0


def disk_low(root: Path) -> str | None:
    """A render that fills the disk can cut a manifest line in half; below this the driver starts no more workers and says so."""
    import shutil
    free = shutil.disk_usage(root).free / 2 ** 30
    return f"LOW DISK: {free:.1f} GiB free on / (need {MIN_FREE_GIB:.0f}); no workers started" if free < MIN_FREE_GIB else None


def ensure_workers(root: Path = ROOT) -> dict:
    """Start the render workers once there is work: the 4070 always, the 5080 only while the game is closed (they cannot share the card)."""
    if not queue_up():
        return {}
    low = disk_low(root)
    if low:
        return {"disk": low}
    q = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/status", timeout=3).read())
    if q["pending"] + q["leased"] == 0:
        return {"workers": "idle, no work"}
    started = []
    if not win_run(WIN_LIST, root).strip():
        win_run(WIN_PS1, root)
        started.append("win-4070")
    info: dict = {}
    if not sh(f"pgrep -f '[w]orker.py.*:{PORT}'").strip():
        go, note = local_gate(root)
        if note:
            info["local_gpu"] = note
        if go:
            log = open(root / "data/render/overnight/worker-cast-5080.log", "ab")
            subprocess.Popen([LOCAL_PY, "-u", str(root / "tools/render_corpus/worker.py"), "--server", f"http://127.0.0.1:{PORT}", "--engine", "voxcpm2",
                              "--token", TOKEN, "--name", "linux-5080", "--asr-model", "openai/whisper-small"], stdout=log, stderr=log,
                             start_new_session=True, cwd=root)
            started.append("linux-5080")
            marker = root / WHEN_FREE_FILE
            if marker.exists():      # the GPU came free: the worker keeps the card from here on (marker moved aside, not deleted)
                os.replace(marker, root / f"{WHEN_FREE_FILE}.resumed-{time.strftime('%Y%m%d-%H%M%S')}")
    return {"workers_started": started, "game_running": game_running(), **info}


def stitch(root: Path) -> str:
    """Join the finished pieces of every batch into one clip per cue (cast-stitched). Needs the render environment (soundfile)."""
    p = paths(root)
    files = [f for f in sorted(p["batches"].glob("*.jsonl")) if not f.name.startswith("redo-")]     # redo takes replace pieces, they are not pieces
    if not files or not (root / "data/render" / RUN / "manifest.jsonl").is_file():
        return "nothing to stitch yet"
    p["all"].write_text("".join(f.read_text(encoding="utf-8") for f in files), encoding="utf-8")
    env = {**os.environ, "LENIENT_RUNS": RUN}
    r = subprocess.run([sys.executable, str(root / "tools/render_corpus/stitch_mixed.py"), "--jobs", str(p["all"]), "--runs", RUN,
                        "--out", "cast-stitched"], capture_output=True, text=True, env=env, cwd=root)
    return (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:]])[-1]


def tick(root: Path = ROOT, dry_run: bool = False) -> dict:
    p = paths(root)
    state = read(p["state"], {})
    ok, waiting = ready(root)
    fresh = [(sp, bg) for sp, bg in ok if sp not in state]
    changed = [sp for sp, bg in ok if sp in state and state[sp]["bg3"] != bg]
    out = {"ready": len(ok), "new": [sp for sp, _ in fresh], "changed_since_render": changed, "waiting": waiting, "planned": 0, "stitch": None}
    if fresh and not dry_run:
        from studio_server import casting
        from studio_server.config import Config
        reg = casting.register(Config(root=root), only=[sp for sp, _ in fresh])
        import plan_voiceless
        done = set(reg["registered"])
        rows, stats, missing = plan_voiceless.build(p["jobs"], MAX_CHARS, done)
        batch = time.strftime("cast-%Y%m%d-%H%M%S")
        if rows:
            p["batches"].mkdir(parents=True, exist_ok=True)
            tmp = p["batches"] / f".{batch}.tmp"
            tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
            os.replace(tmp, p["batches"] / f"{batch}.jsonl")
        for sp, bg in fresh:
            if sp in done:
                state[sp] = {"bg3": bg, "batch": batch, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                             "pieces": sum(1 for r in rows if r["speaker"] == sp)}
        write(p["state"], state)
        out.update(planned=len(rows), registered=sorted(done), unregistered=reg["skipped"], batch=batch if rows else None, unplanned=dict(missing))
    if not dry_run:
        out["stitch"] = stitch(root)
        out.update(ensure_workers(root))
        import cast_followup
        out.update(cast_followup.step(root))        # once the queue is idle: redo what failed, accept the best of what cannot do better, audit, report
        if disk_low(root):
            out["disk"] = disk_low(root)
    return out


def status(root: Path = ROOT) -> str:
    ok, waiting = ready(root)
    state = read(paths(root)["state"], {})
    q = None
    if queue_up():
        q = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/status", timeout=3).read())
    lines = [f"ready {len(ok)}, waiting {len(waiting)}, queued for render {len(state)}"]
    if q:
        lines.append(f"queue: {q['done']} of {q['total']} done, {q['pending']} pending, workers {list(q['workers'])}")
    for sp, why in list(waiting.items())[:10]:
        lines.append(f"  waiting: {sp}: {why}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true", help="say what would be registered and planned; change nothing")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        print(status())
        return
    while True:
        if not a.dry_run:
            ensure_queue()
        out = tick(dry_run=a.dry_run)
        print(time.strftime("%H:%M:%S"), {k: v for k, v in out.items() if k != "waiting"}, f"waiting {len(out['waiting'])}", flush=True)
        if a.once or a.dry_run:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
