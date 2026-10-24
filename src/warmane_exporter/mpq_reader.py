"""Read-only MPQ (v1/v2) archive reader, standard library only.

Supports the subset needed for WoW 3.3.5a client data: hash/block tables,
single-unit and sector files, zlib and bzip2 compression, encryption.
Anything else (implode, huffman, adpcm, sparse, patch files) raises MPQError.
"""

from __future__ import annotations

import bz2
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

MPQ_MAGIC = b"MPQ\x1a"

FLAG_IMPLODE = 0x00000100
FLAG_COMPRESS = 0x00000200
FLAG_ENCRYPTED = 0x00010000
FLAG_FIX_KEY = 0x00020000
FLAG_PATCH = 0x00100000
FLAG_SINGLE_UNIT = 0x01000000
FLAG_DELETED = 0x02000000
FLAG_EXISTS = 0x80000000

HASH_TABLE_INDEX = 0
HASH_NAME_A = 1
HASH_NAME_B = 2
HASH_FILE_KEY = 3

EMPTY_BLOCK = 0xFFFFFFFF
MASK32 = 0xFFFFFFFF


class MPQError(Exception):
    """Raised for malformed or unsupported MPQ data."""


def _build_crypt_table() -> list[int]:
    table = [0] * 0x500
    seed = 0x00100001
    for index1 in range(0x100):
        index2 = index1
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp1 = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp2 = seed & 0xFFFF
            table[index2] = temp1 | temp2
            index2 += 0x100
    return table


CRYPT_TABLE = _build_crypt_table()


def hash_string(text: str, hash_type: int) -> int:
    seed1 = 0x7FED7FED
    seed2 = 0xEEEEEEEE
    base = hash_type * 0x100
    for char in text.upper().replace("/", "\\"):
        value = ord(char)
        seed1 = (CRYPT_TABLE[base + value] ^ (seed1 + seed2)) & MASK32
        seed2 = (value + seed1 + seed2 + (seed2 << 5) + 3) & MASK32
    return seed1


def decrypt_bytes(data: bytes, key: int) -> bytes:
    """Decrypt whole 32-bit words; trailing bytes (if any) are left as-is."""
    count = len(data) // 4
    words = list(struct.unpack_from(f"<{count}I", data))
    seed2 = 0xEEEEEEEE
    key &= MASK32
    for i in range(count):
        seed2 = (seed2 + CRYPT_TABLE[0x400 + (key & 0xFF)]) & MASK32
        plain = words[i] ^ ((key + seed2) & MASK32)
        words[i] = plain
        key = ((((~key) & MASK32) << 21) + 0x11111111) & MASK32 | (key >> 11)
        seed2 = (plain + seed2 + (seed2 << 5) + 3) & MASK32
    return struct.pack(f"<{count}I", *words) + data[count * 4 :]


@dataclass(frozen=True)
class _Block:
    offset: int
    packed_size: int
    file_size: int
    flags: int


def _decompress(data: bytes, expected: int) -> bytes:
    """Decompress one unit whose first byte is the compression mask."""
    if not data:
        raise MPQError("Empty compressed unit")
    mask = data[0]
    body = data[1:]
    if mask == 0x02:
        try:
            out = zlib.decompress(body)
        except zlib.error as exc:
            raise MPQError(f"zlib error: {exc}") from exc
    elif mask == 0x10:
        try:
            out = bz2.decompress(body)
        except (OSError, ValueError) as exc:
            raise MPQError(f"bzip2 error: {exc}") from exc
    else:
        raise MPQError(f"Unsupported compression mask 0x{mask:02X}")
    if len(out) != expected:
        raise MPQError(f"Decompressed size {len(out)} != expected {expected}")
    return out


