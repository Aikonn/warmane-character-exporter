"""Parse the Warmane armory reputation page (static HTML, one flat list of factions)."""

from __future__ import annotations

import html
import re
from typing import Any

_BLOCK = re.compile(
    r'<div class="reputation (?P<cls>[a-z]+)">\s*<div class="name">(?P<name>.*?)</div>.*?'
    r'<div class="contentbody">(?P<cur>[\d,]+)\s*/\s*(?P<max>[\d,]+)</div>.*?'
    r'<div class="standing">(?P<standing>.*?)</div>',
    re.S,
)


class ReputationError(ValueError):
    pass


def parse_reputation_page(page_html: str) -> list[dict[str, Any]]:
    if 'class="reputation ' not in page_html:
        raise ReputationError("Page contains no reputation entries")
    rows = []
    for m in _BLOCK.finditer(page_html):
        standing = html.unescape(m.group("standing")).strip()
        if m.group("cls") != standing.lower().replace(" ", ""):
            raise ReputationError(f"Standing class {m.group('cls')!r} disagrees with text {standing!r}")
        rows.append({
            "faction": html.unescape(m.group("name")).strip(),
            "standing": standing,
            "current": int(m.group("cur").replace(",", "")),
            "maximum": int(m.group("max").replace(",", "")),
        })
    if not rows:
        raise ReputationError("Reputation blocks found but none could be parsed")
    return rows
