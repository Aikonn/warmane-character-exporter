from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from warmane_exporter.checkpoint import ProbeCheckpointStore


class CheckpointTests(unittest.TestCase):
    def test_persists_cooldown_and_completed_requests(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            checkpoint_path = Path(tmp_dir) / "checkpoint.json"
            store = ProbeCheckpointStore(path=checkpoint_path)
            store.set_cooldown_until("armory.warmane.com", 1234.5)
            store.mark_completed("GET https://armory.warmane.com/x", "success")

            reloaded = ProbeCheckpointStore(path=checkpoint_path)
            self.assertEqual(reloaded.get_cooldown_until("armory.warmane.com"), 1234.5)
            self.assertTrue(reloaded.is_completed("GET https://armory.warmane.com/x"))


if __name__ == "__main__":
    unittest.main()
