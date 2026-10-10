"""Server-side job queue for model generations.

One worker thread runs jobs one after another (the GPU does one generation at a time anyway). A job is a list of
items; each item is the body of an existing synchronous route (clone/generate or design/generate), so the work is done
by clone.generate / design.generate. The registry is kept in memory and mirrored to data/studio/_jobs.json so a
restart keeps the history (jobs that were still queued or running then are marked failed).

The seed is drawn here, at submit time, when an item leaves it blank: the record returned by submit already shows
every item's seed, long before the model answers.
"""
from __future__ import annotations

import copy
import queue
import random
import threading
import time
import weakref

from . import clone, design, fx
from .config import Config
from .errors import ApiError
from .jsonio import read_json, write_json_atomic
from .speakers import find_speaker, studio_dir
from .store import OPTION_DEFAULTS, read_takes

KINDS = ("clone", "design")
LABELS = {"clone": "Generating", "design": "Designing"}
MAX_ITEMS = 200
HISTORY = 100
SEED_LIMIT = 2 ** 31
DEFAULT_LIST_LIMIT = 50
EXPECTED_FROM_TAKES = 20          # past takes averaged for expected_s when this job has no finished item yet
ACTIVE = ("queued", "running")
RESTART_ERROR = "the studio server restarted before this job finished"


class _Cancelled(Exception):
    pass


class _Guarded:
    """Wraps the model for one job: a result that arrives after Cancel is dropped before anything is saved."""

    def __init__(self, model, is_cancelled):
        self._model, self._cancelled = model, is_cancelled

    def call(self, path: str, body: dict) -> dict:
        out = self._model.call(path, body)
        if self._cancelled():
            raise _Cancelled()
        return out


def draw_seed() -> int:
    return random.SystemRandom().randrange(SEED_LIMIT)


