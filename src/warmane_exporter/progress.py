"""Progress lines for the launcher window.

When the environment variable WARMANE_PROGRESS is set, steps print lines of the form
PROGRESS|<percent>|<text> (flushed at once) that the launcher shows. Without it nothing is printed.
Progress is counted in units: one per page or statistics/achievement category fetched, one for the export.
"""

from __future__ import annotations

import os

_state = {"total": 0, "done": 0}


def enabled() -> bool:
    return bool(os.environ.get("WARMANE_PROGRESS"))


def percent() -> int:
    total = _state["total"]
    return 0 if total <= 0 else min(100, int(100 * _state["done"] / total))


def _emit(text: str) -> None:
    if enabled():
        print(f"PROGRESS|{percent()}|{text}", flush=True)


def start(total_units: int, text: str = "Starting") -> None:
    _state["total"], _state["done"] = max(total_units, 0), 0
    _emit(text)


def note(text: str) -> None:
    """Announce what is happening now without counting a finished unit."""
    _emit(text)


def advance(text: str, units: int = 1) -> None:
    """Count finished units and announce the next thing or the result."""
    _state["done"] += units
    _emit(text)
