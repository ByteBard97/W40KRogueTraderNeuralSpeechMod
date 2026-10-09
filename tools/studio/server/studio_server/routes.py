from __future__ import annotations

from . import clone, design, fx, fx_library, pools, speakers, store
from .errors import ApiError
from .router import Router


def build_router() -> Router:
    r = Router()
    S = "/api/speakers/{slug}"
    r.add("GET", "/api/model/health", lambda q: {"state": q.model.health()})
    r.add("GET", "/api/speakers", lambda q: speakers.list_speakers(q.cfg))
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
    r.add("POST", S + "/design/order", lambda q: design.post_order(q.cfg, q.params["slug"], q.body.get("order", [])))
    r.add("POST", S + "/register", lambda q: design.register_pick(q.cfg, q.params["slug"]))
    r.add("POST", S + "/design/description",
          lambda q: design.post_description(q.cfg, q.params["slug"], q.body.get("description", "")))
    r.add("POST", S + "/clone/generate", lambda q: clone.generate(q.cfg, q.model, q.params["slug"], q.body))
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
        queued=flag(q.query.get("queued")), offset=q.query.get("offset", 0), limit=q.query.get("limit", 100)))
    r.add("GET", "/api/pools/queue", lambda q: pools.queue(q.cfg))
    r.add("POST", "/api/pools/routes", lambda q: pools.override(q.cfg, q.body))
    r.add("POST", "/api/pools/slots/{slot}/rename", lambda q: pools.rename_slot(q.cfg, q.params["slot"], q.body.get("name", "")))
    r.add("POST", "/api/pools/slots/{slot}/merge", lambda q: pools.merge_slot(q.cfg, q.params["slot"], q.body.get("into", "")))
    r.add("GET", "/api/pools/spot-check/{slot}", lambda q: pools.spot_check_sample(q.cfg, q.params["slot"], q.query.get("seed")))
    r.add("POST", "/api/pools/spot-check/{slot}",
          lambda q: pools.record_spot_check(q.cfg, q.params["slot"], q.body.get("results", {})))
    r.add("GET", "/api/fx/library", lambda q: fx_library.library(q.cfg))
    r.add("GET", "/api/fx/labels", lambda q: fx_library.get_labels(q.cfg))
    r.add("POST", "/api/fx/labels", lambda q: fx_library.save_labels(q.cfg, q.body))
    r.add("GET", "/api/fx/assignments/preview", lambda q: fx_library.preview(q.cfg))
    r.add("POST", "/api/fx/assignments", lambda q: fx_library.write(q.cfg))
    return r
