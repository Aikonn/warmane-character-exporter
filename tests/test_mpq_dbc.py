import bz2
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from warmane_exporter.dbc_parser import DbcError, DbcTable
from warmane_exporter.mpq_reader import (
    CRYPT_TABLE,
    ClientData,
    MPQArchive,
    MPQError,
    archive_load_order,
    hash_string,
)

M = 0xFFFFFFFF


def encrypt(data: bytes, key: int) -> bytes:
    """Test-side encryptor (inverse of the reader's decrypt, written separately)."""
    out = []
    seed2 = 0xEEEEEEEE
    for (plain,) in struct.iter_unpack("<I", data):
        seed2 = (seed2 + CRYPT_TABLE[0x400 + (key & 0xFF)]) & M
        out.append(plain ^ ((key + seed2) & M))
        key = (((~key << 21) + 0x11111111) | (key >> 11)) & M
        seed2 = (plain + seed2 + (seed2 << 5) + 3) & M
    return struct.pack(f"<{len(out)}I", *out)


def build_mpq(files: dict[str, bytes], mode: str = "zlib") -> bytes:
    """Build a real-layout MPQ v1 with one file per block (512-byte sectors)."""
    hash_size = 16
    shift = 0
    sector = 512 << shift
    header_len = 32
    blob = b""
    blocks = []
    data_start = header_len + hash_size * 16 + len(files) * 16
    for name, content in files.items():
        offset = data_start + len(blob)
        if mode == "single":
            flags = 0x80000000 | 0x01000000
            packed = content
            blob += packed
        else:
            flags = 0x80000000 | 0x00000200
            count = -(-len(content) // sector)
            chunks = []
            for i in range(count):
                piece = content[i * sector : (i + 1) * sector]
                if mode == "bzip2":
                    comp = b"\x10" + bz2.compress(piece)
                else:
                    comp = b"\x02" + zlib.compress(piece)
                chunks.append(comp if len(comp) < len(piece) else piece)
            pos = (count + 1) * 4
            offsets = [pos]
            for chunk in chunks:
                pos += len(chunk)
                offsets.append(pos)
            packed = struct.pack(f"<{count + 1}I", *offsets) + b"".join(chunks)
            blob += packed
        blocks.append((offset, len(packed), len(content), flags))

    hashes = [(M, M, 0xFFFF, 0xFFFF, M)] * hash_size
    for index, name in enumerate(files):
        slot = hash_string(name, 0) & (hash_size - 1)
        while hashes[slot][4] != M:
            slot = (slot + 1) & (hash_size - 1)
        hashes[slot] = (hash_string(name, 1), hash_string(name, 2), 0, 0, index)
    hash_raw = b"".join(struct.pack("<IIHHI", *h) for h in hashes)
    block_raw = b"".join(struct.pack("<IIII", *b) for b in blocks)
    hash_enc = encrypt(hash_raw, 0xC3AF3770)
    block_enc = encrypt(block_raw, 0xEC83B3A3)
    total = header_len + len(hash_enc) + len(block_enc) + len(blob)
    header = b"MPQ\x1a" + struct.pack(
        "<IIHHIIII", header_len, total, 0, shift, header_len,
        header_len + len(hash_enc), hash_size, len(blocks),
    )
    return header + hash_enc + block_enc + blob


def build_dbc(rows: list[tuple[int, ...]], strings: bytes = b"\x00") -> bytes:
    fields = len(rows[0])
    body = b"".join(struct.pack(f"<{fields}I", *r) for r in rows)
    return b"WDBC" + struct.pack("<IIII", len(rows), fields, fields * 4, len(strings)) + body + strings


class KnownAnswerTests(unittest.TestCase):
    def test_crypt_table_and_keys(self) -> None:
        self.assertEqual(CRYPT_TABLE[0], 0x55C636E2)
        self.assertEqual(hash_string("(hash table)", 3), 0xC3AF3770)
        self.assertEqual(hash_string("(block table)", 3), 0xEC83B3A3)


class MpqTests(unittest.TestCase):
    def _open(self, files: dict[str, bytes], mode: str = "zlib") -> MPQArchive:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "a.mpq"
        path.write_bytes(build_mpq(files, mode))
        archive = MPQArchive(path)
        self.addCleanup(archive.close)
        return archive

    def test_read_modes(self) -> None:
        big = bytes(range(256)) * 20 + b"tail"
        for mode in ("zlib", "bzip2", "single"):
            archive = self._open({"DBFilesClient\\X.dbc": big, "other.txt": b"hi"}, mode)
            self.assertEqual(archive.read("DBFilesClient\\X.dbc"), big, mode)
            self.assertEqual(archive.read("dbfilesclient/x.DBC"), big, mode)
            self.assertEqual(archive.read("other.txt"), b"hi", mode)

    def test_missing_file(self) -> None:
        archive = self._open({"a.txt": b"1"})
        self.assertIsNone(archive.read("nope.txt"))
        self.assertFalse(archive.contains("nope.txt"))

    def test_bad_magic_and_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.mpq"
            bad.write_bytes(b"XXXX" + bytes(40))
            with self.assertRaisesRegex(MPQError, "magic"):
                MPQArchive(bad)
            short = Path(tmp) / "short.mpq"
            short.write_bytes(b"MPQ\x1a")
            with self.assertRaisesRegex(MPQError, "short"):
                MPQArchive(short)
            cut = Path(tmp) / "cut.mpq"
            cut.write_bytes(build_mpq({"a": b"1"})[:100])
            with self.assertRaisesRegex(MPQError, "Truncated"):
                MPQArchive(cut)

    def test_unsupported_compression_mask(self) -> None:
        raw = bytearray(build_mpq({"a.txt": b"x" * 100}))
        archive_path_dir = tempfile.TemporaryDirectory()
        self.addCleanup(archive_path_dir.cleanup)
        # sector payload starts after tables; mask byte is the first byte after the sector table
        marker = b"\x02" + zlib.compress(b"x" * 100)
        position = bytes(raw).index(marker)
        raw[position] = 0x08
        path = Path(archive_path_dir.name) / "u.mpq"
        path.write_bytes(bytes(raw))
        with MPQArchive(path) as archive:
            with self.assertRaisesRegex(MPQError, "Unsupported compression"):
                archive.read("a.txt")


class ClientDataTests(unittest.TestCase):
    def test_priority_patch_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "enUS").mkdir()
            (data / "common.MPQ").write_bytes(build_mpq({"f.txt": b"old", "only.txt": b"base"}))
            (data / "patch-3.MPQ").write_bytes(build_mpq({"f.txt": b"new"}))
            (data / "enUS" / "locale-enUS.MPQ").write_bytes(build_mpq({"g.txt": b"loc"}))
            names = [p.name.lower() for p in archive_load_order(data)]
            self.assertEqual(names, ["common.mpq", "locale-enus.mpq", "patch-3.mpq"])
            with ClientData(data) as client:
                self.assertEqual(client.read("f.txt")[0], b"new")
                self.assertEqual(client.read("only.txt")[0], b"base")
                self.assertEqual(client.read("g.txt")[0], b"loc")
                self.assertIsNone(client.read("missing.txt"))

    def test_corrupt_archive_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "common.MPQ").write_bytes(build_mpq({"f.txt": b"ok"}))
            (data / "patch.MPQ").write_bytes(b"garbage" * 10)
            with ClientData(data) as client:
                self.assertEqual(len(client.skipped), 1)
                self.assertEqual(client.read("f.txt")[0], b"ok")

    def test_missing_folder(self) -> None:
        with self.assertRaises(MPQError):
            ClientData("Z:\\definitely\\missing")


