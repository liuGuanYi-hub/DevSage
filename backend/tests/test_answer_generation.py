import json
import os
import unittest
from unittest.mock import patch

from backend.app.ingestion.models import ChunkRecord
from backend.app.retrieval.models import SearchResult
from backend.app.services.answer_generation import (
    AnswerGenerationError,
    generate_grounded_answer,
)


def _evidence() -> list[SearchResult]:
    return [
        SearchResult(
            chunk=ChunkRecord(
                chunk_id="e1",
                source_path="docs/port.md",
                file_type="markdown",
                content="先使用 netstat 查询占用 8080 端口的 PID。",
                start_line=3,
                end_line=5,
            ),
            score=0.9,
            matched_terms=("8080", "PID"),
        )
    ]


class AnswerGenerationTests(unittest.TestCase):
    def test_offline_provider_does_not_call_remote_model(self) -> None:
        with patch.dict(os.environ, {"ANSWER_GENERATION_PROVIDER": "offline"}, clear=False):
            self.assertIsNone(
                generate_grounded_answer("8080 怎么排查？", "troubleshooting", _evidence())
            )

    def test_qwen_compatible_response_requires_evidence_marker(self) -> None:
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "answer": "先使用 netstat 查询 8080 端口的 PID。[E1]",
                                "key_steps": ["执行来源中给出的端口检查命令。"],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(response_payload, ensure_ascii=False).encode("utf-8")

        with patch.dict(
            os.environ,
            {
                "ANSWER_GENERATION_PROVIDER": "qwen",
                "ANSWER_GENERATION_API_URL": "https://example.invalid/v1/chat/completions",
                "ANSWER_GENERATION_API_KEY_ENV": "TEST_QWEN_KEY",
                "TEST_QWEN_KEY": "test-key",
                "ANSWER_GENERATION_MODEL": "qwen-test",
            },
            clear=False,
        ), patch("backend.app.services.answer_generation.urlopen", return_value=FakeResponse()):
            generated = generate_grounded_answer("8080 怎么排查？", "troubleshooting", _evidence())

        self.assertIsNotNone(generated)
        self.assertIn("[E1]", generated.answer)
        self.assertEqual(("执行来源中给出的端口检查命令。",), generated.key_steps)

    def test_qwen_response_without_evidence_marker_is_rejected(self) -> None:
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": '{"answer":"请检查端口。","key_steps":["检查"]}'
                    }
                }
            ]
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(response_payload).encode("utf-8")

        with patch.dict(
            os.environ,
            {
                "ANSWER_GENERATION_PROVIDER": "qwen",
                "ANSWER_GENERATION_API_URL": "https://example.invalid/v1/chat/completions",
                "ANSWER_GENERATION_API_KEY_ENV": "TEST_QWEN_KEY",
                "TEST_QWEN_KEY": "test-key",
            },
            clear=False,
        ), patch("backend.app.services.answer_generation.urlopen", return_value=FakeResponse()):
            with self.assertRaises(AnswerGenerationError):
                generate_grounded_answer("8080 怎么排查？", "troubleshooting", _evidence())


if __name__ == "__main__":
    unittest.main()
