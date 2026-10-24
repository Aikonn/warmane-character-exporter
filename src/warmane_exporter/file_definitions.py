"""Definitions read from the local export written by definition_export (no game client needed)."""

from __future__ import annotations

import json
from pathlib import Path

from .client_definitions import GlyphInfo, SpellInfo, TalentInfo
from .definition_export import SCHEMA
from .spell_text import Rendered


class FileDefinitions:
    def __init__(self, path: Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA:
            raise ValueError(f"unsupported definitions file schema: {data.get('schema')!r}")
        self.data = data
        self._enchants: dict[str, str] = data["enchants"]
        self._spells: dict[str, dict] = data["spells"]
        self._gems: dict[str, list] = data.get("gem_properties", {})   # absent in exports made before gem colours
        self._conditions: dict[str, list] = data.get("enchant_conditions", {})   # absent in older exports
        self._talent_by_spell: dict[int, TalentInfo] = {}
        for t in data["talents"]:
            info = TalentInfo(t["id"], t["tab"], t["row"], t["column"], tuple(t["ranks"]))
            for spell_id in t["ranks"]:
                self._talent_by_spell[spell_id] = info
        self._glyph_by_spell = {g["spell"]: GlyphInfo(g["id"], g["spell"], g["flags"]) for g in data["glyphs"]}

    def enchant_text(self, enchant_id: int) -> str | None:
        return self._enchants.get(str(enchant_id))

    def gem_properties(self, enchant_id: int) -> tuple[int, int] | None:
        found = self._gems.get(str(enchant_id))
        return None if found is None else (found[0], found[1])

    def gem_requirements(self, enchant_id: int) -> list[list[int]] | None:
        return self._conditions.get(str(enchant_id))

    def spell(self, spell_id: int) -> SpellInfo | None:
        entry = self._spells.get(str(spell_id))
        return None if entry is None else SpellInfo(spell_id, entry["name"], entry["rank"], entry["description"])

    def render_spell_description(self, spell_id: int) -> Rendered | None:
        entry = self._spells.get(str(spell_id))
        if entry is None or "rendered" not in entry:
            return None
        return Rendered(entry["rendered"], bool(entry.get("rendered_unresolved")))

    def talent_for_spell(self, spell_id: int) -> TalentInfo | None:
        return self._talent_by_spell.get(spell_id)

    def glyph_for_spell(self, spell_id: int) -> GlyphInfo | None:
        return self._glyph_by_spell.get(spell_id)