class DbcTests(unittest.TestCase):
    def test_rows_find_and_strings(self) -> None:
        strings = b"\x00Hello\x00World\x00"
        table = DbcTable(build_dbc([(10, 1, 6), (20, 2, 12)], strings))
        self.assertEqual(len(table), 2)
        self.assertEqual(table.row(1), (20, 2, 12))
        self.assertEqual(table.find(10), (10, 1, 6))
        self.assertIsNone(table.find(99))
        self.assertEqual(table.string_at(1), "Hello")
        self.assertEqual(table.string_at(7), "World")
        self.assertIsNone(table.string_at(3))   # mid-string
        self.assertIsNone(table.string_at(0))   # empty string
        self.assertIsNone(table.string_at(500))

    def test_bad_inputs(self) -> None:
        good = build_dbc([(1, 2)])
        with self.assertRaisesRegex(DbcError, "magic"):
            DbcTable(b"XXXX" + good[4:])
        with self.assertRaisesRegex(DbcError, "short"):
            DbcTable(b"WDBC")
        with self.assertRaisesRegex(DbcError, "Truncated"):
            DbcTable(good[:-2])
        broken = bytearray(good)
        broken[12:16] = struct.pack("<I", 7)
        with self.assertRaisesRegex(DbcError, "Record size"):
            DbcTable(bytes(broken))


if __name__ == "__main__":
    unittest.main()
