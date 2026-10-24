from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

# One fixed, browser-compatible header set. Verified 2026-10-24: the default
# Python User-Agent is rejected by Cloudflare (error 1010), this one is accepted.
# The header set is constant on purpose: no User-Agent rotation or other evasion.
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    body_text: str
    body_truncated: bool = False
    transport_error: str | None = None
    body_bytes_captured: int = 0


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):  # type: ignore[override]
        return None


class UrllibHttpClient:
    """
    urllib uses one socket timeout value for connect/read operations.
    This client therefore applies a single timeout budget for both phases.
    """

    def __init__(self, max_body_bytes: int = 131072, headers: dict[str, str] | None = None) -> None:
        if max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive.")
        self.max_body_bytes = max_body_bytes
        self.headers = dict(DEFAULT_HEADERS if headers is None else headers)
        self._opener = build_opener(NoRedirectHandler())

    def get(self, url: str, connect_timeout: float, read_timeout: float) -> HttpResponse:
        request = Request(url=url, method="GET", headers=self.headers)
        return self._send(request, max(connect_timeout, read_timeout))

    def post_form(
        self,
        url: str,
        form: dict[str, str],
        connect_timeout: float,
        read_timeout: float,
        referer: str | None = None,
    ) -> HttpResponse:
        """POST url-encoded form data the way the armory page scripts do (XMLHttpRequest)."""
        headers = dict(self.headers)
        headers["Accept"] = "application/json,*/*;q=0.8"
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Origin"] = "https://armory.warmane.com"
        if referer:
            headers["Referer"] = referer
        request = Request(
            url=url,
            data=urlencode(form).encode("utf-8"),
            method="POST",
            headers=headers,
        )
        return self._send(request, max(connect_timeout, read_timeout))

    def _send(self, request: Request, timeout: float) -> HttpResponse:
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw_body = response.read(self.max_body_bytes + 1)
                body_truncated = len(raw_body) > self.max_body_bytes
                if body_truncated:
                    raw_body = raw_body[: self.max_body_bytes]
                charset = response.headers.get_content_charset() or "utf-8"
                body = raw_body.decode(charset, errors="replace")
                headers = {k: v for k, v in response.headers.items()}
                return HttpResponse(
                    status_code=response.status,
                    headers=headers,
                    body_text=body,
                    body_truncated=body_truncated,
                    body_bytes_captured=len(raw_body),
                )
        except HTTPError as exc:
            raw_body = exc.read(self.max_body_bytes + 1)
            body_truncated = len(raw_body) > self.max_body_bytes
            if body_truncated:
                raw_body = raw_body[: self.max_body_bytes]
            charset = exc.headers.get_content_charset() or "utf-8"
            body = raw_body.decode(charset, errors="replace")
            headers = {k: v for k, v in exc.headers.items()}
            return HttpResponse(
                status_code=exc.code,
                headers=headers,
                body_text=body,
                body_truncated=body_truncated,
                body_bytes_captured=len(raw_body),
            )
        except URLError as exc:
            return HttpResponse(
                status_code=0,
                headers={},
                body_text="",
                transport_error=str(exc.reason),
                body_bytes_captured=0,
            )
