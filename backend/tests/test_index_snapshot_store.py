import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.app.ingestion.indexer import build_index
from backend.app.services.index_service import IndexService
from backend.app.services.index_snapshot_store import FileIndexSnapshotStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_ROOT = PROJECT_ROOT / "sample-data"


class IndexSnapshotStoreTests(unittest.TestCase):
    def test_snapshot_round_trip_preserves_documents_and_chunks(self) -> None:
        snapshot = build_index(SAMPLE_ROOT)
        with TemporaryDirectory() as temporary:
            store = FileIndexSnapshotStore(temporary)
            path = store.save("sample-data", snapshot)
            restored = store.load("sample-data")

            self.assertTrue(path.is_file())
            self.assertIsNotNone(restored)
            assert restored is not None
            self.assertEqual(snapshot.documents, restored.documents)
            self.assertEqual(snapshot.chunks, restored.chunks)
            self.assertIsNone(restored.stats)

    def test_corrupt_snapshot_is_ignored_and_can_be_rebuilt(self) -> None:
        with TemporaryDirectory() as temporary:
            store = FileIndexSnapshotStore(temporary)
            path = store.save("sample-data", build_index(SAMPLE_ROOT))
            path.write_text("not-json", encoding="utf-8")
            self.assertIsNone(store.load("sample-data"))

    def test_index_service_reuses_snapshot_after_process_restart(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "docs"
            source_root.mkdir()
            (source_root / "note.md").write_text(
                "# Stable note\n\ncontent\n", encoding="utf-8"
            )
            store = FileIndexSnapshotStore(root / "snapshots")
            with patch("backend.app.services.index_service.PROJECT_ROOT", root):
                first = IndexService(snapshot_store=store)
                _, first_snapshot = first.build("docs")
                second = IndexService(snapshot_store=store)
                _, second_snapshot = second.build("docs")

            self.assertEqual(1, first_snapshot.stats.added_documents)
            self.assertEqual(1, second_snapshot.stats.unchanged_documents)
            self.assertEqual(0, second_snapshot.stats.changed_documents)
            self.assertEqual(first_snapshot.chunks, second_snapshot.chunks)


if __name__ == "__main__":
    unittest.main()
