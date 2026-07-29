import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProjectStructureTests(unittest.TestCase):
    def test_required_stage_zero_files_exist(self) -> None:
        required_files = [
            "README.md",
            "pytest.ini",
            "DevSage长期任务路线图.md",
            "backend/app/main.py",
            "backend/app/ingestion/loaders.py",
            "backend/app/ingestion/chunkers.py",
            "backend/app/retrieval/keyword_search.py",
            "backend/app/retrieval/rrf.py",
            "backend/app/retrieval/embeddings.py",
            "backend/app/retrieval/vector_search.py",
            "backend/app/retrieval/hybrid_search.py",
            "backend/app/retrieval/provider_factory.py",
            "backend/app/storage/postgres_repository.py",
            "backend/tests/test_provider_adapters.py",
            "backend/app/services/index_service.py",
            "backend/app/services/index_snapshot_store.py",
            "backend/app/services/project_registry.py",
            "backend/app/services/knowledge_writeback.py",
            "backend/app/services/code_writeback.py",
            "backend/app/schemas/search.py",
            "backend/app/schemas/projects.py",
            "backend/app/schemas/code_changes.py",
            "backend/tests/test_api.py",
            "backend/tests/test_answer_service.py",
            "backend/app/agents/classifier.py",
            "backend/app/agents/state.py",
            "backend/app/agents/runner.py",
            "backend/app/agents/git_tools.py",
            "backend/app/agents/issue_tools.py",
            "backend/app/schemas/agent.py",
            "backend/tests/test_agent.py",
            "backend/tests/test_git_issue_tools.py",
            "backend/tests/test_writeback.py",
            "backend/tests/test_code_writeback.py",
            "backend/migrations/001_initial_schema.sql",
            "frontend/src/api/client.ts",
            "evaluation/reports/2026-07-30-keyword-hybrid-baseline.md",
            "evaluation/scripts/evaluate_keyword_baseline.py",
            "evaluation/scripts/evaluate_hybrid_baseline.py",
            "evaluation/scripts/evaluate_retrieval_strategies.py",
            "backend/requirements.txt",
            "backend/Dockerfile",
            "backend/.dockerignore",
            "docker-compose.yml",
            "frontend/package.json",
            "evaluation/datasets/devmind_mvp_questions.json",
            "evaluation/scripts/validate_mvp_dataset.py",
            "evaluation/scripts/evaluate_agent_grounding.py",
            "evaluation/scripts/smoke_mcp.py",
            "scripts/smoke-http.ps1",
            "scripts/preflight.ps1",
            "scripts/start-demo.ps1",
            "scripts/verify-offline.ps1",
            "scripts/smoke-docker.ps1",
            "docs/DevSage演示与API手册.md",
            "docs/DevSage演示脚本.md",
            "docs/DevSage交付就绪审计.md",
            "docs/diagrams/devsage-architecture.html",
            "docs/diagrams/devsage-agent.html",
            "sample-data/docs/springboot-errors.md",
            "sample-data/docs/laravel-auth.md",
        ]

        missing = [
            path
            for path in required_files
            if not (PROJECT_ROOT / path).is_file()
        ]
        self.assertEqual([], missing, f"Missing scaffold files: {missing}")

    def test_api_entrypoint_contains_health_route(self) -> None:
        main_source = (PROJECT_ROOT / "backend/app/main.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('app = FastAPI(', main_source)
        self.assertIn('@app.get("/health"', main_source)

    def test_container_health_and_build_context_are_declared(self) -> None:
        dockerfile = (PROJECT_ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
        compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        dockerignore = (PROJECT_ROOT / "backend/.dockerignore").read_text(encoding="utf-8")
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("healthcheck:", compose)
        self.assertIn("tests/", dockerignore)
        self.assertIn(".env", dockerignore)


if __name__ == "__main__":
    unittest.main()
