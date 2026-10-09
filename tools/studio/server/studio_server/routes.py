from __future__ import annotations

from . import clone, design, fx, speakers, store
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
    return r
