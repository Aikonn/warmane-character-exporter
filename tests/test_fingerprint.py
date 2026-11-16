import tempfile
import time
import unittest
from pathlib import Path

from warmane_exporter.cache import ResponseCache
from warmane_exporter.fingerprint import (
    cached_fingerprint,
    fingerprint_for_bodies,
    html_fingerprint,
    response_cache_keys,
    tool_version_hash,
)


class FingerprintTests(unittest.TestCase):
    def test_same_inputs_are_stable_and_body_or_tool_changes_change_hash(self):
        body = ("json", "summary", "talents")
        first = fingerprint_for_bodies("tool-v1", *body)
        self.assertEqual(fingerprint_for_bodies("tool-v1", *body), first)
        self.assertNotEqual(fingerprint_for_bodies("tool-v1", "changed", *body[1:]), first)
        self.assertNotEqual(fingerprint_for_bodies("tool-v2", *body), first)

    def test_tool_version_hash_tracks_sources_assets_and_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src" / "warmane_exporter" / "run.py"
            definitions = root / "library" / "definitions" / "client-export.json"
            items = root / "library" / "acore" / "items.db"
            config = root / "local.config"
            for path in (source, definitions, items, config):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"first")

            first = tool_version_hash(root, config)
            for path in (source, definitions, items, config):
                path.write_bytes(b"changed")
                self.assertNotEqual(tool_version_hash(root, config), first, path)
                path.write_bytes(b"first")

    def test_cached_fingerprint_uses_all_three_sources_and_requires_fresh_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = ResponseCache(Path(tmp) / "responses.sqlite")
            try:
                bodies = ("json body", "html body", "talents body")
                keys = response_cache_keys("Aikka", "Onyxia")
                now = time.time()
                for key, body in zip(keys, bodies, strict=True):
                    cache.put(key, key.split("|", 1)[0], body, now)

                expected = fingerprint_for_bodies("tool-v1", *bodies)
                self.assertEqual(
                    cached_fingerprint(cache, "Aikka", "Onyxia", "tool-v1", 7200, now),
                    expected,
                )
                self.assertIsNone(
                    cached_fingerprint(cache, "Aikka", "Onyxia", "tool-v1", 7200, now + 7200),
                )
                cache.put(keys[1], "warmane-html-summary", "changed body", now)
                self.assertNotEqual(
                    cached_fingerprint(cache, "Aikka", "Onyxia", "tool-v1", 7200, now),
                    expected,
                )
            finally:
                cache.close()

    def test_html_fingerprint_requires_one_valid_meta_value(self):
        fingerprint = "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.html"
            path.write_text(
                f'<meta name="warmane-fingerprint" content="{fingerprint}">',
                encoding="utf-8",
            )
            self.assertEqual(html_fingerprint(path), fingerprint)
            path.write_text(
                f'<meta name="warmane-fingerprint" content="{fingerprint}">'
                '<meta name="warmane-fingerprint" content="' + "b" * 64 + '">',
                encoding="utf-8",
            )
            self.assertIsNone(html_fingerprint(path))


if __name__ == "__main__":
    unittest.main()
