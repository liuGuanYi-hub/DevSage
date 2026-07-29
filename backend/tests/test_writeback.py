import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.services.knowledge_writeback import (
    KnowledgeWritebackService,
    WritebackPolicyError,
)


class KnowledgeWritebackTests(unittest.TestCase):
    def test_preview_does_not_write_until_approval(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = KnowledgeWritebackService(root)
            preview = service.create_preview(
                title="端口排查",
                content="# 端口排查\n\n来源：sample-data/docs/springboot-errors.md",
                target_path="SpringBoot/端口排查.md",
                source_citations=["sample-data/docs/springboot-errors.md:1-8"],
            )
            self.assertEqual("pending", preview.status)
            self.assertEqual("create", preview.diff.operation)
            self.assertFalse(preview.diff.target_exists)
            self.assertGreater(preview.diff.additions, 0)
            self.assertFalse((root / "SpringBoot/端口排查.md").exists())

            approved = service.approve(preview.preview_id)
            self.assertEqual("approved", approved.status)
            self.assertTrue((root / "SpringBoot/端口排查.md").is_file())

    def test_update_preview_contains_diff_and_rejects_stale_approval(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "existing.md"
            target.write_text("# Old\n\nold content\n", encoding="utf-8")
            service = KnowledgeWritebackService(root)

            preview = service.create_preview(
                title="Updated note",
                content="# New\n\nnew content",
                target_path="existing.md",
                source_citations=[],
            )
            self.assertEqual("update", preview.diff.operation)
            self.assertTrue(preview.diff.target_exists)
            self.assertGreater(preview.diff.additions, 0)
            self.assertGreater(preview.diff.deletions, 0)
            self.assertTrue(any(line.startswith("@@") for line in preview.diff.unified_diff))

            target.write_text("# Changed by somebody else\n", encoding="utf-8")
            with self.assertRaisesRegex(WritebackPolicyError, "target changed"):
                service.approve(preview.preview_id)
            self.assertEqual("# Changed by somebody else\n", target.read_text(encoding="utf-8"))

    def test_approved_preview_cannot_be_approved_twice(self) -> None:
        with TemporaryDirectory() as temporary:
            service = KnowledgeWritebackService(temporary)
            preview = service.create_preview(
                title="One time approval",
                content="content",
                target_path="note.md",
                source_citations=[],
            )
            service.approve(preview.preview_id)
            with self.assertRaisesRegex(WritebackPolicyError, "already been approved"):
                service.approve(preview.preview_id)

    def test_preview_rejects_unsafe_target_path(self) -> None:
        service = KnowledgeWritebackService("data/approved-notes")
        with self.assertRaises(WritebackPolicyError):
            service.create_preview(
                title="Unsafe",
                content="content",
                target_path="../outside.md",
                source_citations=[],
            )


if __name__ == "__main__":
    unittest.main()
