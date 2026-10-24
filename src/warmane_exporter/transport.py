from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from random import random
from time import sleep, time
from typing import Callable
from urllib.parse import urlparse

from .checkpoint import ProbeCheckpointStore
from .http_client import HttpResponse
from .retry_after import parse_retry_after_seconds


RATE_LIMIT_MARKERS = (
    "error 1015",
    "you are being rate limited",
    "too many requests",
)
CLIENT_SIGNATURE_BLOCK_MARKERS = (
    "error code: 1010",
    "access denied",
)


@dataclass(frozen=True)
class TransportConfig:
    min_request_interval_seconds: float = 1.0
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    max_rate_limit_retries: int = 3
    max_transient_retries: int = 2
    cooldown_schedule_seconds: tuple[int, ...] = (60, 120, 240)
    jitter_ratio: float = 0.2


@dataclass(frozen=True)
class RequestResult:
    status: str
    detail: str
    attempts: int
    classification: str | None = None
    response_status: int | None = None
    skipped: bool = False
    response_headers: dict[str, str] | None = None
    body_truncated: bool = False
    body_bytes_captured: int = 0
    body_text: str = ""
    transport_error: str | None = None


@dataclass
class RequestOrchestrator:
    checkpoint: ProbeCheckpointStore
    config: TransportConfig = field(default_factory=TransportConfig)
    now_fn: Callable[[], float] = time
    sleep_fn: Callable[[float], None] = sleep
    random_fn: Callable[[], float] = random
    skip_completed: bool = True
    _last_request_time_by_host: dict[str, float] = field(default_factory=dict)

    def execute_single_request(
        self,
        url: str,
        client,
        form: dict[str, str] | None = None,
        referer: str | None = None,
    ) -> RequestResult:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            raise ValueError("URL host is required.")

        if form is None:
            request_key = f"GET {url}"
        else:
            request_key = f"POST {url} " + "&".join(f"{k}={v}" for k, v in sorted(form.items()))
        if self.skip_completed and self.checkpoint.is_completed(request_key):
            return RequestResult(
                status="skipped_completed",
                detail="Request was already completed in checkpoint.",
                attempts=0,
                classification="skipped_completed",
                skipped=True,
            )

        rate_retries = 0
        transient_retries = 0
        attempts = 0

        while True:
            attempts += 1
            self._apply_waits(host)
            response = self._post(client, url, form, referer) if form is not None else client.get(
                url=url,
                connect_timeout=self.config.connect_timeout_seconds,
                read_timeout=self.config.read_timeout_seconds,
            )
            self._last_request_time_by_host[host] = self.now_fn()

            classification = classify_response(response)
            if classification == "success":
                self.checkpoint.mark_completed(request_key=request_key, status="success")
                return RequestResult(
                    status="success",
                    detail="Successful response.",
                    attempts=attempts,
                    classification=classification,
                    response_status=response.status_code,
                    response_headers=response.headers,
                    body_truncated=response.body_truncated,
                    body_bytes_captured=response.body_bytes_captured,
                    body_text=response.body_text,
                )

            if classification == "rate_limited":
                delay_seconds = self._compute_rate_limit_delay(response=response, retry_index=rate_retries)
                self._set_host_cooldown(host=host, delay_seconds=delay_seconds)
                if rate_retries >= self.config.max_rate_limit_retries:
                    return RequestResult(
                        status="failed_rate_limited",
                        detail="Rate-limit retry budget exhausted.",
                        attempts=attempts,
                        classification=classification,
                        response_status=response.status_code,
                        response_headers=response.headers,
                        body_truncated=response.body_truncated,
                        body_bytes_captured=response.body_bytes_captured,
                        body_text=response.body_text,
                        transport_error=response.transport_error,
                    )

                rate_retries += 1
                continue

            if classification == "transient_error":
                if transient_retries >= self.config.max_transient_retries:
                    return RequestResult(
                        status="failed_transient",
                        detail="Transient retry budget exhausted.",
                        attempts=attempts,
                        classification=classification,
                        response_status=response.status_code,
                        response_headers=response.headers,
                        body_truncated=response.body_truncated,
                        body_bytes_captured=response.body_bytes_captured,
                        body_text=response.body_text,
                        transport_error=response.transport_error,
                    )

                delay_seconds = self._compute_transient_delay(transient_retries)
                self.sleep_fn(delay_seconds)
                transient_retries += 1
                continue

            return RequestResult(
                status=(
                    "failed_redirect"
                    if classification == "redirect"
                    else "failed_client_signature_blocked"
                    if classification == "client_signature_blocked"
                    else "failed_permanent"
                ),
                detail=(
                    "Redirect response received."
                    if classification == "redirect"
                    else "Client signature blocked (Cloudflare 1010 style access denial)."
                    if classification == "client_signature_blocked"
                    else "Non-retriable response."
                ),
                attempts=attempts,
                classification=classification,
                response_status=response.status_code,
                response_headers=response.headers,
                body_truncated=response.body_truncated,
                body_bytes_captured=response.body_bytes_captured,
                body_text=response.body_text,
                transport_error=response.transport_error,
            )

    def _post(self, client, url: str, form: dict[str, str], referer: str | None) -> HttpResponse:
        return client.post_form(
            url=url,
            form=form,
            connect_timeout=self.config.connect_timeout_seconds,
            read_timeout=self.config.read_timeout_seconds,
            referer=referer,
        )

    def _apply_waits(self, host: str) -> None:
        now = self.now_fn()
        cooldown_until = self.checkpoint.get_cooldown_until(host)
        if cooldown_until is not None and cooldown_until > now:
            self.sleep_fn(cooldown_until - now)
            now = self.now_fn()

        last = self._last_request_time_by_host.get(host)
        if last is None:
            return
        elapsed = now - last
        remaining = self.config.min_request_interval_seconds - elapsed
        if remaining > 0:
            self.sleep_fn(remaining)

    def _compute_rate_limit_delay(self, response: HttpResponse, retry_index: int) -> float:
        retry_after_seconds = parse_retry_after_seconds(
            value=response.headers.get("Retry-After"),
            now_utc=datetime.now(tz=timezone.utc),
        )
        fallback = self._fallback_cooldown_delay(retry_index)
        if retry_after_seconds is None:
            return fallback
        return max(float(retry_after_seconds), fallback)

    def _fallback_cooldown_delay(self, retry_index: int) -> float:
        base = self.config.cooldown_schedule_seconds[min(retry_index, len(self.config.cooldown_schedule_seconds) - 1)]
        jitter = base * self.config.jitter_ratio * self.random_fn()
        return base + jitter

    def _compute_transient_delay(self, retry_index: int) -> float:
        base = 1 * (2**retry_index)
        jitter = base * self.config.jitter_ratio * self.random_fn()
        return base + jitter

    def _set_host_cooldown(self, host: str, delay_seconds: float) -> None:
        cooldown_until = self.now_fn() + max(0.0, delay_seconds)
        self.checkpoint.set_cooldown_until(host=host, unix_time=cooldown_until)


def classify_response(response: HttpResponse) -> str:
    status = response.status_code
    if status == 0:
        return "transient_error"
    body_lower = response.body_text.lower()
    has_client_signature_block_marker = any(marker in body_lower for marker in CLIENT_SIGNATURE_BLOCK_MARKERS)
    if status == 403 and has_client_signature_block_marker:
        return "client_signature_blocked"

    has_rate_marker = any(marker in body_lower for marker in RATE_LIMIT_MARKERS)
    if status == 429:
        return "rate_limited"
    if status == 403 and has_rate_marker:
        return "rate_limited"
    if status == 200 and has_rate_marker:
        return "rate_limited"

    if 300 <= status < 400:
        return "redirect"
    if 200 <= status < 300:
        return "success"
    if status in (408, 425, 500, 502, 503, 504):
        return "transient_error"
    if 400 <= status < 500:
        return "permanent_error"
    if status >= 500:
        return "transient_error"
    return "permanent_error"
