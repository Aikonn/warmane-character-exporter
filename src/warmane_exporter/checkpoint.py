from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProbeCheckpoint:
    cooldowns: dict[str, float] = field(default_factory=dict)
    completed_requests: dict[str, dict[str, str]] = field(default_factory=dict)


class ProbeCheckpointStore:
    """
    Lightweight JSON checkpoint for Milestone 0 probe only.

    Limitations:
    - Single-process optimistic writes (no locking).
    - No TTL/index strategy.
    - No canonical source/data namespace separation yet.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.state = self._load()

    def _load(self) -> ProbeCheckpoint:
        if not self.path.exists():
            return ProbeCheckpoint()

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        cooldowns = raw.get("cooldowns", {})
        completed_requests = raw.get("completed_requests", {})
        if not isinstance(cooldowns, dict) or not isinstance(completed_requests, dict):
            raise ValueError("Checkpoint file is malformed.")

        return ProbeCheckpoint(
            cooldowns={str(k): float(v) for k, v in cooldowns.items()},
            completed_requests={str(k): dict(v) for k, v in completed_requests.items()},
        )

    def save(self) -> None:
        payload = {
            "cooldowns": self.state.cooldowns,
            "completed_requests": self.state.completed_requests,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def get_cooldown_until(self, host: str) -> float | None:
        return self.state.cooldowns.get(host)

    def set_cooldown_until(self, host: str, unix_time: float) -> None:
        self.state.cooldowns[host] = unix_time
        self.save()

    def is_completed(self, request_key: str) -> bool:
        return request_key in self.state.completed_requests

    def mark_completed(self, request_key: str, status: str) -> None:
        self.state.completed_requests[request_key] = {"status": status}
        self.save()
