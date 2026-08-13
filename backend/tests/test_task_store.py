import json
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
        self.results = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params=None) -> None:
        normalized = " ".join(query.split()).lower()
        if normalized.startswith("insert into agent_tasks"):
            self.connection.payloads[params[0]] = params[5]
        elif normalized.startswith("select payload") and "order by" in normalized:
            values = list(params or ())
            limit = values[-1]
            project_id = values[0] if "payload->>'project_id' = %s" in normalized else None
            status_start = 1 if project_id is not None else 0
            statuses = set(values[status_start:-1]) if "payload->>'status' in" in normalized else None
            payloads = []
            for payload in self.connection.payloads.values():
                item = json.loads(payload)
                if project_id is not None and item.get("project_id") != project_id:
                    continue
                if statuses and item.get("status") not in statuses:
                    continue
                payloads.append(payload)
            if "runtime_ms" in normalized:
                payloads.sort(key=lambda payload: json.loads(payload)["usage"]["runtime_ms"], reverse="desc" in normalized)
            payloads = payloads[:limit]
            self.results = [(payload,) for payload in payloads]
        elif normalized.startswith("select payload"):
            payload = self.connection.payloads.get(params[0])
            self.result = (payload,) if payload is not None else None

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.results


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

    def test_task_history_returns_lightweight_newest_first_summaries(self) -> None:
        first = AgentRunner(IndexService()).run("用户接口入口在哪里", "sample-data")
        second = AgentRunner(IndexService()).run("8080 端口被占用怎么排查？", "sample-data")
        self.store.save(first)
        self.store.save(second)

        items = self.store.list(project_id=None, limit=10)

        self.assertEqual(2, len(items))
        self.assertEqual(second.task_id, items[0]["task_id"])
        self.assertEqual("troubleshooting", items[0]["category"])
        self.assertTrue(items[0]["evidence_count"] > 0)

    def test_task_history_filters_status_and_sorts_by_runtime(self) -> None:
        fast = AgentRunner(IndexService()).run("8080 绔彛琚崰鐢ㄦ€庝箞鎺掓煡锛?", "sample-data")
        slow = AgentRunner(IndexService()).run("Laravel 鐧诲綍鍚庤繕鏄洖 401 鎬庝箞鍔烇紵", "sample-data")
        fast.usage.runtime_ms = 10
        slow.usage.runtime_ms = 900
        slow.status = "failed"
        self.store.save(fast)
        self.store.save(slow)

        filtered = self.store.list(statuses={"failed"}, limit=10)
        ordered = self.store.list(sort_by="runtime_ms", sort_order="desc", limit=10)

        self.assertEqual([slow.task_id], [item["task_id"] for item in filtered])
        self.assertEqual(slow.task_id, ordered[0]["task_id"])


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

    def test_jsonb_task_history_lists_summaries(self) -> None:
        connection = FakeTaskConnection()
        store = PostgresTaskStateStore(connection_factory=lambda: connection)
        state = AgentRunner(IndexService()).run("用户接口入口在哪里", "sample-data", project_id="sample-data")
        store.save(state)

        items = store.list(project_id="sample-data", limit=10)

        self.assertEqual(1, len(items))
        self.assertEqual(state.task_id, items[0]["task_id"])

    def test_jsonb_task_history_filters_status_and_sorts_by_runtime(self) -> None:
        connection = FakeTaskConnection()
        store = PostgresTaskStateStore(connection_factory=lambda: connection)
        fast = AgentRunner(IndexService()).run("8080 端口被占用，应该怎么排查？", "sample-data", project_id="sample-data")
        slow = AgentRunner(IndexService()).run("Laravel 登录后还是 401 怎么办？", "sample-data", project_id="sample-data")
        fast.usage.runtime_ms = 10
        slow.usage.runtime_ms = 900
        slow.status = "failed"
        store.save(fast)
        store.save(slow)

        items = store.list(
            project_id="sample-data",
            statuses={"failed"},
            sort_by="runtime_ms",
            sort_order="desc",
            limit=10,
        )

        self.assertEqual([slow.task_id], [item["task_id"] for item in items])