class JobQueue:
    def __init__(self, cfg: Config, model):
        self.cfg, self.model = cfg, model
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._last_id = 0
        self._load()

    # ---- persistence -------------------------------------------------------------------------------------------
    @property
    def _path(self):
        return self.cfg.studio / "_jobs.json"

    def _load(self) -> None:
        try:
            saved = read_json(self._path, [])
        except ApiError:
            saved = []
        for j in saved:
            if j.get("state") in ACTIVE:
                j.update(state="failed", error=RESTART_ERROR, finished_at=time.time())
                for it in j.get("items", []):
                    if it["state"] in ("queued", "running"):
                        it["state"] = "cancelled"
            self._jobs[j["id"]] = j

    def _save(self) -> None:
        for old in list(self._jobs)[:-HISTORY]:
            if self._jobs[old]["state"] not in ACTIVE:
                del self._jobs[old]
        write_json_atomic(self._path, list(self._jobs.values()))

    # ---- submit ------------------------------------------------------------------------------------------------
    def _new_id(self) -> str:
        self._last_id = max(int(time.time() * 1000), self._last_id + 1)
        return f"j{self._last_id}"

    def _item(self, kind: str, slug: str, n: int, raw: dict) -> dict:
        if not isinstance(raw, dict):
            raise ApiError(400, f"item {n} must be an object")
        body = copy.deepcopy(raw)
        if kind == "clone":
            ref = body.get("reference") or {}
            if not isinstance(body.get("text"), str) or not body["text"].strip():
                raise ApiError(400, f"item {n}: text is required")
            if self.cfg.under_data(ref.get("wav", "")) is None:
                raise ApiError(400, f"item {n}: reference is not a file under data/: {ref.get('wav')!r}")
            o = body["options"] = {**OPTION_DEFAULTS, **(body.get("options") or {})}
            if not str(o.get("seed", "")).strip():
                o["seed"] = draw_seed()
            clone._check_options(o)
            seed, cfg_v, steps, text = o["seed"], o["cfg"], o["timesteps"], body["text"]
        else:
            body["cfg"], body["timesteps"] = body.get("cfg", 2.0), body.get("timesteps", 10)
            if not str(body.get("seed", "")).strip():
                body["seed"] = draw_seed()
            clone._check_options({"seed": body["seed"], "cfg": body["cfg"], "timesteps": body["timesteps"]})
            seed, cfg_v, steps, text = body["seed"], body["cfg"], body["timesteps"], None
        return {"n": n, "state": "queued", "body": body, "seed": int(seed), "cfg": cfg_v, "timesteps": steps,
                "text": text, "started_at": None, "elapsed_s": None, "take": None, "result": None, "error": None,
                "fx_error": None}

    def submit(self, body: dict) -> dict:
        kind, slug = body.get("kind"), body.get("slug")
        if kind not in KINDS:
            raise ApiError(400, f"kind must be one of {KINDS}")
        if not isinstance(slug, str) or not slug:
            raise ApiError(400, "slug is required")
        find_speaker(self.cfg, slug)
        if kind == "design":
            design.design_name(self.cfg, slug)
        raw = body.get("items")
        if not isinstance(raw, list) or not raw or len(raw) > MAX_ITEMS:
            raise ApiError(400, f"items must be a list of 1 to {MAX_ITEMS} request bodies")
        presets = body.get("fx") or []
        if kind != "clone" and presets:
            raise ApiError(400, "fx applies to clone jobs only")
        if not isinstance(presets, list) or not all(isinstance(p, str) for p in presets):
            raise ApiError(400, "fx must be a list of preset names")
        if kind == "clone":
            read_takes(self.cfg, slug)          # a corrupt takes.json must stop us before any generation is spent
        items = [self._item(kind, slug, i, r) for i, r in enumerate(raw)]
        with self._lock:
            job = {"id": self._new_id(), "kind": kind, "slug": slug, "label": str(body.get("label") or LABELS[kind]),
                   "state": "queued", "total": len(items), "done": 0, "index": 0, "items": items, "takes": [],
                   "fx": presets, "error": None, "cancel_requested": False, "created_at": time.time(),
                   "started_at": None, "finished_at": None}
            self._jobs[job["id"]] = job
            self._save()
            if self._thread is None:
                self._thread = threading.Thread(target=self._work, daemon=True, name="studio-jobs")
                self._thread.start()
            self._q.put(job["id"])
            return self._view(job)

    # ---- reading -----------------------------------------------------------------------------------------------
    def _expected(self, job: dict) -> float | None:
        secs = [it["result"].get("seconds") for it in job["items"] if it["state"] == "done" and it["result"]]
        if not secs and job["kind"] == "clone":
            takes = sorted(read_takes(self.cfg, job["slug"]).values(), key=lambda t: t["id"])[-EXPECTED_FROM_TAKES:]
            secs = [t.get("seconds") for t in takes]
        secs = [s for s in secs if isinstance(s, (int, float))]
        return round(sum(secs) / len(secs), 2) if secs else None

    def _view(self, job: dict) -> dict:
        """A copy for the caller: no request bodies, elapsed times filled in, `current` set while an item runs."""
        now = time.time()
        v = copy.deepcopy(job)
        for it in v["items"]:
            it.pop("body", None)
            if it["state"] == "running":
                it["elapsed_s"] = round(now - it["started_at"], 2)
        v["elapsed_s"] = round((v["finished_at"] or now) - v["started_at"], 2) if v["started_at"] else 0.0
        v["expected_s"] = self._expected(job)
        v["current"] = next(({k: it[k] for k in ("n", "text", "seed", "cfg", "timesteps", "started_at", "elapsed_s")}
                             | {"expected_s": v["expected_s"]} for it in v["items"] if it["state"] == "running"), None)
        return v

    def get(self, job_id: str) -> dict:
        with self._lock:
            if job_id not in self._jobs:
                raise ApiError(404, f"no job '{job_id}'")
            return self._view(self._jobs[job_id])

    def list(self, active: bool = False, slug: str | None = None, limit: int = DEFAULT_LIST_LIMIT) -> list[dict]:
        with self._lock:
            jobs = [j for j in self._jobs.values() if (not active or j["state"] in ACTIVE) and (not slug or j["slug"] == slug)]
            if not active:
                jobs.reverse()
            return [self._view(j) for j in jobs[:max(1, limit)]]

    def active_entry(self) -> dict | None:
        """The compact entry /api/model/health carries: the running job, else the first queued one."""
        with self._lock:
            live = [j for j in self._jobs.values() if j["state"] in ACTIVE]
            if not live:
                return None
            j = next((x for x in live if x["state"] == "running"), live[0])
            v = self._view(j)
            return {"id": j["id"], "label": j["label"], "kind": j["kind"], "slug": j["slug"], "state": j["state"],
                    "index": j["index"], "total": j["total"], "done": j["done"], "elapsed_s": v["elapsed_s"],
                    "expected_s": v["expected_s"], "active_jobs": len(live)}

    # ---- cancel ------------------------------------------------------------------------------------------------
    def cancel(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ApiError(404, f"no job '{job_id}'")
            if job["state"] not in ACTIVE:
                raise ApiError(409, f"job is already {job['state']}")
            job["cancel_requested"] = True
            if job["state"] == "queued":
                self._finish(job, "cancelled")
            else:                    # running: the in-flight take cannot be aborted; its result is dropped when it lands
                for it in job["items"]:
                    if it["state"] == "queued":
                        it["state"] = "cancelled"
                self._save()
            return self._view(job)

    # ---- worker ------------------------------------------------------------------------------------------------
    def _finish(self, job: dict, state: str, error: str | None = None) -> None:
        for it in job["items"]:
            if it["state"] in ("queued", "running"):
                it["state"] = "cancelled"
        job.update(state=state, finished_at=time.time(), error=error or job["error"])
        self._save()

    def _work(self) -> None:
        while True:
            jid = self._q.get()
            with self._lock:
                job = self._jobs.get(jid)
                if job is None or job["state"] != "queued":
                    continue
                job.update(state="running", started_at=time.time())
                self._save()
            try:
                self._run(job)
            except Exception as e:         # never let the worker die
                with self._lock:
                    self._finish(job, "failed", f"{type(e).__name__}: {e}")

    def _execute(self, job: dict, it: dict) -> None:
        model = _Guarded(self.model, lambda: job["cancel_requested"])
        if job["kind"] == "design":
            it["result"] = design.generate(self.cfg, model, job["slug"], it["body"])
            return
        take = clone.generate(self.cfg, model, job["slug"], it["body"])
        it["take"] = take["id"]
        if job["fx"]:
            try:
                take = fx.apply_to_take(self.cfg, job["slug"], take["id"], job["fx"])
            except ApiError as e:       # the raw take is kept and usable; the page can retry the FX
                it["fx_error"] = e.message
        it["result"] = take

    def _run(self, job: dict) -> None:
        fatal = None
        for it in job["items"]:
            with self._lock:
                if job["cancel_requested"] or fatal:
                    break
                it.update(state="running", started_at=time.time())
                job["index"] = it["n"] + 1
                self._save()
            outcome, err = "done", None
            try:
                self._execute(job, it)
            except _Cancelled:
                outcome = "cancelled"
            except ApiError as e:
                outcome, err = "failed", e.message
                if e.status == 503:          # the model is down: the rest would fail the same way
                    fatal = e.message
            except Exception as e:
                outcome, err = "failed", f"{type(e).__name__}: {e}"
            with self._lock:
                it.update(state=outcome, error=err, elapsed_s=round(time.time() - it["started_at"], 2))
                if outcome == "done":
                    job["done"] += 1
                    if it["take"]:
                        job["takes"].append(it["take"])
                self._save()
        with self._lock:
            items = job["items"]
            if job["cancel_requested"]:
                self._finish(job, "cancelled")
            elif fatal or all(i["state"] == "failed" for i in items):
                self._finish(job, "failed", fatal or items[0]["error"])
            else:
                self._finish(job, "done")


_QUEUES: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()
_QUEUES_LOCK = threading.Lock()


def queue_for(cfg: Config, model) -> JobQueue:
    """One queue per model client (and so per running server); created on first use."""
    with _QUEUES_LOCK:
        q = _QUEUES.get(model)
        if q is None:
            q = _QUEUES[model] = JobQueue(cfg, model)
        return q


def health(cfg: Config, model) -> dict:
    """The /api/model/health body: {state} plus {job} while a job is queued or running. A running job makes a ready
    backend read as busy (it is between two takes)."""
    state = model.health()
    job = queue_for(cfg, model).active_entry()
    if job is None:
        return {"state": state}
    return {"state": "busy" if state == "ready" else state, "job": job}
