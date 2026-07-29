import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.services.code_writeback import (
    CodeChangePolicyError,
    CodeChangeWritebackService,
)


class CodeWritebackTests(unittest.TestCase):
    def test_preview_does_not_write_and_approval_applies_hash_checked_change(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "project/src/app.py"
            target.parent.mkdir(parents=True)
            target.write_text("print('old')\n", encoding="utf-8")
            service = CodeChangeWritebackService(root)

            preview = service.create_preview(
                source_root="project",
                target_path="src/app.py",
                proposed_content="print('new')\n",
                source_citations=["project/src/app.py:1"],
                project_id="demo",
            )

            self.assertEqual("pending", preview.status)
            self.assertEqual("demo", preview.project_id)
            self.assertEqual("update", preview.diff.operation)
            self.assertFalse("new" in target.read_text(encoding="utf-8"))

            approved = service.approve(preview.preview_id)
            self.assertEqual("approved", approved.status)
            self.assertEqual("print('new')\n", target.read_text(encoding="utf-8"))

    def test_stale_code_preview_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "project/app.py"
            (root / "project").mkdir()
            target.write_text("old\n", encoding="utf-8")
            service = CodeChangeWritebackService(root)
            preview = service.create_preview("project", "app.py", "new\n", [])

            target.write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(CodeChangePolicyError, "target changed"):
                service.approve(preview.preview_id)
            self.assertEqual("changed\n", target.read_text(encoding="utf-8"))

    def test_code_change_rejects_unsafe_or_empty_targets(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project").mkdir()
            (root / "project/app.py").write_text("content\n", encoding="utf-8")
            service = CodeChangeWritebackService(root)

            with self.assertRaises(CodeChangePolicyError):
                service.create_preview("project", "../outside.py", "new", [])
            with self.assertRaises(CodeChangePolicyError):
                service.create_preview("project", "app.py", "", [])


if __name__ == "__main__":
    unittest.main()
