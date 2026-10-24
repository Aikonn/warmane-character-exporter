"""WDBC table reader operating on bytes (no temp files)."""

from __future__ import annotations

import struct
from dataclasses import dataclass


class DbcError(Exception):
    """Raised for malformed DBC data."""


@dataclass(frozen=True)
class DbcHeader:
    record_count: int
    field_count: int
    record_size: int
    string_block_size: int


class DbcTable:
    """Lazy WDBC table. Fields are raw uint32 values; field 0 is the row key."""

    HEADER_SIZE = 20

    def __init__(self, data: bytes) -> None:
        if len(data) < self.HEADER_SIZE:
            raise DbcError("File too short for DBC header")
        if data[:4] != b"WDBC":
            raise DbcError(f"Invalid DBC magic: {data[:4]!r}")
        records, fields, rec_size, str_size = struct.unpack_from("<IIII", data, 4)
        if fields * 4 != rec_size:
            raise DbcError(f"Record size {rec_size} != field count {fields} * 4")
        total = self.HEADER_SIZE + records * rec_size + str_size
        if len(data) < total:
            raise DbcError(f"Truncated DBC: need {total} bytes, have {len(data)}")
        self.header = DbcHeader(records, fields, rec_size, str_size)
        self._data = data
        self._rows_end = self.HEADER_SIZE + records * rec_size
        self._strings = data[self._rows_end : total]
        self._index: dict[int, int] | None = None

    def __len__(self) -> int:
        return self.header.record_count

    def row(self, position: int) -> tuple[int, ...]:
        if not 0 <= position < self.header.record_count:
            raise IndexError(position)
        offset = self.HEADER_SIZE + position * self.header.record_size
        return struct.unpack_from(f"<{self.header.field_count}I", self._data, offset)

    def find(self, key: int) -> tuple[int, ...] | None:
        """Row whose field 0 equals key."""
        if self._index is None:
            size = self.header.record_size
            self._index = {
                struct.unpack_from("<I", self._data, self.HEADER_SIZE + i * size)[0]: i
                for i in range(self.header.record_count)
            }
        position = self._index.get(key)
        return None if position is None else self.row(position)

    def string_at(self, offset: int) -> str | None:
        """String starting exactly at a string boundary, else None."""
        strings = self._strings
        if offset <= 0 or offset >= len(strings) or strings[offset - 1] != 0:
            return None
        end = strings.find(b"\x00", offset)
        if end <= offset:
            return None
        return strings[offset:end].decode("utf-8", errors="replace")
