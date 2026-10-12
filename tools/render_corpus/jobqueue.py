"""Job queue state for networked rendering: which jobs are pending, leased to a worker, or done.

Pure logic (no HTTP, no torch) so it is unit tested. The coordinator in queue_server.py wraps it.
A lease expires if its worker goes quiet (laptop asleep, machine taken back), and the job goes to someone else.
"""
from __future__ import annotations

import threading
import time
from collections import Counter

MAX_FAILURES = 2


class JobQueue:
    def __init__(self, jobs: list[dict], done: set[str] | None = None, failures: Counter | None = None,
                 lease_s: float = 900.0, max_priority: int = 9, clock=time.time):
        jobs = [j for j in jobs if j["priority"] <= max_priority]
        # segments of one cue share the cue's best priority and stay together in segment order, so cues finish (and can be
        # stitched) one by one instead of all speech first and all narration last
        group: dict[str, int] = {}
        for j in jobs:
            if j.get("parent"):
                group[j["parent"]] = min(group.get(j["parent"], 99), j["priority"])
        self.jobs = sorted(jobs, key=lambda j: (group.get(j.get("parent"), j["priority"]), j.get("parent", j["guid"]),
                                                j.get("seg_index", 0), j["guid"]))
        self.done = set(done or ())
        self.failures = Counter(failures or ())
        self.lease_s = lease_s
        self.clock = clock
        self.leases: dict[str, tuple[float, str]] = {}   # guid -> (expires at, worker)
        self.stats: dict[str, dict] = {}                 # worker -> {"jobs": n, "audio_s": s, "first": t, "last": t}
        self._lock = threading.Lock()

    def _available(self, j: dict, now: float) -> bool:
        g = j["guid"]
        if g in self.done or self.failures[g] >= MAX_FAILURES:
            return False
        lease = self.leases.get(g)
        return lease is None or lease[0] <= now

    def lease(self, worker: str, engine: str, n: int = 2) -> list[dict]:
        now = self.clock()
        with self._lock:
            out = []
            for j in self.jobs:
                if j["engine"] == engine and self._available(j, now):
                    self.leases[j["guid"]] = (now + self.lease_s, worker)
                    out.append(j)
                    if len(out) >= n:
                        break
            return out

    def renew(self, worker: str) -> None:
        now = self.clock()
        with self._lock:
            for g, (_, w) in self.leases.items():
                if w == worker:
                    self.leases[g] = (now + self.lease_s, w)

    def complete(self, guid: str, worker: str, ok: bool, audio_s: float = 0.0) -> None:
        now = self.clock()
        with self._lock:
            self.leases.pop(guid, None)
            if ok:
                self.done.add(guid)
            else:
                self.failures[guid] += 1
            s = self.stats.setdefault(worker, {"jobs": 0, "audio_s": 0.0, "first": now, "last": now})
            s["jobs"] += 1
            s["audio_s"] += audio_s
            s["last"] = now

    def status(self) -> dict:
        now = self.clock()
        with self._lock:
            live = {g for g, (exp, _) in self.leases.items() if exp > now}
            gave_up = sum(1 for j in self.jobs if j["guid"] not in self.done and self.failures[j["guid"]] >= MAX_FAILURES)
            workers = {}
            for w, s in self.stats.items():
                span = max(s["last"] - s["first"], 1.0)
                workers[w] = {"jobs": s["jobs"], "audio_h": round(s["audio_s"] / 3600, 3),
                              "audio_h_per_h": round(s["audio_s"] / span, 2), "idle_s": round(now - s["last"])}
            total = len(self.jobs)
            rate = sum(w["audio_h_per_h"] for w in workers.values())
            return {"total": total, "done": len(self.done & {j["guid"] for j in self.jobs}), "leased": len(live),
                    "gave_up": gave_up, "pending": total - len(self.done) - gave_up - len(live), "workers": workers,
                    "aggregate_audio_h_per_h": round(rate, 2)}
