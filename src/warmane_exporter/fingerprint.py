"""Content fingerprints for deciding whether a quick report is unchanged."""

from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from time import time

from .cache import ResponseCache
from .config import find_config_path
from .snapshot import character_page_url
from .warmane_api import api_summary_url


class _FingerprintMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "meta":
            return
        attributes = dict(attrs)
        name = attributes.get("name")
        content = attributes.get("content")
        if name is not None and name.casefold() == "warmane-fingerprint" and content is not None:
            self.values.append(content)


def tool_version_hash(project_root: Path | None = None, config_path: Path | None = None) -> str:
    """Hash package Python sources, bundled data files, and the optional client-path config."""
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
    package_sources = sorted((root / "src" / "warmane_exporter").glob("*.py"))
    files = [
        (path.relative_to(root).as_posix(), path)
        for path in package_sources
    ]
    for relative in (
        Path("library/definitions/client-export.json"),
        Path("library/acore/items.db"),
    ):
        path = root / relative
        if path.is_file():
            files.append((relative.as_posix(), path))

    config = Path(config_path) if config_path is not None else find_config_path(None)
    if config.is_file():
        files.append(("warmane-character-exporter.config", config))

    digest = sha256()
    for label, path in sorted(files, key=lambda item: item[0]):
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def response_cache_keys(name: str, realm: str) -> tuple[str, str, str]:
    """Return snapshot cache keys in fingerprint order: JSON summary, HTML summary, talents."""
    urls = (
        api_summary_url(name, realm),
        character_page_url(name, realm, "summary"),
        character_page_url(name, realm, "talents"),
    )
    sources = ("warmane-json-summary", "warmane-html-summary", "warmane-html-talents")
    return tuple(f"{source}|{url}" for source, url in zip(sources, urls, strict=True))


def fingerprint_for_bodies(
    tool_version: str,
    json_summary: str,
    html_summary: str,
    talents: str,
) -> str:
    """Hash the tool version and three cached snapshot bodies in their canonical order."""
    digest = sha256()
    digest.update(tool_version.encode("ascii"))
    for body in (json_summary, html_summary, talents):
        encoded = body.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def cached_fingerprint(
    cache: ResponseCache,
    name: str,
    realm: str,
    tool_version: str,
    max_age_seconds: float | None = None,
    now: float | None = None,
) -> str | None:
    """Fingerprint cached source bodies, optionally requiring all entries to be fresh."""
    entries = [cache.get(key) for key in response_cache_keys(name, realm)]
    if any(entry is None for entry in entries):
        return None
    cached = [entry for entry in entries if entry is not None]
    if max_age_seconds is not None:
        current_time = time() if now is None else now
        if any(entry.age_seconds(current_time) >= max_age_seconds for entry in cached):
            return None
    return fingerprint_for_bodies(tool_version, *(entry.body for entry in cached))


def html_fingerprint(path: Path) -> str | None:
    """Read a report's fingerprint meta value; absent, malformed, or conflicting values return None."""
    if not path.is_file():
        return None
    parser = _FingerprintMetaParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    if not parser.values or len(set(parser.values)) != 1:
        return None
    value = parser.values[0]
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        return None
    return value
