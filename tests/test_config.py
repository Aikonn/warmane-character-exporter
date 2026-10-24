import tempfile
import unittest
from pathlib import Path

from warmane_exporter.config import (
    ConfigError,
    find_config_path,
    load_config,
    resolve_wow_client_dir,
)


class ConfigTests(unittest.TestCase):
    def test_default_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "warmane-character-exporter.config"
            config_path.write_text(
                "[default]\n"
                r"wow_client_dirs = ['C:\Games\WoW']" "\n",
                encoding="utf-8",
            )

            merged = load_config(config_path, hostname="ANY-HOST")
            self.assertEqual(merged["wow_client_dirs"], ["C:\\Games\\WoW"])

    def test_machine_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "warmane-character-exporter.config"
            config_path.write_text(
                "[default]\n"
                r"wow_client_dirs = ['C:\Default']" "\n"
                "[machines.MY-PC]\n"
                r"wow_client_dirs = ['E:\Machine']" "\n",
                encoding="utf-8",
            )

            merged = load_config(config_path, hostname="MY-PC")
            self.assertEqual(merged["wow_client_dirs"], ["E:\\Machine"])

    def test_case_insensitive_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "warmane-character-exporter.config"
            config_path.write_text(
                "[default]\n"
                r"wow_client_dirs = ['C:\Default']" "\n"
                "[machines.example-pc]\n"
                r"wow_client_dirs = ['E:\LowerCaseMatch']" "\n",
                encoding="utf-8",
            )

            merged = load_config(config_path, hostname="EXAMPLE-PC")
            self.assertEqual(merged["wow_client_dirs"], ["E:\\LowerCaseMatch"])

    def test_missing_file(self) -> None:
        missing_path = Path("Z:\\unlikely\\missing\\warmane-character-exporter.config")
        with self.assertRaisesRegex(ConfigError, "Copy warmane-character-exporter.config.template"):
            load_config(missing_path, hostname="HOST")

    def test_unknown_host_with_no_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "warmane-character-exporter.config"
            config_path.write_text(
                "[machines.OTHER-PC]\n"
                r"wow_client_dirs = ['E:\OnlyOtherMachine']" "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "UNMATCHED-HOST"):
                load_config(config_path, hostname="UNMATCHED-HOST")

    def test_first_existing_path_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "missing-client"
            second = Path(tmp) / "present-client"
            second.mkdir()

            resolved = resolve_wow_client_dir(
                {"wow_client_dirs": [str(first), str(second)]}
            )
            self.assertEqual(resolved, second)

    def test_invalid_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "warmane-character-exporter.config"
            config_path.write_text(r"[default" "\n" r"wow_client_dirs = ['C:\Bad']", encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "Invalid TOML"):
                load_config(config_path, hostname="HOST")

    def test_find_config_path_default(self) -> None:
        path = find_config_path()
        self.assertEqual(path.name, "warmane-character-exporter.config")


if __name__ == "__main__":
    unittest.main()
