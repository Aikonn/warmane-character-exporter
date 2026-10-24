"""Parse the Warmane armory mounts-and-companions page (static HTML, two tabs)."""

from __future__ import annotations

import html
import re
from typing import Any

_TAB = re.compile(r'<div id="(?P<id>mount|companion)-tab">(?P<body>.*?)(?=<div id="(?:mount|companion)-tab">|<div id="page-footer"|\Z)', re.S)
_BOX = re.compile(
    r"<div class=\"journal-box\">.*?npcs/(?P<npc>\d+)\.jpg.*?"
    r'<a href="[^"]*?item=(?P<item>\d+)"[^>]*>(?P<name>.*?)</a>',
    re.S,
)


class MountsError(ValueError):
    pass


def parse_mounts_page(page_html: str) -> dict[str, list[dict[str, Any]]]:
    """Return {"mounts": [...], "companions": [...]}; each entry has name, item_id, npc_id."""
    tabs = {m.group("id"): m.group("body") for m in _TAB.finditer(page_html)}
    if "mount" not in tabs or "companion" not in tabs:
        raise MountsError("Page has no mount and companion tabs")
    result: dict[str, list[dict[str, Any]]] = {}
    for key, plural in (("mount", "mounts"), ("companion", "companions")):
        body = tabs[key]
        boxes = body.count('class="journal-box"')
        entries = [
            {"name": html.unescape(re.sub(r"<[^>]+>", "", m.group("name"))).strip(),
             "item_id": int(m.group("item")), "npc_id": int(m.group("npc"))}
            for m in _BOX.finditer(body)
        ]
        if len(entries) != boxes:
            raise MountsError(f"{plural}: {boxes} boxes but {len(entries)} parsed")
        result[plural] = entries
    return result
