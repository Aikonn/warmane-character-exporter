"""Parse Warmane armory achievement and statistic category responses.

Both endpoints answer a form POST (category=<id>) with JSON {"content": "<html>"}.
Pure functions, no network. Achievement entries are ``earned`` or ``locked``; the date text is
kept as shown (MM/DD/YYYY) and also converted to ISO.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any


class CategoryError(ValueError):
    pass


def extract_content(body_text: str) -> str:
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise CategoryError(f"Response is not JSON: {exc}") from exc
    content = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(content, str):
        raise CategoryError("JSON has no string 'content' field")
    return content


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


_BLOCK = re.compile(r'<div class="achievement(?P<cls>[^"]*)" id="ach(?P<id>\d+)"')
_POINTS = re.compile(r'<div class="points">\s*<div>(?P<v>[^<]*)</div>', re.S)
_ICON = re.compile(r'<img src="(?P<v>[^"]+)"')
_TITLE = re.compile(r'<div class="title">(?P<v>.*?)</div>', re.S)
_DESC = re.compile(r'<div class="description">(?P<v>.*?)</div>', re.S)
_DATE = re.compile(r'<div class="date">\s*Earned (?P<v>\d{2}/\d{2}/\d{4})\s*</div>', re.S)


def _iso(us_date: str) -> str:
    month, day, year = us_date.split("/")
    return f"{year}-{month}-{day}"


def parse_achievements_content(content: str) -> list[dict[str, Any]]:
    """Return achievement entries in page order."""
    matches = list(_BLOCK.finditer(content))
    entries: list[dict[str, Any]] = []
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(content)
        chunk = content[match.start():end]
        title = _TITLE.search(chunk)
        if title is None:
            raise CategoryError(f"Achievement {match.group('id')} has no title")
        points = _POINTS.search(chunk)
        date = _DATE.search(chunk)
        icon = _ICON.search(chunk)
        locked = "locked" in match.group("cls").split()
        entries.append({
            "id": int(match.group("id")),
            "title": _text(title.group("v")),
            "description": _text(_DESC.search(chunk).group("v")) if _DESC.search(chunk) else "",
            "points": int(points.group("v")) if points and points.group("v").strip().isdigit() else None,
            "icon": icon.group("v") if icon else None,
            "earned": not locked,
            "earned_date": _iso(date.group("v")) if date else None,
            "earned_date_text": date.group("v") if date else None,
        })
    return entries


def parse_achievements_response(body_text: str) -> list[dict[str, Any]]:
    content = extract_content(body_text)
    if "achievement" not in content:
        raise CategoryError("Content does not look like an achievement list")
    return parse_achievements_content(content)


_ROW = re.compile(r"<tr>\s*<td[^>]*>(?P<k>.*?)</td>\s*<td[^>]*>(?P<v>.*?)</td>\s*</tr>", re.S)


def parse_statistics_content(content: str) -> list[dict[str, str]]:
    return [
        {"name": _text(m.group("k")), "value": _text(m.group("v"))}
        for m in _ROW.finditer(content)
    ]


def parse_statistics_response(body_text: str) -> list[dict[str, str]]:
    content = extract_content(body_text)
    if "data-table" not in content:
        raise CategoryError("Content does not look like a statistics table")
    return parse_statistics_content(content)
