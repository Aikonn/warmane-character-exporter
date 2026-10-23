from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .checkpoint import ProbeCheckpointStore
from .http_client import UrllibHttpClient
from .identity import parse_character_url
from .transport import RequestOrchestrator, TransportConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Warmane Milestone 0 probe")
    parser.add_argument("url", help="Warmane character URL")
    parser.add_argument(
        "--checkpoint",
        default=".warmane-probe-checkpoint.json",
        help="Path to local probe checkpoint JSON file",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute one live GET request. Without this flag, no network request is made.",
    )
    parser.add_argument(
        "--live-once",
        action="store_true",
        help="Live mode with one HTTP attempt: no retries and no redirect following.",
    )
    return parser


def _config_dict(config: TransportConfig) -> dict[str, object]:
    return {
        "min_request_interval_seconds": config.min_request_interval_seconds,
        "connect_timeout_seconds": config.connect_timeout_seconds,
        "read_timeout_seconds": config.read_timeout_seconds,
        "max_rate_limit_retries": config.max_rate_limit_retries,
        "max_transient_retries": config.max_transient_retries,
        "cooldown_schedule_seconds": list(config.cooldown_schedule_seconds),
        "jitter_ratio": config.jitter_ratio,
    }


def main() -> None:
    args = build_parser().parse_args()
    if args.live and args.live_once:
        raise SystemExit("Use either --live or --live-once, not both.")

    if args.live_once:
        live_mode = "live_once"
        config = TransportConfig(
            max_rate_limit_retries=0,
            max_transient_retries=0,
        )
    else:
        live_mode = "live" if args.live else "offline_plan"
        config = TransportConfig()

    identity = parse_character_url(args.url)
    checkpoint = ProbeCheckpointStore(path=Path(args.checkpoint))
    orchestrator = RequestOrchestrator(checkpoint=checkpoint, config=config)

    host = (urlparse(identity.request_url).hostname or "").lower()
    output = {
        "mode": live_mode,
        "identity": {
            "name": identity.name,
            "realm": identity.realm,
            "input_url": identity.input_url,
            "request_url": identity.request_url,
            "canonical_url": identity.canonical_url,
        },
        "first_request": {
            "method": "GET",
            "url": identity.request_url,
            "host": host,
        },
        "safeguards": _config_dict(config),
        "http_client_limits": {
            "follows_redirects": False,
            "max_body_bytes": 131072,
            "timeout_mode": "single socket timeout from urllib (max(connect_timeout, read_timeout))",
        },
        "checkpoint_path": str(Path(args.checkpoint).resolve()),
    }

    if not args.live and not args.live_once:
        print(json.dumps(output, indent=2))
        return

    if args.live_once:
        cooldown_until = checkpoint.get_cooldown_until(host)
        now = datetime.now(tz=timezone.utc).timestamp()
        if cooldown_until is not None and cooldown_until > now:
            output["result"] = {
                "status": "blocked_by_cooldown",
                "detail": "Existing cooldown prevents request in live-once mode.",
                "cooldown_until_unix": cooldown_until,
                "seconds_remaining": cooldown_until - now,
            }
            print(json.dumps(output, indent=2))
            return

    result = orchestrator.execute_single_request(url=identity.request_url, client=UrllibHttpClient(max_body_bytes=131072))
    headers = result.response_headers or {}
    content_type = headers.get("Content-Type")
    retry_after = headers.get("Retry-After")
    location = headers.get("Location")
    character_detected, evidence = _detect_character_content(result.body_text, identity.name, identity.realm)

    evidence_path = _save_sanitized_evidence(
        status=result.response_status,
        headers=headers,
        body=result.body_text,
        body_truncated=result.body_truncated,
        body_bytes_captured=result.body_bytes_captured,
    )

    output["result"] = {
        "status": result.status,
        "detail": result.detail,
        "attempts": result.attempts,
        "classification": result.classification,
        "response_status": result.response_status,
        "skipped": result.skipped,
        "body_truncated": result.body_truncated,
        "body_bytes_captured": result.body_bytes_captured,
        "content_type": content_type,
        "location": location,
        "retry_after": retry_after,
        "transport_error": result.transport_error,
        "character_content_detected": character_detected,
        "character_detection_evidence": evidence,
        "sanitized_evidence_path": str(evidence_path.resolve()),
    }
    print(json.dumps(output, indent=2))


def _detect_character_content(body: str, name: str, realm: str) -> tuple[bool, list[str]]:
    if not body:
        return False, ["empty response body"]

    lower = body.lower()
    evidence: list[str] = []
    if "<html" in lower:
        evidence.append("contains <html")
    if "character" in lower:
        evidence.append("contains 'character'")
    if name.lower() in lower:
        evidence.append(f"contains character name '{name}'")
    if realm.lower() in lower:
        evidence.append(f"contains realm '{realm}'")
    if "error 1015" in lower:
        evidence.append("contains error marker 'Error 1015'")
    if "you are being rate limited" in lower:
        evidence.append("contains rate-limit marker text")

    looks_like_error = any("error marker" in item or "rate-limit marker" in item for item in evidence)
    recognized = ("contains character name" in " ".join(evidence)) and ("contains realm" in " ".join(evidence)) and not looks_like_error
    return recognized, evidence


def _save_sanitized_evidence(
    status: int | None,
    headers: dict[str, str],
    body: str,
    body_truncated: bool,
    body_bytes_captured: int,
) -> Path:
    out_dir = Path("tests") / "fixtures" / "captures"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "last-live-response-sanitized.json"

    sanitized_headers = {}
    for key, value in headers.items():
        if key.lower() in {"set-cookie", "cookie", "authorization"}:
            continue
        sanitized_headers[key] = value

    sanitized_body = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<redacted-ip>", body)
    payload = {
        "status": status,
        "headers": sanitized_headers,
        "body_truncated": body_truncated,
        "body_bytes_captured": body_bytes_captured,
        "body_text": sanitized_body,
        "synthetic": False,
        "sanitized_note": "Cookies/auth headers removed; IPv4 addresses redacted.",
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    main()
