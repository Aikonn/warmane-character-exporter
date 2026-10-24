"""Local Library of static reference pages (items, gems, enchants, spells ...).

Anything fetched from outside the character armory pages is stored here once and reused for
every later parse; nothing is fetched twice unless the fetch mechanism itself changes
(then bump the version string and the old files stay for comparison).

Layout: library/<kind>/<key>.<ext> plus library/index.jsonl (one metadata line per file:
url, fetched_at, sha256, bytes, version).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Callable

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


class Library:
    def __init__(self, root: Path, version: str = "v1", now: Callable[[], float] = time.time):
        self.root, self.version, self._now = Path(root), version, now

    def _path(self, kind: str, key: str, ext: str) -> Path:
        return self.root / _SAFE.sub("_", kind) / f"{_SAFE.sub('_', str(key))}.{ext.lstrip('.')}"

    def has(self, kind: str, key: str, ext: str = "html") -> bool:
        return self._path(kind, key, ext).exists()

    def get(self, kind: str, key: str, ext: str = "html") -> str | None:
        path = self._path(kind, key, ext)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def put(self, kind: str, key: str, text: str, url: str, ext: str = "html") -> Path:
        path = self._path(kind, key, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        meta = {
            "kind": kind, "key": str(key), "url": url, "fetched_at": self._now(),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "bytes": len(text.encode("utf-8")), "version": self.version,
        }
        with (self.root / "index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(meta) + "\n")
        return path

    def get_or_fetch(self, kind: str, key: str, url: str, fetch: Callable[[str], str], ext: str = "html") -> tuple[str, bool]:
        """Return (text, fetched_live). fetch(url) must return the body text and is called only on a miss."""
        cached = self.get(kind, key, ext)
        if cached is not None:
            return cached, False
        text = fetch(url)
        self.put(kind, key, text, url, ext)
        return text, True
