import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.app.services.project_registry import (
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
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"DEVSAGE_PROJECT_MANIFEST": "projects.json"}, clear=False):
                registry = ProjectRegistry.from_environment(root)
            self.assertEqual("docs-demo", registry.list_projects()[0].project_id)
            self.assertTrue(registry.resolve_source_root("docs-demo").is_dir())

    def test_manifest_rejects_absolute_path(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "projects.json").write_text("[]", encoding="utf-8")
            with patch.dict(os.environ, {"DEVSAGE_PROJECT_MANIFEST": str(root / "projects.json")}, clear=False):
                with self.assertRaises(ProjectRegistryError):
                    ProjectRegistry.from_environment(root)


if __name__ == "__main__":
    unittest.main()
