"""Milestone 0 probe: can a plain Python HTTP client reach the Warmane armory?

Makes exactly 3 requests, 15 seconds apart, for one character:
summary page (GET), talents page (GET), achievements category 92 (POST).
Usage: python scripts/probe_plain_http.py
"""

import time
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
BASE = "https://armory.warmane.com/character/Aikka/Onyxia/"


def go(label, url, data=None, extra=None):
    headers = {
        "User-Agent": UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,*/*" if data is None else "application/json,*/*",
    }
    if extra:
        headers.update(extra)
    try:
        response = urllib.request.urlopen(
            urllib.request.Request(url, data=data, headers=headers), timeout=30
        )
        body = response.read().decode("utf-8", "replace")
        print(
            label,
            response.status,
            "bytes=%d" % len(body),
            "item_rel=%d" % body.count('rel="item='),
            "data-spec=%d" % body.count("data-spec"),
            "content_key=%s" % ('"content"' in body),
        )
    except Exception as exc:  # report and continue
        detail = getattr(exc, "read", lambda: b"")()[:120]
        print(label, "FAIL", exc, detail)


go("summary", BASE + "summary")
time.sleep(15)
go("talents", BASE + "talents")
time.sleep(15)
go(
    "achievements-post-92",
    BASE + "achievements",
    urllib.parse.urlencode({"category": "92"}).encode(),
    {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE + "achievements",
        "Origin": "https://armory.warmane.com",
    },
)
