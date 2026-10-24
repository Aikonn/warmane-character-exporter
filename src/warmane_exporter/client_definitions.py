"""Typed offline lookups on top of the 3.3.5a (build 12340) DBC tables.

Field indexes verified against the real client on 2026-10-24:
  SpellItemEnchantment.dbc (38 fields): name enUS = 14
  Spell.dbc (234 fields): name enUS = 136, rank enUS = 153, description enUS = 170
  Talent.dbc (23 fields, UNVERIFIED until run on a real client): tab = 1, row = 2, column = 3, rank spell IDs = 4..12
  Item.dbc (8 fields): class = 1, subclass = 2, inventory type = 6
Item names are NOT in 3.3.5a DBCs (they live in the item cache), so they are not resolved here.
"""

from __future__ import annotations

import struct
from typing import Any
from dataclasses import dataclass

from .dbc_parser import DbcError, DbcTable
from .mpq_reader import ClientData

ENCHANT_FIELDS = 38
ENCHANT_NAME = 14
SPELL_FIELDS = 234
SPELL_NAME = 136
SPELL_RANK = 153
SPELL_DESCRIPTION = 170
SPELL_PROC_CHANCE = 35
SPELL_PROC_CHARGES = 36
SPELL_DURATION_INDEX = 40
SPELL_STACK_AMOUNT = 49
SPELL_EFFECT_DIE_SIDES = 74       # 3 fields each, effect 1..3
SPELL_EFFECT_BASE_POINTS = 80
SPELL_EFFECT_RADIUS_INDEX = 92
SPELL_EFFECT_AMPLITUDE = 98
SPELL_EFFECT_MULTIPLE_VALUE = 101
SPELL_EFFECT_CHAIN_TARGETS = 104
DURATION_FIELDS = 4               # SpellDuration.dbc: ID, Duration, PerLevel, Max
RADIUS_FIELDS = 4                 # SpellRadius.dbc: ID, Radius, PerLevel, Max (floats)

TALENT_FIELDS = 23
TALENT_TAB = 1
TALENT_ROW = 2
TALENT_COLUMN = 3
TALENT_RANK_FIRST = 4   # RankID[9] occupies fields 4..12
TALENT_RANK_COUNT = 9
ENCHANT_CONDITION = 34      # SpellItemEnchantment.dbc: id of the SpellItemEnchantmentCondition row (meta gem requirements)
ITEMSET_FIELDS = 53          # ItemSet.dbc: ID, name[17], item[17], bonus spell[8], threshold[8], skill, rank
ITEMSET_ITEMS = 18
ITEMSET_SPELLS = 35
ITEMSET_THRESHOLDS = 43
GEMPROP_FIELDS = 5        # GemProperties.dbc: ID, EnchantID, MaxcountInv, MaxcountItem, Type (colour bit mask)
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


CONDITION_RECORD = struct.Struct("<I5B5I5B5B5I5B")   # packed, no padding: id, colour[5], operand[5], comparator[5], compare colour[5], value[5], logic[5]


def parse_conditions(data: bytes) -> dict[int, list[list[int]]]:
    """SpellItemEnchantmentCondition.dbc: {condition id: [[colour, comparator, compare colour, value], ...]}.

    This table is packed (its header claims 31 four-byte fields but the records are 64 bytes), so it
    cannot go through DbcTable.
    """
    if data[:4] != b"WDBC":
        raise DbcError(f"Invalid DBC magic: {data[:4]!r}")
    count, _fields, size, _strings = struct.unpack_from("<IIII", data, 4)
    if size != CONDITION_RECORD.size:
        raise DbcError(f"SpellItemEnchantmentCondition.dbc record size {size}, expected {CONDITION_RECORD.size}")
    found: dict[int, list[list[int]]] = {}
    for position in range(count):
        row = CONDITION_RECORD.unpack_from(data, 20 + position * size)
        colour, comparator, compare, value = row[1:6], row[11:16], row[16:21], row[21:26]
        rows = [[colour[i], comparator[i], compare[i], value[i]] for i in range(5) if colour[i]]
        if rows:
            found[row[0]] = rows
    return found


