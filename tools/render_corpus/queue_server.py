#!/usr/bin/env python3
"""Coordinator for networked rendering. Workers on any machine on the LAN pull jobs, render, and upload the audio here.

  python3 tools/render_corpus/queue_server.py --run overnight1 --jobs data/render/jobs.jsonl [--max-priority 2] [--port 8920]

Prints a token; give it to each worker (RT_QUEUE_TOKEN or --token). Results land in data/render/<run>/ exactly like a
single-machine render (wav/<guid>.wav + manifest.jsonl, plus asr.jsonl when workers run Whisper), so merge.py and the audit
page work unchanged. Restart it any time: progress is rebuilt from the manifest. GET /status shows throughput per machine.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jobqueue import JobQueue
import processed

ROOT = Path(__file__).resolve().parents[2]


def read_manifest(path: Path) -> tuple[set[str], Counter]:
    done, fails = set(), Counter()
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            if r.get("status") == "ok":
                done.add(r["guid"])
            else:
                fails[r["guid"]] += 1
    return done, fails


class Handler(BaseHTTPRequestHandler):
    queue: JobQueue
    run_dir: Path
    token: str
    write_lock = threading.Lock()

    def _send(self, body: bytes, ctype="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        if self.headers.get("X-Token") == self.token:
            return True
        self._send(b'{"error":"bad token"}', code=401)
        return False

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length", 0)))

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/status":   # no token: shows only counts and speeds
            return self._send(json.dumps(self.queue.status()).encode())
        if not self._authed():
            return
        if u.path == "/ref":
            rel = parse_qs(u.query).get("path", [""])[0]
            p = (ROOT / rel).resolve()
            if not p.is_file() or p.suffix != ".wav" or ROOT / "data" not in p.parents:
                return self._send(b'{"error":"no such reference"}', code=404)
            return self._send(p.read_bytes(), "audio/wav")
        self._send(b"{}", code=404)

    def do_POST(self):
        u = urlparse(self.path)
        if not self._authed():
            return
        if u.path == "/lease":
            b = json.loads(self._body() or b"{}")
            self.queue.renew(b["worker"])
            if b["worker"] in blocked_workers():
                return self._send(json.dumps({"jobs": []}).encode())
            jobs = self.queue.lease(b["worker"], b["engine"], int(b.get("n", 2)))
            return self._send(json.dumps({"jobs": jobs}).encode())
        if u.path == "/result":
            q = parse_qs(u.query)
            guid, worker = q["guid"][0], q["worker"][0]
            row = json.loads(base64.urlsafe_b64decode(self.headers["X-Row"]))
            asr = row.pop("asr", None)
            data = self._body()
            ok = row.get("status") == "ok" and len(data) > 44
            row["worker"] = worker
            if not ok:
                row["status"] = "failed"
            with self.write_lock:   # one writer at a time keeps manifest lines whole
                if ok:
                    tmp = self.run_dir / "wav" / f".{guid}.tmp"
                    tmp.write_bytes(data)
                    os.replace(tmp, self.run_dir / "wav" / f"{guid}.wav")
                with open(self.run_dir / "manifest.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                if asr:
                    with open(self.run_dir / "asr.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps({"guid": guid, **asr}, ensure_ascii=False) + "\n")
            self.queue.complete(guid, worker, ok, float(row.get("seconds") or 0))
            return self._send(b'{"ok":true}')
        self._send(b"{}", code=404)

    def log_message(self, *a):
        pass


def blocked_workers() -> set[str]:
    """Worker names in data/render/blocked_workers.txt (one per line, read on every lease) get no jobs: a worker whose code or setup is not right."""
    p = ROOT / "data/render/blocked_workers.txt"
    return {ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")} if p.is_file() else set()


def load_jobs(path: Path, root: Path = ROOT) -> list[dict]:
    """The jobs in a file, with processed speakers' recipes already at the higher step count (see processed.py)."""
    jobs = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return processed.apply(jobs, processed.load(root))


def watch(queue: JobQueue, folder: Path, loaded: set[str], every_s: float) -> None:
    """Add the jobs of every *.jsonl that appears in `folder` (write the file elsewhere and rename it in, so it is whole)."""
    import time
    while True:
        for f in sorted(folder.glob("*.jsonl")):
            if f.name not in loaded:
                try:
                    n = queue.add(load_jobs(f))
                except (OSError, ValueError) as e:
                    print(f"cannot read {f.name}: {e}", flush=True)
                    continue
                loaded.add(f.name)
                print(f"added {n} jobs from {f.name}", flush=True)
        time.sleep(every_s)


class Server(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="results go to data/render/<run>")
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs.jsonl"))
    ap.add_argument("--max-priority", type=int, default=9)
    ap.add_argument("--port", type=int, default=8920)
    ap.add_argument("--host", default="0.0.0.0", help="0.0.0.0 = reachable from the LAN (token required either way)")
    ap.add_argument("--token", default=os.environ.get("RT_QUEUE_TOKEN") or secrets.token_urlsafe(12))
    ap.add_argument("--lease-s", type=float, default=900.0)
    ap.add_argument("--watch", help="folder to watch: jobs of any *.jsonl that appears (or is already there) are queued, so a run can grow")
    ap.add_argument("--watch-every", type=float, default=15.0)
    a = ap.parse_args()
    run_dir = ROOT / "data/render" / a.run
    (run_dir / "wav").mkdir(parents=True, exist_ok=True)
    done, fails = read_manifest(run_dir / "manifest.jsonl")
    jobs = load_jobs(Path(a.jobs)) if a.jobs not in ("", "none") else []
    Handler.queue = JobQueue(jobs, done, fails, a.lease_s, a.max_priority)
    if a.watch:
        folder = Path(a.watch)
        folder.mkdir(parents=True, exist_ok=True)
        loaded: set[str] = set()
        threading.Thread(target=watch, args=(Handler.queue, folder, loaded, a.watch_every), daemon=True).start()
    Handler.run_dir, Handler.token = run_dir, a.token
    st = Handler.queue.status()
    print(f"{st['total']} jobs, {st['done']} already done. token: {a.token}", flush=True)
    print(f"workers: python tools/render_corpus/worker.py --server http://THIS_HOST:{a.port} --engine voxcpm2 --token {a.token}", flush=True)
    Server((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
