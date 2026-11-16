"""Optional timing output shared by roster orchestration and its in-process steps."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Iterator


class TimingLog:
    def __init__(self, cache_dir: Path) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        self.path = cache_dir / f"timing-{stamp}.log"
        self.totals: dict[str, float] = {}

    def record(self, label: str, duration: float) -> None:
        self.totals[label] = self.totals.get(label, 0.0) + duration
        line = f"TIMING {label}: {duration:.3f}s"
        print(line, file=sys.stderr, flush=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")


_active_log: ContextVar[TimingLog | None] = ContextVar("warmane_timing_log", default=None)


def timing_requested(explicit: bool = False) -> bool:
    return explicit or os.environ.get("WARMANE_TIMING") == "1"


@contextmanager
def activate(log: TimingLog | None) -> Iterator[None]:
    token = _active_log.set(log)
    try:
        yield
    finally:
        _active_log.reset(token)


def timing_active() -> bool:
    return _active_log.get() is not None


def timing_total(label: str) -> float:
    log = _active_log.get()
    return log.totals.get(label, 0.0) if log is not None else 0.0


def record_timing(label: str, duration: float) -> None:
    log = _active_log.get()
    if log is not None:
        log.record(label, duration)


@contextmanager
def timed(label: str) -> Iterator[None]:
    if not timing_active():
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        record_timing(label, perf_counter() - started)