class ClientDefinitions:
    """Lazy per-table loader. Raises DbcError if a table has an unexpected layout."""

    def __init__(self, client: ClientData) -> None:
        self._client = client
        self._tables: dict[str, DbcTable] = {}
        self._talent_by_spell: dict[int, TalentInfo] | None = None
        self._glyph_by_spell: dict[int, GlyphInfo] | None = None
        self._gem_by_enchant: dict[int, tuple[int, int]] | None = None
        self._conditions: dict[int, list[list[int]]] | None = None
        self._sets: dict[int, dict[str, Any]] | None = None

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

    def gem_properties(self, enchant_id: int) -> tuple[int, int] | None:
        """(GemProperties id, colour bit mask) of the gem whose socketed effect is this enchant id."""
        if self._gem_by_enchant is None:
            table = self._table("GemProperties.dbc", GEMPROP_FIELDS)
            self._gem_by_enchant = {}
            for position in range(len(table)):
                row = table.row(position)
                if row[1]:
                    self._gem_by_enchant.setdefault(row[1], (row[0], row[4]))
        return self._gem_by_enchant.get(enchant_id)

    def gem_requirements(self, enchant_id: int) -> list[list[int]] | None:
        """Meta gem requirements as [colour, comparator, compare colour, value] rows, None when the effect has none."""
        table = self._table("SpellItemEnchantment.dbc", ENCHANT_FIELDS)
        row = table.find(enchant_id)
        if row is None or not row[ENCHANT_CONDITION]:
            return None
        if self._conditions is None:
            found = self._client.read("DBFilesClient\\SpellItemEnchantmentCondition.dbc")
            if found is None:
                raise DbcError("SpellItemEnchantmentCondition.dbc not found in client archives")
            self._conditions = parse_conditions(found[0])
        return self._conditions.get(row[ENCHANT_CONDITION])

    def item_sets(self) -> list[dict[str, Any]]:
        """Every item set: id, name, item ids, bonus spell ids with their piece thresholds."""
        table = self._table("ItemSet.dbc", ITEMSET_FIELDS)
        sets = []
        for position in range(len(table)):
            row = table.row(position)
            bonuses = [[row[ITEMSET_THRESHOLDS + i], row[ITEMSET_SPELLS + i]] for i in range(8) if row[ITEMSET_SPELLS + i]]
            items = [i for i in row[ITEMSET_ITEMS: ITEMSET_ITEMS + 17] if i]
            if row[0]:
                sets.append({"id": row[0], "name": table.string_at(row[1]) or "", "items": items, "bonuses": sorted(bonuses)})
        return sets

    def item_set(self, set_id: int) -> dict[str, Any] | None:
        if self._sets is None:
            try:
                self._sets = {s["id"]: s for s in self.item_sets()}
            except DbcError:   # table missing in this client: the export file may still know the sets
                self._sets = {}
        return self._sets.get(set_id)

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

    def spell_numbers(self, spell_id: int):
        """Numeric fields needed to render description templates (layout verified by diagnostics)."""
        from .spell_text import SpellNumbers

        table = self._table("Spell.dbc", SPELL_FIELDS)
        row = table.find(spell_id)
        if row is None:
            return None

        def signed(value: int) -> int:
            return value - (1 << 32) if value >= (1 << 31) else value

        def triple(first: int):
            return tuple(signed(row[first + i]) for i in range(3))

        return SpellNumbers(
            spell_id,
            base_points=triple(SPELL_EFFECT_BASE_POINTS),
            die_sides=triple(SPELL_EFFECT_DIE_SIDES),
            radius_index=triple(SPELL_EFFECT_RADIUS_INDEX),
            amplitude_ms=triple(SPELL_EFFECT_AMPLITUDE),
            chain_targets=triple(SPELL_EFFECT_CHAIN_TARGETS),
            multiple_value=tuple(struct.unpack("<f", struct.pack("<I", row[SPELL_EFFECT_MULTIPLE_VALUE + i]))[0] for i in range(3)),
            duration_index=row[SPELL_DURATION_INDEX],
            proc_chance=row[SPELL_PROC_CHANCE],
            proc_charges=row[SPELL_PROC_CHARGES],
            stack_amount=row[SPELL_STACK_AMOUNT],
        )

    def duration_ms(self, index: int):
        if index == 0:
            return 0
        table = self._table("SpellDuration.dbc", DURATION_FIELDS)
        row = table.find(index)
        if row is None:
            return None
        value = row[1] - (1 << 32) if row[1] >= (1 << 31) else row[1]
        return value

    def radius_yards(self, index: int):
        if index == 0:
            return 0.0
        table = self._table("SpellRadius.dbc", RADIUS_FIELDS)
        row = table.find(index)
        if row is None:
            return None
        return struct.unpack("<f", struct.pack("<I", row[1]))[0]

    def render_spell_description(self, spell_id: int):
        """Rendered description (spell_text.Rendered) or None if the spell is unknown."""
        from .spell_text import render_description

        info = self.spell(spell_id)
        return None if info is None else render_description(info.description, spell_id, self)

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
