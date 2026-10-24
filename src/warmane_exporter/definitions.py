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

from .acore_items import QUALITY_NAMES, AcoreItem, AcoreItems
from .client_definitions import INVENTORY_TYPES, ItemInfo


GEM_COLORS = {1: "meta", 2: "red", 4: "yellow", 8: "blue", 6: "orange", 10: "purple", 12: "green", 14: "prismatic"}


class Definitions:
    """Texts: game client first, then the local export file. Items: client, then AzerothCore."""

    def __init__(self, client: Any = None, acore: AcoreItems | None = None, file: Any = None) -> None:
        if client is None and acore is None and file is None:
            raise ValueError("Definitions needs at least one source")
        self.client, self.acore, self.file = client, acore, file
        self._texts = [s for s in (client, file) if s is not None]

    @property
    def source_names(self) -> list[str]:
        return [n for n, s in (("client", self.client), ("export-file", self.file), ("acore", self.acore)) if s is not None]

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

    # texts ----------------------------------------------------------------
    def _first(self, method: str, key: int):
        for source in self._texts:
            value = getattr(source, method)(key)
            if value is not None:
                return value
        return None

    def enchant_text(self, enchant_id: int) -> str | None:
        return self._first("enchant_text", enchant_id)

    def gem_info(self, enchant_id: int) -> dict[str, Any] | None:
        """Colour name and quality name of the gem behind a socketed gem effect (either part may be missing)."""
        found = None
        for source in self._texts:
            fn = getattr(source, "gem_properties", None)
            found = fn(enchant_id) if fn else None
            if found is not None:
                break
        if found is None:
            return None
        props_id, mask = found
        quality = self.acore.gem_quality(props_id) if self.acore is not None else None
        return {"color": GEM_COLORS.get(mask, f"mask {mask}"), "quality": QUALITY_NAMES.get(quality) if quality is not None else None}

    def gem_requirements(self, enchant_id: int):
        return self._first("gem_requirements", enchant_id)

    def item_set(self, set_id: int):
        return self._first("item_set", set_id)

    def spell(self, spell_id: int):
        return self._first("spell", spell_id)

    def render_spell_description(self, spell_id: int):
        return self._first("render_spell_description", spell_id)

    def talent_for_spell(self, spell_id: int):
        return self._first("talent_for_spell", spell_id)

    def glyph_for_spell(self, spell_id: int):
        return self._first("glyph_for_spell", spell_id)


def load_definitions(client: Any = None, library_root: Path = Path("library")) -> Definitions | None:
    """Combine the given client definitions (or None) with the local export file and item database if present."""
    root = Path(library_root)
    acore = AcoreItems(root / "acore" / "items.db") if (root / "acore" / "items.db").exists() else None
    file = None
    export = root / "definitions" / "client-export.json"
    if export.exists():
        from .file_definitions import FileDefinitions

        file = FileDefinitions(export)
    if client is None and acore is None and file is None:
        return None
    return Definitions(client, acore, file)


__all__ = ["Definitions", "load_definitions", "INVENTORY_TYPES"]
