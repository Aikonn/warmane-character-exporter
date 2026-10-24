from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .checkpoint import ProbeCheckpointStore
from .http_client import UrllibHttpClient
from .transport import RequestOrchestrator, TransportConfig


APPROVED_HOSTS = {
    "wotlk.cavernoftime.com",
    "wotlk.evowow.com",
}

# Positive integers: [1-9][0-9]*
# Nonnegative gem codes: [0-9]+(?::[0-9]+)* (allows 0, allows zero-separated sequences)
CAVERNOFTIME_PATTERNS = [
    r"^/spell=([1-9][0-9]*)$",
    r"^/spell=([1-9][0-9]*)&power=true$",
    r"^/item=([1-9][0-9]*)$",
    r"^/item=([1-9][0-9]*)&power=true$",
    r"^/item=([1-9][0-9]*)&power=true&ench=([1-9][0-9]*)$",
    r"^/item=([1-9][0-9]*)&power=true&gems=(?:[0-9]+(?::[0-9]+)*)$",
    r"^/item=([1-9][0-9]*)&power=true&ench=([1-9][0-9]*)&gems=(?:[0-9]+(?::[0-9]+)*)$",
]

EVOWOW_PATTERN = r"^/?\?enchantment=([1-9][0-9]*)$"


def validate_definition_url(url: str) -> str:
    """
    Validate and normalize a definition-source URL.
    
    Returns the normalized URL (https://<host><path><query>).
    Raises ValueError if URL is invalid or not approved.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")
    
    # Validate ORIGINAL string before any normalization
    for char in url:
        if char in (' ', '\t', '\n', '\r', '\v', '\f') or ord(char) < 32 or ord(char) == 127:
            raise ValueError("URL contains whitespace or control characters.")
    
    parsed = urlparse(url)
    
    # Reject scheme-less URLs (after pre-validation)
    if not parsed.scheme:
        raise ValueError("URL must include an explicit https:// scheme.")
    
    if parsed.scheme != "https":
        raise ValueError("Only https URLs are supported.")
    
    host = (parsed.hostname or "").lower()
    if host not in APPROVED_HOSTS:
        raise ValueError(f"Unsupported host: {parsed.hostname!r}. Approved hosts: {', '.join(sorted(APPROVED_HOSTS))}.")
    
    if parsed.port is not None:
        raise ValueError("Non-default ports are not allowed.")
    
    if parsed.username or parsed.password:
        raise ValueError("Credentials are not allowed in URLs.")
    
    if parsed.fragment:
        raise ValueError("URL fragments are not allowed.")
    
    # Reject params (semicolon suffixes)
    if parsed.params:
        raise ValueError("URL parameters (semicolon-separated) are not allowed.")
    
    path = parsed.path or ""
    query = parsed.query or ""
    
    if not path and not query:
        raise ValueError("URL must include a path or query.")
    
    combined = path
    if query:
        combined = f"{path}?{query}"
    
    # Check for control characters (before regex validation so we catch them cleanly)
    for char in combined:
        if char in (' ', '\t', '\n', '\r', '\v', '\f') or ord(char) < 32 or ord(char) == 127:
            raise ValueError(f"URL contains whitespace or control characters.")
    
    if host == "wotlk.cavernoftime.com":
        if not any(re.fullmatch(pattern, combined) for pattern in CAVERNOFTIME_PATTERNS):
            raise ValueError(f"Unsupported Cavernoftime path/query form: {combined!r}.")
    elif host == "wotlk.evowow.com":
        if not re.fullmatch(EVOWOW_PATTERN, combined):
            raise ValueError(f"Unsupported EvoWoW path/query form: {combined!r}.")
    
    normalized_url = f"https://{host}{combined}"
    return normalized_url


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


def _truncate_body_excerpt(body: str, max_chars: int = 500) -> str:
    if len(body) > max_chars:
        return body[:max_chars]
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmane definition-source diagnostic")
    parser.add_argument("url", help="Definition-source URL (Cavernoftime or EvoWoW)")
    parser.add_argument(
        "--live-once",
        action="store_true",
        help="Execute one live HTTP GET with zero retries. Without this flag, no network request is made.",
    )
    parser.add_argument(
        "--checkpoint",
        default=".warmane-probe-checkpoint.json",
        help="Path to local probe checkpoint JSON file",
    )
    
    args = parser.parse_args()
    
    try:
        validated_url = validate_definition_url(args.url)
    except ValueError as exc:
        output = {
            "mode": "offline_validation",
            "input_url": args.url,
            "validation_error": str(exc),
        }
        print(json.dumps(output, indent=2))
        return
    
    parsed = urlparse(validated_url)
    host = (parsed.hostname or "").lower()
    
    config = TransportConfig(
        max_rate_limit_retries=0,
        max_transient_retries=0,
    )
    checkpoint = ProbeCheckpointStore(path=Path(args.checkpoint))
    
    output = {
        "mode": "live_once" if args.live_once else "offline_plan",
        "validated_url": validated_url,
        "host": host,
        "safeguards": _config_dict(config),
        "http_client_limits": {
            "follows_redirects": False,
            "max_body_bytes": 131072,
            "timeout_mode": "single socket timeout from urllib (max(connect_timeout, read_timeout))",
        },
        "checkpoint_path": str(Path(args.checkpoint).resolve()),
    }
    
    if not args.live_once:
        print(json.dumps(output, indent=2))
        return
    
    cooldown_until = checkpoint.get_cooldown_until(host)
    now = datetime.now(tz=timezone.utc).timestamp()
    if cooldown_until is not None and cooldown_until > now:
        output["result"] = {
            "status": "blocked_by_cooldown",
            "detail": "Existing cooldown prevents request.",
            "cooldown_until_unix": cooldown_until,
            "seconds_remaining": cooldown_until - now,
        }
        print(json.dumps(output, indent=2))
        return
    
    orchestrator = RequestOrchestrator(checkpoint=checkpoint, config=config)
    result = orchestrator.execute_single_request(url=validated_url, client=UrllibHttpClient(max_body_bytes=131072))
    
    headers = result.response_headers or {}
    content_type = headers.get("Content-Type")
    
    body_excerpt = _truncate_body_excerpt(result.body_text, max_chars=500)
    
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
        "transport_error": result.transport_error,
        "body_excerpt": body_excerpt,
    }
    
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
