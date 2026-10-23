from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, unquote, urlparse

SUPPORTED_HOST = "armory.warmane.com"
SUPPORTED_REALMS = {
    "onyxia": "Onyxia",
    "icecrown": "Icecrown",
}
SUPPORTED_VIEWS = {"summary", "profile"}


@dataclass(frozen=True)
class CharacterIdentity:
    input_url: str
    request_url: str
    canonical_url: str
    name: str
    realm: str
    view: str


def parse_character_url(url: str) -> CharacterIdentity:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only https URLs are supported.")

    host = (parsed.hostname or "").lower()
    if host != SUPPORTED_HOST:
        raise ValueError(f"Unsupported host: {parsed.hostname!r}. Expected {SUPPORTED_HOST}.")

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) != 4 or path_parts[0].lower() != "character":
        raise ValueError("Path must follow /character/<name>/<realm>/<summary|profile>.")

    raw_name = unquote(path_parts[1]).strip()
    raw_realm = unquote(path_parts[2]).strip()
    raw_view = path_parts[3].strip().lower()

    if not raw_name:
        raise ValueError("Character name is missing.")

    realm = SUPPORTED_REALMS.get(raw_realm.lower())
    if realm is None:
        raise ValueError("Unsupported realm. Supported realms: Onyxia, Icecrown.")

    if raw_view not in SUPPORTED_VIEWS:
        raise ValueError("Unsupported character view. Expected summary or profile.")

    encoded_name = quote(raw_name, safe="")
    request_url = f"https://{SUPPORTED_HOST}/character/{encoded_name}/{realm}/{raw_view}"
    canonical_url = f"https://{SUPPORTED_HOST}/character/{encoded_name}/{realm}/summary"

    return CharacterIdentity(
        input_url=url,
        request_url=request_url,
        canonical_url=canonical_url,
        name=raw_name,
        realm=realm,
        view=raw_view,
    )
