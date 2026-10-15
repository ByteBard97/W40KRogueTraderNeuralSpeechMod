from __future__ import annotations

from . import auto_cast, bg3_labels, rt_voices, casting, clone, design, lab, lab_opus, fx, fx_library, jobs, matches, pools, qa, speakers, store, summary
from .errors import ApiError
from .router import Router


def build_router() -> Router:
    r = Router()
    S = "/api/speakers/{slug}"
    r.add("GET", "/api/model/health", lambda q: jobs.health(q.cfg, q.model))
    r.add("GET", "/api/summary", lambda q: summary.summary(q.cfg, q.model))
    queue = lambda q: jobs.queue_for(q.cfg, q.model)
    r.add("POST", "/api/jobs", lambda q: queue(q).submit(q.body))
    r.add("GET", "/api/jobs", lambda q: queue(q).list(
        active=q.query.get("active", "") not in ("", "0", "false"), slug=q.query.get("slug"),
        limit=int(q.query.get("limit", jobs.DEFAULT_LIST_LIMIT))))
    r.add("GET", "/api/jobs/{id}", lambda q: queue(q).get(q.params["id"]))
    r.add("POST", "/api/jobs/{id}/cancel", lambda q: queue(q).cancel(q.params["id"]))
    r.add("GET", "/api/speakers", lambda q: speakers.list_speakers(q.cfg))
    r.add("POST", "/api/speakers/register-all", lambda q: design.register_all(q.cfg))
    r.add("GET", S, lambda q: speakers.speaker_detail(q.cfg, q.params["slug"]))
    r.add("GET", S + "/lines", lambda q: speakers.speaker_lines(q.cfg, speakers.find_speaker(q.cfg, q.params["slug"])["name"]))
    def list_takes(q):
        speakers.find_speaker(q.cfg, q.params["slug"])      # 404 for an unknown speaker, like every sibling route
        return sorted(store.read_takes(q.cfg, q.params["slug"]).values(), key=lambda t: t["id"], reverse=True)

    r.add("GET", S + "/takes", list_takes)

    def get_profile(q):
        p = store.get_profile(q.cfg, q.params["slug"])
        if p is None:
            raise ApiError(404, "no profile saved yet")
        return p

    r.add("GET", S + "/profile", get_profile)
    r.add("POST", S + "/profile", lambda q: store.save_profile(q.cfg, q.params["slug"], q.body))
    r.add("POST", S + "/active", lambda q: store.set_active(q.cfg, q.params["slug"]))
    r.add("POST", S + "/design/generate", lambda q: design.generate(q.cfg, q.model, q.params["slug"], q.body))
    r.add("POST", S + "/design/keep", lambda q: design.keep(q.cfg, q.params["slug"], q.body))
    r.add("POST", S + "/design/verdict", lambda q: design.post_verdict(q.cfg, q.params["slug"], q.body))
    r.add("POST", S + "/design/order", lambda q: design.post_order(q.cfg, q.params["slug"], q.body.get("order", []), bool(q.body.get("follow_rank"))))
    r.add("POST", S + "/register", lambda q: design.register_pick(q.cfg, q.params["slug"]))
    r.add("POST", S + "/design/description",
          lambda q: design.post_description(q.cfg, q.params["slug"], q.body.get("description", "")))
    r.add("POST", S + "/clone/generate", lambda q: clone.generate(q.cfg, q.model, q.params["slug"], q.body))
    r.add("POST", S + "/clone/jobs", lambda q: queue(q).submit({**q.body, "kind": "clone", "slug": q.params["slug"]}))
    r.add("POST", S + "/design/jobs", lambda q: queue(q).submit({**q.body, "kind": "design", "slug": q.params["slug"]}))
    r.add("POST", S + "/takes/{id}/fx",
          lambda q: fx.apply_to_take(q.cfg, q.params["slug"], q.params["id"], q.body.get("presets", [])))
    r.add("POST", S + "/takes/{id}/rate", lambda q: clone.rate_take(q.cfg, q.params["slug"], q.params["id"], q.body))
    r.add("GET", "/api/fx/presets", lambda q: fx.list_presets(q.cfg))
    def flag(v):                      # "1"/"0" in a query string; None when absent
        return None if v is None else v not in ("", "0", "false")

    r.add("GET", "/api/pools", lambda q: pools.summary(q.cfg))
    r.add("POST", "/api/pools/rebuild",
          lambda q: pools.rebuild(q.cfg, q.body.get("threshold"), q.body.get("min_slot_lines")))
    r.add("GET", "/api/pools/routes", lambda q: pools.routes_page(
        q.cfg, to=q.query.get("to"), slot=q.query.get("slot"), speaker=q.query.get("speaker"),
        queued=flag(q.query.get("queued")), offset=q.query.get("offset", 0), limit=q.query.get("limit", 100),
        q=q.query.get("q"), conf_lt=q.query.get("conf_lt"), bank=flag(q.query.get("bank")), entry_name=q.query.get("entry_name")))
    r.add("GET", "/api/pools/queue", lambda q: pools.queue(q.cfg))
    r.add("POST", "/api/pools/routes", lambda q: pools.override(q.cfg, q.body))
    r.add("POST", "/api/pools/routes/restore", lambda q: pools.restore_routes(q.cfg, q.body.get("previous")))
    r.add("POST", "/api/pools/slots", lambda q: pools.create_slot(q.cfg, q.body))
    r.add("POST", "/api/pools/slots/{slot}/unmerge", lambda q: pools.unmerge_slot(q.cfg, q.params["slot"]))
    r.add("POST", "/api/pools/slots/{slot}/rename", lambda q: pools.rename_slot(q.cfg, q.params["slot"], q.body.get("name", "")))
    r.add("POST", "/api/pools/slots/{slot}/merge", lambda q: pools.merge_slot(q.cfg, q.params["slot"], q.body.get("into", "")))
    r.add("GET", "/api/pools/spot-check/{slot}", lambda q: pools.spot_check_sample(q.cfg, q.params["slot"], q.query.get("seed")))
    r.add("POST", "/api/pools/spot-check/{slot}",
          lambda q: pools.record_spot_check(q.cfg, q.params["slot"], q.body.get("results", {})))
    L = "/api/lab"
    r.add("GET", L + "/options", lambda q: lab.options())
    r.add("GET", L + "/speakers", lambda q: lab.speakers(q.cfg))
    r.add("GET", L + "/recipes", lambda q: lab.recipes(q.cfg))
    r.add("POST", L + "/recipes", lambda q: lab.save_recipe(q.cfg, q.body))
    r.add("POST", L + "/prepare", lambda q: lab.prepare(q.cfg, q.body))
    r.add("GET", L + "/lexicon", lambda q: lab.lexicon_lookup(q.query.get("q", "")))
    r.add("POST", L + "/opus", lambda q: lab_opus.preview(q.cfg, q.body["wav"], int(q.body["kbps"])))
    r.add("GET", L + "/real-clips", lambda q: lab.real_clips(q.cfg, q.query.get("q", ""), int(q.query.get("limit", lab.REAL_CLIP_LIMIT))))
    r.add("POST", L + "/render", lambda q: lab.start_render(q.cfg, q.model, q.body))
    r.add("GET", L + "/jobs", lambda q: lab.active_jobs())
    r.add("GET", L + "/jobs/{id}", lambda q: lab.get_job(q.params["id"]))
    r.add("POST", L + "/jobs/{id}/cancel", lambda q: lab.cancel_job(q.params["id"]))
    r.add("GET", L + "/{speaker}/lines", lambda q: lab.lines(q.cfg, q.params["speaker"]))
    r.add("GET", L + "/{speaker}/takes", lambda q: lab.takes(q.cfg, q.params["speaker"], q.query.get("guid")))
    r.add("POST", L + "/{speaker}/takes/{id}", lambda q: lab.update_take(q.cfg, q.params["speaker"], q.params["id"], q.body))
    r.add("GET", "/api/fx/library", lambda q: fx_library.library(q.cfg))
    r.add("GET", "/api/fx/labels", lambda q: fx_library.get_labels(q.cfg))
    r.add("POST", "/api/fx/labels", lambda q: fx_library.save_labels(q.cfg, q.body))
    r.add("GET", "/api/fx/assignments/preview", lambda q: fx_library.preview(q.cfg))
    r.add("POST", "/api/fx/assignments", lambda q: fx_library.write(q.cfg))
    r.add("GET", "/api/fx/assignments/diff", lambda q: fx_library.diff(q.cfg))
    r.add("GET", "/api/fx/labels/usage", lambda q: fx_library.usage(q.cfg))
    r.add("GET", "/api/fx/backups", lambda q: fx_library.backups(q.cfg))
    r.add("POST", "/api/fx/restore", lambda q: fx_library.restore(q.cfg, q.body.get("backup", "")))
    r.add("GET", "/api/matches", lambda q: matches.page(
        q.cfg, group=q.query.get("group"), speaker=q.query.get("speaker"), state=q.query.get("state"), q=q.query.get("q"),
        offset=q.query.get("offset", 0), limit=q.query.get("limit", matches.DEFAULT_LIMIT)))
    r.add("POST", "/api/matches/decision", lambda q: matches.save(
        q.cfg, q.body.get("id", ""), q.body.get("value", ""), rebuild=q.body.get("rebuild", True) is not False))
    r.add("POST", "/api/matches/rebuild", lambda q: matches.flush_pools(q.cfg))
    r.add("GET", "/api/casting", lambda q: casting.page(q.cfg))
    r.add("GET", "/api/casting/bg3", lambda q: casting.bg3_voices(q.cfg))
    r.add("POST", "/api/casting/assign", lambda q: casting.assign(q.cfg, q.body["speaker"], q.body.get("bg3")))
    r.add("POST", "/api/casting/portrait", lambda q: casting.set_portrait(q.cfg, q.body["speaker"], q.body.get("portrait")))
    r.add("POST", "/api/casting/audition", lambda q: casting.audition(
        q.cfg, q.model, q.body["speaker"], q.body["bg3"], int(q.body.get("ref", 0)), int(q.body.get("line", 0))))
    r.add("GET", "/api/casting/labels", lambda q: {"schema": bg3_labels.SCHEMA, "progress": bg3_labels.progress(q.cfg, casting.bg3_voices(q.cfg))})
    r.add("POST", "/api/casting/labels", lambda q: bg3_labels.set_label(q.cfg, q.body["slug"], q.body["key"], q.body.get("value")))
    r.add("POST", "/api/casting/labels/backup", lambda q: {"backup": bg3_labels.backup(q.cfg)})
    r.add("POST", "/api/casting/register", lambda q: casting.register(q.cfg))
    r.add("GET", "/api/rtvoices", lambda q: rt_voices.page(q.cfg))
    r.add("POST", "/api/rtvoices/labels", lambda q: rt_voices.set_label(q.cfg, q.body["slug"], q.body["key"], q.body.get("value")))
    r.add("GET", "/api/assignments", lambda q: auto_cast.page(q.cfg))
    r.add("POST", "/api/assignments/run", lambda q: auto_cast.run(q.cfg))
    r.add("POST", "/api/assignments/override", lambda q: auto_cast.override(q.cfg, q.body["key"], q.body.get("bg3")))
    run = lambda q: q.query.get("run") or qa.EXPORT
    r.add("GET", "/api/qa/runs", lambda q: qa.runs(q.cfg))
    r.add("GET", "/api/qa/facets", lambda q: qa.facets(q.cfg, run(q)))
    r.add("GET", "/api/qa/clips", lambda q: qa.page(
        q.cfg, run(q), speaker=q.query.get("speaker"), ref=q.query.get("ref"), engine=q.query.get("engine"),
        flag=q.query.get("flag"), verdict=q.query.get("verdict"), q=q.query.get("q"),
        sort=q.query.get("sort", "suspicious"), seed=q.query.get("seed", 0), exclude=q.query.get("exclude"),
        offset=q.query.get("offset", 0), limit=q.query.get("limit", qa.DEFAULT_LIMIT)))
    r.add("POST", "/api/qa/verdict", lambda q: qa.set_verdict(q.cfg, q.body.get("run") or qa.EXPORT, q.body))
    fresh_pools(r)
    return r


def fresh_pools(r: Router) -> None:
    """Pools reads see matches decisions: a deferred rebuild (matches.save rebuild=false) is flushed before any GET."""
    def wrap(fn):
        def run(q):
            try:
                matches.flush_pools(q.cfg)
            except ApiError:
                pass                      # the read itself reports a real problem; a failed flush must not hide the data
            return fn(q)
        return run
    r._routes = [(m, rx, wrap(fn) if m == "GET" and rx.pattern.startswith("^/api/pools") else fn) for m, rx, fn in r._routes]
