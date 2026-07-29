import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from backend.app.agents.runner import AgentRunner
from backend.app.services.index_service import IndexService
from backend.app.services.task_store import FileTaskStateStore, TaskStateError


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TaskStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = PROJECT_ROOT / "data" / f".test-task-state-{uuid4().hex}"
        self.store = FileTaskStateStore(self.root)

    def tearDown(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)

    def test_explicit_snapshot_round_trip(self) -> None:
        state = AgentRunner(IndexService()).run("用户接口入口在哪里", "sample-data")
        path = self.store.save(state)
        restored = self.store.load(state.task_id)
        self.assertTrue(path.is_file())
        self.assertEqual(state.task_id, restored.task_id)
        self.assertEqual(state.answer.citations, restored.answer.citations)

    def test_task_id_is_confined_to_the_store(self) -> None:
        with self.assertRaises(TaskStateError):
            self.store.load("../outside")
