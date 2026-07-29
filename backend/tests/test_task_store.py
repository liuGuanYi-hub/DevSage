import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from backend.app.agents.runner import AgentRunner
from backend.app.services.index_service import IndexService
from backend.app.services.task_store import (
    FileTaskStateStore,
    PostgresTaskStateStore,
    TaskStateError,
    TaskStateNotFoundError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FakeTaskCursor:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params=None) -> None:
        normalized = " ".join(query.split()).lower()
        if normalized.startswith("insert into agent_tasks"):
            self.connection.payloads[params[0]] = params[5]
        elif normalized.startswith("select payload"):
            payload = self.connection.payloads.get(params[0])
            self.result = (payload,) if payload is not None else None

    def fetchone(self):
        return self.result


class FakeTaskConnection:
    def __init__(self) -> None:
        self.payloads = {}

    def cursor(self):
        return FakeTaskCursor(self)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


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


class PostgresTaskStoreTests(unittest.TestCase):
    def test_jsonb_snapshot_round_trip_with_connection_boundary(self) -> None:
        connection = FakeTaskConnection()
        store = PostgresTaskStateStore(connection_factory=lambda: connection)
        state = AgentRunner(IndexService()).run("用户接口入口在哪里", "sample-data")

        task_id = store.save(state)
        restored = store.load(task_id)

        self.assertEqual(state.task_id, task_id)
        self.assertEqual(state.task_id, restored.task_id)
        self.assertEqual(state.answer.citations, restored.answer.citations)

    def test_missing_jsonb_snapshot_uses_same_not_found_contract(self) -> None:
        connection = FakeTaskConnection()
        store = PostgresTaskStateStore(connection_factory=lambda: connection)

        with self.assertRaises(TaskStateNotFoundError):
            store.load("missing-task")
