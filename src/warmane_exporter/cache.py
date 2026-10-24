"""Small SQLite response cache.

Only validated content is stored (the caller validates before put). Error pages
must never be passed to put(), so they cannot replace valid entries.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

MAX_BODY_CHARS = 2_000_000


@dataclass(frozen=True)
class CacheEntry:
    key: str
    source: str
    body: str
    fetched_at: float
    sha256: str

    def age_seconds(self, now: float) -> float:
        return max(0.0, now - self.fetched_at)


class ResponseCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            "key TEXT PRIMARY KEY, source TEXT NOT NULL, body TEXT NOT NULL, "
            "fetched_at REAL NOT NULL, sha256 TEXT NOT NULL)"
        )
        self._db.commit()

    def get(self, key: str) -> CacheEntry | None:
        row = self._db.execute(
            "SELECT key, source, body, fetched_at, sha256 FROM responses WHERE key = ?", (key,)
        ).fetchone()
        return CacheEntry(*row) if row else None

    def put(self, key: str, source: str, body: str, fetched_at: float) -> None:
        if len(body) > MAX_BODY_CHARS:
            raise ValueError("Body exceeds the cache size limit.")
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        self._db.execute(
            "INSERT OR REPLACE INTO responses (key, source, body, fetched_at, sha256) VALUES (?, ?, ?, ?, ?)",
            (key, source, body, fetched_at, digest),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()
