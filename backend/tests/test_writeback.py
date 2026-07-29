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
            self.assertFalse((root / "SpringBoot/端口排查.md").exists())

            approved = service.approve(preview.preview_id)
            self.assertEqual("approved", approved.status)
            self.assertTrue((root / "SpringBoot/端口排查.md").is_file())

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

