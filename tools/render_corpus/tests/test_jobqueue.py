import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobqueue import JobQueue  # noqa: E402


def J(g, engine="voxcpm2", priority=1):
    return {"guid": g, "engine": engine, "priority": priority}


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def test_leases_by_priority_then_guid_and_engine():
    q = JobQueue([J("b"), J("a"), J("z", priority=0), J("q", engine="qwen3_tts")])
    assert [j["guid"] for j in q.lease("w1", "voxcpm2", 3)] == ["z", "a", "b"]
    assert [j["guid"] for j in q.lease("w2", "qwen3_tts")] == ["q"]


def test_leased_jobs_are_not_given_twice_until_the_lease_expires():
    c = Clock()
    q = JobQueue([J("a"), J("b")], lease_s=60, clock=c)
    assert [j["guid"] for j in q.lease("w1", "voxcpm2", 1)] == ["a"]
    assert [j["guid"] for j in q.lease("w2", "voxcpm2", 2)] == ["b"]
    c.t += 61
    assert [j["guid"] for j in q.lease("w2", "voxcpm2", 2)] == ["a", "b"]


def test_done_and_resume():
    q = JobQueue([J("a"), J("b")], done={"a"})
    assert [j["guid"] for j in q.lease("w", "voxcpm2", 5)] == ["b"]
    q.complete("b", "w", ok=True, audio_s=12.0)
    assert q.lease("w", "voxcpm2", 5) == []
    assert q.status()["done"] == 2


def test_failures_retry_then_give_up():
    q = JobQueue([J("a")])
    for _ in range(2):
        assert q.lease("w", "voxcpm2")
        q.complete("a", "w", ok=False)
    assert q.lease("w", "voxcpm2") == []
    s = q.status()
    assert s["gave_up"] == 1 and s["pending"] == 0


def test_max_priority_filter_and_status_counts():
    q = JobQueue([J("a", priority=1), J("b", priority=3)], max_priority=2)
    assert q.status()["total"] == 1
    q.lease("w", "voxcpm2")
    assert q.status()["leased"] == 1 and q.status()["pending"] == 0


def test_renew_extends_only_that_workers_leases():
    c = Clock()
    q = JobQueue([J("a"), J("b")], lease_s=60, clock=c)
    q.lease("w1", "voxcpm2", 1)
    q.lease("w2", "voxcpm2", 1)
    c.t += 50
    q.renew("w1")
    c.t += 20
    assert [j["guid"] for j in q.lease("w3", "voxcpm2", 2)] == ["b"]


def S(parent, k, priority):
    return {"guid": f"{parent}~{k}", "parent": parent, "seg_index": k, "engine": "voxcpm2", "priority": priority}


def test_segments_of_one_cue_are_served_together_so_the_cue_can_be_stitched():
    jobs = [S("b", 0, 2), S("b", 1, 1), S("a", 0, 1), S("a", 1, 2), J("c", priority=0), J("d", priority=2)]
    q = JobQueue(jobs)
    order = [j["guid"] for j in q.lease("w", "voxcpm2", 10)]
    assert order == ["c", "a~0", "a~1", "b~0", "b~1", "d"]
