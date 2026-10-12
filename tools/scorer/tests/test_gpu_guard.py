import pytest

from gpu_guard import parse_free_mb, wait_for_free


def test_parse():
    assert parse_free_mb("8123\n") == 8123
    assert parse_free_mb("8123\n2000\n") == 8123
    with pytest.raises(ValueError):
        parse_free_mb("\n")


def test_wait_returns_when_free():
    seq = iter([100, 100, 5000])
    slept = []
    assert wait_for_free(4000, read=lambda: next(seq), sleep=slept.append, poll_s=7)
    assert slept == [7, 7]


def test_wait_times_out():
    t = [0.0]
    def sleep(s): t[0] += s
    assert wait_for_free(4000, timeout_s=50, poll_s=30, read=lambda: 0, sleep=sleep, clock=lambda: t[0]) is False