class MPQArchive:
    """One opened MPQ archive. Use as a context manager."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._file = open(self.path, "rb")
        try:
            self._read_header()
            self._read_tables()
        except Exception:
            self._file.close()
            raise

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "MPQArchive":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _read_header(self) -> None:
        raw = self._file.read(32)
        if len(raw) < 32:
            raise MPQError("File too short for MPQ header")
        if raw[:4] != MPQ_MAGIC:
            raise MPQError(f"Invalid MPQ magic: {raw[:4]!r}")
        (
            header_size,
            _archive_size,
            _version,
            block_shift,
            hash_pos,
            block_pos,
            hash_count,
            block_count,
        ) = struct.unpack_from("<IIHHIIII", raw, 4)
        if header_size < 32:
            raise MPQError(f"Invalid header size {header_size}")
        if hash_count == 0 or hash_count & (hash_count - 1):
            raise MPQError(f"Hash table size {hash_count} is not a power of two")
        self.sector_size = 512 << block_shift
        self._hash_pos = hash_pos
        self._block_pos = block_pos
        self._hash_count = hash_count
        self._block_count = block_count

    def _read_exact(self, pos: int, size: int, what: str) -> bytes:
        self._file.seek(pos)
        data = self._file.read(size)
        if len(data) != size:
            raise MPQError(f"Truncated {what}")
        return data

    def _read_tables(self) -> None:
        raw = self._read_exact(self._hash_pos, self._hash_count * 16, "hash table")
        raw = decrypt_bytes(raw, hash_string("(hash table)", HASH_FILE_KEY))
        self._hashes = list(struct.iter_unpack("<IIHHI", raw))
        raw = self._read_exact(self._block_pos, self._block_count * 16, "block table")
        raw = decrypt_bytes(raw, hash_string("(block table)", HASH_FILE_KEY))
        self._blocks = [_Block(*item) for item in struct.iter_unpack("<IIII", raw)]

    def _find_block(self, name: str) -> _Block | None:
        start = hash_string(name, HASH_TABLE_INDEX) & (self._hash_count - 1)
        want_a = hash_string(name, HASH_NAME_A)
        want_b = hash_string(name, HASH_NAME_B)
        index = start
        for _ in range(self._hash_count):
            hash_a, hash_b, _locale, _platform, block_index = self._hashes[index]
            if block_index == EMPTY_BLOCK:
                return None
            if hash_a == want_a and hash_b == want_b and block_index < self._block_count:
                return self._blocks[block_index]
            index = (index + 1) & (self._hash_count - 1)
        return None

    def contains(self, name: str) -> bool:
        block = self._find_block(name)
        return block is not None and bool(block.flags & FLAG_EXISTS) and not block.flags & FLAG_DELETED

    def read(self, name: str) -> bytes | None:
        """Return file bytes, or None if absent. Raises MPQError if unsupported."""
        block = self._find_block(name)
        if block is None or not block.flags & FLAG_EXISTS or block.flags & FLAG_DELETED:
            return None
        if block.flags & FLAG_PATCH:
            raise MPQError(f"{name}: patch files are not supported")
        if block.flags & FLAG_IMPLODE:
            raise MPQError(f"{name}: implode compression is not supported")
        key = 0
        if block.flags & FLAG_ENCRYPTED:
            key = hash_string(name.replace("/", "\\").split("\\")[-1], HASH_FILE_KEY)
            if block.flags & FLAG_FIX_KEY:
                key = ((key + block.offset) ^ block.file_size) & MASK32
        compressed = bool(block.flags & FLAG_COMPRESS)

        if block.flags & FLAG_SINGLE_UNIT:
            data = self._read_exact(block.offset, block.packed_size, name)
            if key:
                data = decrypt_bytes(data, key)
            if compressed and block.packed_size < block.file_size:
                return _decompress(data, block.file_size)
            return data[: block.file_size]

        sectors = -(-block.file_size // self.sector_size)
        if not compressed:
            data = self._read_exact(block.offset, block.file_size, name)
            if key:
                data = b"".join(
                    decrypt_bytes(data[i * self.sector_size : (i + 1) * self.sector_size], key + i)
                    for i in range(sectors)
                )
            return data

        table = self._read_exact(block.offset, (sectors + 1) * 4, f"{name} sector table")
        if key:
            table = decrypt_bytes(table, (key - 1) & MASK32)
        offsets = struct.unpack(f"<{sectors + 1}I", table)
        parts: list[bytes] = []
        for i in range(sectors):
            start, end = offsets[i], offsets[i + 1]
            if end < start or end > block.packed_size:
                raise MPQError(f"{name}: invalid sector offsets")
            chunk = self._read_exact(block.offset + start, end - start, name)
            if key:
                chunk = decrypt_bytes(chunk, (key + i) & MASK32)
            expected = min(self.sector_size, block.file_size - i * self.sector_size)
            parts.append(_decompress(chunk, expected) if len(chunk) < expected else chunk)
        return b"".join(parts)


_BASE_ORDER = [
    "common.mpq",
    "common-2.mpq",
    "expansion.mpq",
    "lichking.mpq",
    "{loc}/locale-{loc}.mpq",
    "{loc}/expansion-locale-{loc}.mpq",
    "{loc}/lichking-locale-{loc}.mpq",
    "patch.mpq",
    "patch-2.mpq",
    "patch-3.mpq",
    "{loc}/patch-{loc}.mpq",
    "{loc}/patch-{loc}-2.mpq",
    "{loc}/patch-{loc}-3.mpq",
]


def archive_load_order(data_dir: str | Path, locale: str = "enUS") -> list[Path]:
    """Existing archives under a client Data folder, lowest priority first."""
    root = Path(data_dir)
    found: dict[str, Path] = {}
    for path in list(root.glob("*.[mM][pP][qQ]")) + list((root / locale).glob("*.[mM][pP][qQ]")):
        rel = path.relative_to(root).as_posix().lower()
        found[rel] = path
    known = [pattern.format(loc=locale).lower() for pattern in _BASE_ORDER]
    ordered = [found.pop(rel) for rel in known if rel in found]
    extras = sorted(found.items(), key=lambda item: (item[0].count("/") == 0, item[0]))
    return ordered + [path for _, path in extras]


class ClientData:
    """Reads files from a client Data folder, highest-priority archive wins."""

    def __init__(self, data_dir: str | Path, locale: str = "enUS") -> None:
        self.data_dir = Path(data_dir)
        if not self.data_dir.is_dir():
            raise MPQError(f"Data folder not found: {self.data_dir}")
        paths = archive_load_order(self.data_dir, locale)
        if not paths:
            raise MPQError(f"No MPQ archives found in {self.data_dir}")
        self.skipped: list[tuple[Path, str]] = []
        self._archives: list[MPQArchive] = []
        for path in paths:
            try:
                self._archives.append(MPQArchive(path))
            except (MPQError, OSError) as exc:
                self.skipped.append((path, str(exc)))
        if not self._archives:
            raise MPQError("No readable MPQ archives")

    def close(self) -> None:
        for archive in self._archives:
            archive.close()

    def __enter__(self) -> "ClientData":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def read(self, name: str) -> tuple[bytes, Path] | None:
        """Return (data, archive path) from the highest-priority archive."""
        for archive in reversed(self._archives):
            data = archive.read(name)
            if data is not None:
                return data, archive.path
        return None
