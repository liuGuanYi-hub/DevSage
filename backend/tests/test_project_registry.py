import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.app.services.project_registry import (
    ROLE_ACTIONS,
    OBSIDIAN_PROJECT_ID,
    ProjectRegistry,
    ProjectRegistryError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProjectRegistryTests(unittest.TestCase):
    def test_default_registry_exposes_sample_project_without_absolute_path(self) -> None:
        registry = ProjectRegistry(PROJECT_ROOT)
        project = registry.get("sample-data")
        self.assertEqual("sample-data", project.source_root)
        self.assertTrue(registry.resolve_source_root(project.project_id).is_dir())
        self.assertNotIn("\\", project.to_dict()["source_root"])
        self.assertIn("writeback_approve", project.to_dict()["roles"][1]["actions"])
        self.assertEqual("local-demo", project.to_dict()["members"][0]["actor_id"])
        self.assertIn("manage_project", project.to_dict()["members"][0]["actions"])
        self.assertEqual("operator", registry.role_for("sample-data", "local-demo"))
        self.assertEqual(
            "operator",
            registry.require_action("sample-data", "local-demo", "manage_project"),
        )
        with self.assertRaises(ProjectRegistryError):
            registry.require_action("sample-data", "unknown", "search")

    def test_manifest_load_is_confined_and_validated(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "projects.json").write_text(
                json.dumps(
                    [
                        {
                            "project_id": "docs-demo",
                            "name": "Docs Demo",
                            "source_root": "docs",
                            "description": "test project",
                            "roles": ["viewer"],
                            "members": {"alice": "viewer"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"DEVSAGE_PROJECT_MANIFEST": "projects.json"}, clear=False):
                registry = ProjectRegistry.from_environment(root)
            self.assertEqual("docs-demo", registry.list_projects()[0].project_id)
            self.assertTrue(registry.resolve_source_root("docs-demo").is_dir())
            self.assertEqual("viewer", registry.role_for("docs-demo", "alice"))
            self.assertIn("search", ROLE_ACTIONS["viewer"])
            with self.assertRaises(ProjectRegistryError):
                registry.require_action("docs-demo", "alice", "writeback_preview")

    def test_manifest_rejects_absolute_path(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "projects.json").write_text("[]", encoding="utf-8")
            with patch.dict(os.environ, {"DEVSAGE_PROJECT_MANIFEST": str(root / "projects.json")}, clear=False):
                with self.assertRaises(ProjectRegistryError):
                    ProjectRegistry.from_environment(root)

    def test_external_obsidian_registration_is_logical_and_read_only(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "Obsidian Vault"
            vault.mkdir()
            with patch.dict(
                os.environ,
                {
                    "DEVSAGE_PROJECT_MANIFEST": "",
                    "DEVSAGE_OBSIDIAN_VAULT_PATH": str(vault),
                },
                clear=False,
            ):
                registry = ProjectRegistry.from_environment(PROJECT_ROOT)

            project = registry.get(OBSIDIAN_PROJECT_ID)
            payload = project.to_dict()
            self.assertEqual(OBSIDIAN_PROJECT_ID, project.source_root)
            self.assertTrue(project.read_only)
            self.assertEqual("obsidian_vault", project.source_kind)
            self.assertEqual("vault_viewer", project.members[0][1])
            self.assertIn("index", payload["members"][0]["actions"])
            self.assertNotIn(str(vault), str(payload))
            self.assertEqual(vault.resolve(), registry.resolve_source_root(OBSIDIAN_PROJECT_ID))
            self.assertEqual({OBSIDIAN_PROJECT_ID: vault.resolve()}, registry.external_sources())
            with self.assertRaises(ProjectRegistryError):
                registry.require_action(OBSIDIAN_PROJECT_ID, "obsidian-viewer", "writeback_preview")


if __name__ == "__main__":
    unittest.main()
