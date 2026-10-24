"""Item definitions from the AzerothCore world database (item_template), no game client needed.

Source: https://github.com/azerothcore/database-wotlk (sql/base/item_template.sql, AGPL-3.0,
a 3.3.5a world database dump). The dump is downloaded once into the local Library and
converted into a small SQLite file; later runs read only the local file.

Only a subset of columns is kept: identity, quality, slot, level, stats, sockets.
Values come from AzerothCore, not from Warmane, so compare them with the armory
(see acore_verify) before trusting them for a given realm.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SOURCE_URL = "https://raw.githubusercontent.com/azerothcore/database-wotlk/master/sql/base/item_template.sql"

QUALITY_NAMES = {0: "poor", 1: "common", 2: "uncommon", 3: "rare", 4: "epic", 5: "legendary", 6: "artifact", 7: "heirloom"}
STAT_NAMES = {
    0: "mana", 1: "health", 3: "agility", 4: "strength", 5: "intellect", 6: "spirit", 7: "stamina",
    12: "defense rating", 13: "dodge rating", 14: "parry rating", 15: "block rating",
    16: "melee hit rating", 17: "ranged hit rating", 18: "spell hit rating",
    19: "melee crit rating", 20: "ranged crit rating", 21: "spell crit rating",
    28: "melee haste rating", 29: "ranged haste rating", 30: "spell haste rating",
    31: "hit rating", 32: "crit rating", 35: "resilience rating", 36: "haste rating",
    37: "expertise rating", 38: "attack power", 39: "ranged attack power",
    41: "spell healing done", 42: "spell damage done", 43: "mana regeneration",
    44: "armor penetration rating", 45: "spell power", 46: "health regeneration",
    47: "spell penetration", 48: "block value",
}
SOCKET_COLORS = {0: None, 1: "meta", 2: "red", 4: "yellow", 8: "blue"}

_COLUMN = re.compile(r"^\s*`(\w+)`\s")


def parse_columns(sql: str) -> list[str]:
    """Column names in CREATE TABLE order."""
    columns: list[str] = []
    inside = False
    for line in sql.splitlines():
        if line.startswith("CREATE TABLE"):
            inside = True
            continue
        if inside:
            match = _COLUMN.match(line)
            if match:
                columns.append(match.group(1))
            elif line.startswith(")"):
                break
    if not columns:
        raise ValueError("no CREATE TABLE column list found")
    return columns


def iter_rows(sql: str) -> Iterator[list]:
    """Yield each row of the INSERT statements as a list of int / float / str / None."""
    inserting = False
    for line in sql.splitlines():
        if line.startswith("INSERT INTO"):
            inserting = True
        elif inserting and line.startswith("("):
            yield _parse_tuple(line.rstrip(",;"))


def _parse_tuple(text: str) -> list:
    values: list = []
    i, n = 1, len(text)          # skip the opening parenthesis
    while i < n:
        ch = text[i]
        if ch == "'":
            j, out = i + 1, []
            while True:
                if j >= n:
                    raise ValueError("unterminated string")
                c = text[j]
                if c == "\\" and j + 1 < n:
                    nxt = text[j + 1]
                    out.append({"n": "\n", "r": "\r", "t": "\t", "0": "\0"}.get(nxt, nxt))
                    j += 2
                elif c == "'":
                    if j + 1 < n and text[j + 1] == "'":
                        out.append("'")
                        j += 2
                    else:
                        break
                else:
                    out.append(c)
                    j += 1
            values.append("".join(out))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ",)":
                j += 1
            token = text[i:j].strip()
            if token.upper() == "NULL":
                values.append(None)
            else:
                try:
                    values.append(int(token))
                except ValueError:
                    values.append(float(token))
            i = j
        while i < n and text[i] in ", ":
            i += 1
        if i < n and text[i] == ")":
            break
    return values


KEEP = (
    ["entry", "class", "subclass", "name", "Quality", "InventoryType", "ItemLevel", "RequiredLevel",
     "AllowableClass", "AllowableRace", "bonding", "itemset", "socketBonus", "GemProperties", "VerifiedBuild",
     "StatsCount", "ScalingStatDistribution", "ScalingStatValue", "armor", "delay", "MaxDurability"]
    + [f"stat_type{i}" for i in range(1, 11)] + [f"stat_value{i}" for i in range(1, 11)]
    + [f"socketColor_{i}" for i in range(1, 4)] + [f"socketContent_{i}" for i in range(1, 4)]
)


def build_database(sql_text: str, db_path: Path, source_url: str = SOURCE_URL) -> int:
    """Convert the SQL dump into SQLite at db_path (replaced). Returns the number of items."""
    columns = parse_columns(sql_text)
    missing = [c for c in KEEP if c not in columns]
    if missing:
        raise ValueError(f"item_template layout changed, missing columns: {missing}")
    index = [columns.index(c) for c in KEEP]
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    try:
        con.execute(f"CREATE TABLE item ({', '.join(f'{c} ' + ('TEXT' if c == 'name' else 'INTEGER') for c in KEEP)}, PRIMARY KEY (entry))")
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        count = 0
        for row in iter_rows(sql_text):
            if len(row) != len(columns):
                raise ValueError(f"row has {len(row)} values, expected {len(columns)}")
            con.execute(f"INSERT INTO item VALUES ({','.join('?' * len(KEEP))})", [row[i] for i in index])
            count += 1
        con.execute("INSERT INTO meta VALUES ('source_url', ?)", (source_url,))
        con.commit()
    finally:
        con.close()
    tmp.replace(db_path)
    return count


@dataclass(frozen=True)
class AcoreItem:
    item_id: int
    name: str
    item_class: int
    item_subclass: int
    quality: int
    inventory_type: int
    item_level: int
    required_level: int
    stats: tuple[tuple[str, int], ...]
    sockets: tuple[str, ...]          # socket colours in order; empty = no sockets
    socket_bonus_enchant_id: int      # SpellItemEnchantment id, 0 = none
    gem_properties_id: int
    scaling: bool                     # heirloom-style scaling stats: stat values are not fixed

    @property
    def quality_name(self) -> str:
        return QUALITY_NAMES.get(self.quality, f"unknown({self.quality})")


class AcoreItems:
    def __init__(self, db_path: Path) -> None:
        self._con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
        self._con.row_factory = sqlite3.Row

    def close(self) -> None:
        self._con.close()

    def item(self, item_id: int) -> AcoreItem | None:
        row = self._con.execute("SELECT * FROM item WHERE entry = ?", (item_id,)).fetchone()
        if row is None:
            return None
        stats = tuple(
            (STAT_NAMES.get(row[f"stat_type{i}"], f"stat{row[f'stat_type{i}']}"), row[f"stat_value{i}"])
            for i in range(1, min(row["StatsCount"], 10) + 1) if row[f"stat_type{i}"] or row[f"stat_value{i}"]
        )
        sockets = tuple(
            SOCKET_COLORS.get(row[f"socketColor_{i}"], f"unknown({row[f'socketColor_{i}']})")
            for i in range(1, 4) if row[f"socketColor_{i}"]
        )
        return AcoreItem(
            row["entry"], row["name"], row["class"], row["subclass"], row["Quality"], row["InventoryType"],
            row["ItemLevel"], row["RequiredLevel"], stats, sockets, row["socketBonus"], row["GemProperties"],
            bool(row["ScalingStatDistribution"]),
        )

    def gem_quality(self, gem_properties_id: int) -> int | None:
        """Highest item quality among gem items (class 3) that use this GemProperties id."""
        row = self._con.execute("SELECT MAX(Quality) FROM item WHERE GemProperties = ? AND class = 3",
                                (gem_properties_id,)).fetchone()
        return row[0]

    def count(self) -> int:
        return self._con.execute("SELECT COUNT(*) FROM item").fetchone()[0]
