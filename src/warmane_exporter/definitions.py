"""Swappable source of static game definitions.

Enrichment code talks to one Definitions object. Behind it are up to two sources:
  - the game client (ClientDefinitions): spell, talent, glyph, enchant and gem texts;
  - the local AzerothCore item database (AcoreItems): item names, quality, slot, stats, sockets.
Item facts prefer the client when present (it is what the player actually runs), then AzerothCore.
Anything neither source knows returns None and is reported as unresolved, never guessed.
Extra sources (for example cached Warmane tooltips) can be added by extending `texts`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .acore_items import AcoreItem, AcoreItems
from .client_definitions import INVENTORY_TYPES, ItemInfo


class Definitions:
    def __init__(self, client: Any = None, acore: AcoreItems | None = None) -> None:
        if client is None and acore is None:
            raise ValueError("Definitions needs at least one source")
        self.client, self.acore = client, acore

    @property
    def source_names(self) -> list[str]:
        return [n for n, s in (("client", self.client), ("acore", self.acore)) if s is not None]

    def close(self) -> None:
        if self.acore is not None:
            self.acore.close()

    # item facts -------------------------------------------------------
    def item(self, item_id: int) -> ItemInfo | None:
        if self.client is not None:
            info = self.client.item(item_id)
            if info is not None:
                return info
        if self.acore is not None:
            ac = self.acore.item(item_id)
            if ac is not None:
                return ItemInfo(ac.item_id, ac.item_class, ac.item_subclass, ac.inventory_type)
        return None

    def acore_item(self, item_id: int) -> AcoreItem | None:
        return self.acore.item(item_id) if self.acore is not None else None

    # texts: client only (for now) ---------------------------------------
    def enchant_text(self, enchant_id: int) -> str | None:
        return self.client.enchant_text(enchant_id) if self.client is not None else None

    def spell(self, spell_id: int):
        return self.client.spell(spell_id) if self.client is not None else None

    def render_spell_description(self, spell_id: int):
        return self.client.render_spell_description(spell_id) if self.client is not None else None

    def talent_for_spell(self, spell_id: int):
        return self.client.talent_for_spell(spell_id) if self.client is not None else None

    def glyph_for_spell(self, spell_id: int):
        return self.client.glyph_for_spell(spell_id) if self.client is not None else None


def load_definitions(client: Any = None, library_root: Path = Path("library")) -> Definitions | None:
    """Combine the given client definitions (or None) with the local AzerothCore database if present."""
    acore = None
    db = Path(library_root) / "acore" / "items.db"
    if db.exists():
        acore = AcoreItems(db)
    if client is None and acore is None:
        return None
    return Definitions(client, acore)


__all__ = ["Definitions", "load_definitions", "INVENTORY_TYPES"]
