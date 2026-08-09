import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.ingestion.indexer import build_index
from backend.app.services.index_service import IndexService
from backend.app.services.index_snapshot_store import FileIndexSnapshotStore
from backend.app.services.project_registry import ProjectDefinition, ProjectRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ExternalVaultTests(unittest.TestCase):
    def test_external_vault_uses_devsage_snapshot_and_relative_line_citations(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "Obsidian Vault"
            vault.mkdir()
            note = vault / "04-Research" / "DevSage.md"
            note.parent.mkdir()
            note.write_text(
                "# DevSage\n\nExternal Vault relative citation\n",
                encoding="utf-8",
            )
            obsidian = ProjectDefinition(
                project_id="obsidian-vault",
                name="Obsidian Vault",
                source_root="obsidian-vault",
                description="test",
                roles=("vault_viewer",),
                members=(("obsidian-viewer", "vault_viewer"),),
                external_path=vault,
                read_only=True,
                source_kind="obsidian_vault",
            )
            registry = ProjectRegistry(PROJECT_ROOT, (obsidian,))
            snapshot_store = FileIndexSnapshotStore(root / "devsage-data")
            service = IndexService(
                snapshot_store=snapshot_store,
                external_roots=registry.external_sources(),
            )

            source_root, snapshot = service.build("obsidian-vault")
            _, results = service.search("obsidian-vault", "relative citation", top_k=5)
            content = service.read_file("obsidian-vault", "04-Research/DevSage.md", 1, 3)

            self.assertEqual("obsidian-vault", source_root)
            self.assertEqual(["04-Research/DevSage.md"], [item.source_path for item in snapshot.documents])
            self.assertTrue(results)
            self.assertEqual("04-Research/DevSage.md", results[0].chunk.source_path)
            self.assertGreaterEqual(results[0].chunk.start_line, 1)
            self.assertLessEqual(results[0].chunk.start_line, results[0].chunk.end_line)
            self.assertEqual("04-Research/DevSage.md:1-3", results[0].citation)
            self.assertIn("External Vault relative citation", content)
            self.assertTrue(list((root / "devsage-data").glob("*.json")))
            self.assertFalse((vault / "data").exists())

    def test_build_index_keeps_external_source_path_relative(self) -> None:
        with TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "note.md").write_text("# Note\n", encoding="utf-8")
            snapshot = build_index(vault)
            self.assertEqual("note.md", snapshot.documents[0].source_path)
            self.assertFalse(Path(snapshot.documents[0].source_path).is_absolute())


if __name__ == "__main__":
    unittest.main()
