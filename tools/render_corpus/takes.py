"""Which take of a piece the stitcher uses: its own, else its redo takes (cast_followup.py), first usable wins. No audio libraries needed."""
MAX_REDO = 3          # redo takes "<guid>@r1" .. "<guid>@r3"


def redo_guid(guid: str, k: int) -> str:
    return f"{guid}@r{k}"


def fix_guid(guid: str) -> str:
    """A take re-planned with the true speaker (plan_cast_fix.py); it beats every other take of the piece."""
    return f"{guid}@fix"


def pick(job: dict, segs: dict) -> str | None:
    """The guid of the first usable take for a piece (`segs` is keyed by take guid): the fix take, else its own, else its redo takes. None if none."""
    return next((g for g in (fix_guid(job["guid"]), job["guid"], *(redo_guid(job["guid"], k) for k in range(1, MAX_REDO + 1))) if g in segs), None)
