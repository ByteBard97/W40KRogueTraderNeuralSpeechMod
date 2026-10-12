"""Wait for enough free GPU memory before starting a stage (the GPU is shared with games etc.)."""
from __future__ import annotations

import subprocess
import time
from typing import Callable


def free_vram_mb() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, check=True).stdout
    return parse_free_mb(out)


def parse_free_mb(nvidia_smi_output: str) -> int:
    """First GPU's free MiB from `--query-gpu=memory.free --format=csv,noheader,nounits`."""
    lines = [x.strip() for x in nvidia_smi_output.splitlines() if x.strip()]
    if not lines:
        raise ValueError("empty nvidia-smi output")
    return int(lines[0])


def wait_for_free(need_mb: int, poll_s: float = 30.0, timeout_s: float | None = None,
                  read: Callable[[], int] = free_vram_mb, sleep: Callable[[float], None] = time.sleep,
                  clock: Callable[[], float] = time.monotonic) -> bool:
    """Block until `need_mb` is free. Returns False if timeout_s elapses first."""
    start = clock()
    while read() < need_mb:
        if timeout_s is not None and clock() - start >= timeout_s:
            return False
        sleep(poll_s)
    return True
