import json
import unittest

from backend.app.mcp.server import MCPServer
from backend.app.services.index_service import IndexService


class MCPServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = MCPServer(IndexService())

    def test_initialize_and_list_tools(self) -> None:
        initialized = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            }
        )
        self.assertEqual("devsage", initialized["result"]["serverInfo"]["name"])
        listed = self.server.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertEqual(
            {
                "search_documents",
                "search_code",
                "read_file",
                "get_git_history",
                "generate_troubleshooting_report",
            },
            names,
        )

    def test_search_tool_returns_citations(self) -> None:
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "search_documents",
                    "arguments": {"query": "8080 端口占用", "source_root": "sample-data"},
                },
            }
        )
        self.assertFalse(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertTrue(payload)
        self.assertTrue(payload[0]["citation"])

    def test_read_file_rejects_escape_and_unknown_method_is_error(self) -> None:
        escaped = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "read_file",
                    "arguments": {"source_root": "sample-data", "source_path": "../README.md"},
                },
            }
        )
        self.assertTrue(escaped["result"]["isError"])
        unknown = self.server.handle_request(
            {"jsonrpc": "2.0", "id": 5, "method": "no/such/method", "params": {}}
        )
        self.assertEqual(-32601, unknown["error"]["code"])

    def test_notification_has_no_response(self) -> None:
        response = self.server.handle_request(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )
        self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()
