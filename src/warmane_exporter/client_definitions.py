"""Typed offline lookups on top of the 3.3.5a (build 12340) DBC tables.

Field indexes verified against the real client on 2026-10-24:
  SpellItemEnchantment.dbc (38 fields): name enUS = 14
  Spell.dbc (234 fields): name enUS = 136, rank enUS = 153, description enUS = 170
  Talent.dbc (23 fields, UNVERIFIED until run on a real client): tab = 1, row = 2, column = 3, rank spell IDs = 4..12
  Item.dbc (8 fields): class = 1, subclass = 2, inventory type = 6
Item names are NOT in 3.3.5a DBCs (they live in the item cache), so they are not resolved here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dbc_parser import DbcError, DbcTable
from .mpq_reader import ClientData

ENCHANT_FIELDS = 38
ENCHANT_NAME = 14
SPELL_FIELDS = 234
SPELL_NAME = 136
SPELL_RANK = 153
SPELL_DESCRIPTION = 170
TALENT_FIELDS = 23
TALENT_TAB = 1
TALENT_ROW = 2
TALENT_COLUMN = 3
TALENT_RANK_FIRST = 4   # RankID[9] occupies fields 4..12
TALENT_RANK_COUNT = 9
GLYPH_FIELDS = 4         # GlyphProperties.dbc: ID, SpellID, GlyphSlotFlags, SpellIconID (UNVERIFIED)
ITEM_FIELDS = 8
ITEM_CLASS = 1
ITEM_SUBCLASS = 2
ITEM_INVENTORY_TYPE = 6

INVENTORY_TYPES = {
    0: "none", 1: "head", 2: "neck", 3: "shoulder", 4: "shirt", 5: "chest",
    6: "waist", 7: "legs", 8: "feet", 9: "wrist", 10: "hands", 11: "finger",
    12: "trinket", 13: "one-hand", 14: "shield", 15: "ranged", 16: "back",
    17: "two-hand", 18: "bag", 19: "tabard", 20: "robe", 21: "main-hand",
    22: "off-hand", 23: "held-in-off-hand", 24: "ammo", 25: "thrown",
    26: "ranged-right", 27: "quiver", 28: "relic",
}


@dataclass(frozen=True)
class SpellInfo:
    spell_id: int
    name: str
    rank: str
    description: str


@dataclass(frozen=True)
class TalentInfo:
    talent_id: int
    tab_id: int
    row: int
    column: int
    rank_spell_ids: tuple[int, ...]   # rank 1..N, zero slots removed


@dataclass(frozen=True)
class GlyphInfo:
    glyph_id: int
    spell_id: int
    slot_flags: int   # 0 = major, 1 = minor (to be cross-checked against captures)


@dataclass(frozen=True)
class ItemInfo:
    item_id: int
    item_class: int
    item_subclass: int
    inventory_type: int

    @property
    def inventory_type_name(self) -> str:
        return INVENTORY_TYPES.get(self.inventory_type, f"unknown({self.inventory_type})")


class ClientDefinitions:
    """Lazy per-table loader. Raises DbcError if a table has an unexpected layout."""

    def __init__(self, client: ClientData) -> None:
        self._client = client
        self._tables: dict[str, DbcTable] = {}
        self._talent_by_spell: dict[int, TalentInfo] | None = None
        self._glyph_by_spell: dict[int, GlyphInfo] | None = None

    def _table(self, name: str, fields: int) -> DbcTable:
        if name not in self._tables:
            found = self._client.read(f"DBFilesClient\\{name}")
            if found is None:
                raise DbcError(f"{name} not found in client archives")
            table = DbcTable(found[0])
            if table.header.field_count != fields:
                raise DbcError(
                    f"{name} has {table.header.field_count} fields, expected {fields}; "
                    "this is not a 3.3.5a (12340) table"
                )
            self._tables[name] = table
        return self._tables[name]

    def enchant_text(self, enchant_id: int) -> str | None:
        table = self._table("SpellItemEnchantment.dbc", ENCHANT_FIELDS)
        row = table.find(enchant_id)
        return None if row is None else table.string_at(row[ENCHANT_NAME]) or ""

    def spell(self, spell_id: int) -> SpellInfo | None:
        table = self._table("Spell.dbc", SPELL_FIELDS)
        row = table.find(spell_id)
        if row is None:
            return None
        return SpellInfo(
            spell_id,
            table.string_at(row[SPELL_NAME]) or "",
            table.string_at(row[SPELL_RANK]) or "",
            table.string_at(row[SPELL_DESCRIPTION]) or "",
        )

    def item(self, item_id: int) -> ItemInfo | None:
        table = self._table("Item.dbc", ITEM_FIELDS)
        row = table.find(item_id)
        if row is None:
            return None
        return ItemInfo(item_id, row[ITEM_CLASS], row[ITEM_SUBCLASS], row[ITEM_INVENTORY_TYPE])

    def talent_for_spell(self, spell_id: int) -> TalentInfo | None:
        """Talent whose rank list contains spell_id (any rank)."""
        if self._talent_by_spell is None:
            table = self._table("Talent.dbc", TALENT_FIELDS)
            index: dict[int, TalentInfo] = {}
            for position in range(len(table)):
                row = table.row(position)
                ranks = tuple(
                    s for s in row[TALENT_RANK_FIRST : TALENT_RANK_FIRST + TALENT_RANK_COUNT] if s
                )
                info = TalentInfo(row[0], row[TALENT_TAB], row[TALENT_ROW], row[TALENT_COLUMN], ranks)
                for s in ranks:
                    index[s] = info
            self._talent_by_spell = index
        return self._talent_by_spell.get(spell_id)

    def glyph_for_spell(self, spell_id: int) -> GlyphInfo | None:
        if self._glyph_by_spell is None:
            table = self._table("GlyphProperties.dbc", GLYPH_FIELDS)
            self._glyph_by_spell = {}
            for position in range(len(table)):
                row = table.row(position)
                self._glyph_by_spell[row[1]] = GlyphInfo(row[0], row[1], row[2])
        return self._glyph_by_spell.get(spell_id)
