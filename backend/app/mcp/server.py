"""Minimal MCP-compatible JSON-RPC server for the DevSage demo.

The implementation intentionally uses only the Python standard library. It
keeps the tool contracts testable before an MCP SDK or host application is
introduced.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

from ..agents.git_tools import GitToolError, get_git_history
from ..agents.issue_tools import IssueToolError
from ..agents.runner import AgentRunner
from ..services.index_service import IndexService, PROJECT_ROOT, SourceRootError
from ..services.project_registry import ProjectRegistry, ProjectRegistryError
from ..services.troubleshooting import build_troubleshooting_report


SERVER_INFO = {
    "name": "devsage",
    "version": "0.1.0",
}


class MCPMethodNotFoundError(RuntimeError):
    """Raised when a JSON-RPC method is not part of the MCP surface."""

TOOL_DEFINITIONS = [
    {
        "name": "search_documents",
        "description": "Search indexed Markdown, configuration, and project documents with citations.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "source_root": {"type": "string", "default": "sample-data"},
                "project_id": {"type": "string", "description": "Registered project id; takes precedence over source_root."},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
        },
    },
    {
        "name": "search_code",
        "description": "Search indexed source code with transparent query expansions and citations.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "source_root": {"type": "string", "default": "sample-data"},
                "project_id": {"type": "string", "description": "Registered project id; takes precedence over source_root."},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
        },
    },
    {
        "name": "read_file",
        "description": "Read a bounded line range inside a configured source root.",
        "inputSchema": {
            "type": "object",
            "required": ["source_path"],
            "properties": {
                "source_root": {"type": "string", "default": "sample-data"},
                "project_id": {"type": "string", "description": "Registered project id; takes precedence over source_root."},
                "source_path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
        },
    },
    {
        "name": "get_git_history",
        "description": "Read recent local Git history without modifying the repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "default": ""},
                "repository_path": {"type": "string", "default": "."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
        },
    },
    {
        "name": "generate_troubleshooting_report",
        "description": "Combine document, Issue, and Git evidence into a cited troubleshooting report.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "source_root": {"type": "string", "default": "sample-data"},
                "project_id": {"type": "string", "description": "Registered project id; takes precedence over source_root."},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
        },
    },
]


class MCPServer:
    """Dispatch MCP lifecycle and tool requests over JSON-compatible values."""

    def __init__(
        self,
        index_service: IndexService | None = None,
        project_registry: ProjectRegistry | None = None,
    ) -> None:
        self.index_service = index_service or IndexService()
        self.project_registry = project_registry or ProjectRegistry.from_environment(PROJECT_ROOT)
        self.agent_runner = AgentRunner(self.index_service)
        self._tools: dict[str, Callable[[dict[str, Any]], Any]] = {
            "search_documents": self._search_documents,
            "search_code": self._search_code,
            "read_file": self._read_file,
            "get_git_history": self._get_git_history,
            "generate_troubleshooting_report": self._generate_troubleshooting_report,
        }

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC request; return None for notifications."""

        request_id = request.get("id")
        method = request.get("method")
        if method is None:
            return _error_response(request_id, -32600, "method is required")
        if request_id is None and str(method).startswith("notifications/"):
            return None

        try:
            result = self._dispatch(str(method), request.get("params") or {})
        except MCPMethodNotFoundError as exc:
            return _error_response(request_id, -32601, str(exc))
        except (SourceRootError, ProjectRegistryError, GitToolError, IssueToolError, ValueError) as exc:
            return _error_response(request_id, -32602, str(exc))
        except Exception:
            return _error_response(request_id, -32000, "internal MCP tool error")
        if request_id is None:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return {
                "protocolVersion": str(params.get("protocolVersion", "2025-06-18")),
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": TOOL_DEFINITIONS}
        if method == "tools/call":
            return self._call_tool(params)
        raise MCPMethodNotFoundError(f"unknown MCP method: {method}")

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or name not in self._tools:
            raise ValueError("unknown MCP tool")
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        try:
            value = self._tools[name](arguments)
        except (SourceRootError, ProjectRegistryError, GitToolError, IssueToolError, ValueError) as exc:
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(value, ensure_ascii=False),
                }
            ],
            "isError": False,
        }

    def _search_documents(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        query, source_root, top_k = self._search_arguments(arguments)
        _, results = self.index_service.search_hybrid(source_root, query, top_k)
        return [_result_dict(result) for result in results]

    def _search_code(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        query, source_root, top_k = self._search_arguments(arguments)
        results = self.index_service.search_code(source_root, query, top_k)
        return [_result_dict(result) for result in results]

    def _read_file(self, arguments: dict[str, Any]) -> dict[str, str]:
        source_root = self._resolve_source_root(arguments)
        source_path = arguments.get("source_path")
        if not isinstance(source_path, str) or not source_path:
            raise ValueError("source_path is required")
        start_line = int(arguments.get("start_line", 1))
        end_line = arguments.get("end_line")
        content = self.index_service.read_file(
            source_root,
            source_path,
            start_line=start_line,
            end_line=int(end_line) if end_line is not None else None,
        )
        return {"source_path": source_path, "start_line": start_line, "content": content}

    def _get_git_history(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        results = get_git_history(
            query=str(arguments.get("query", "")),
            repository_path=str(arguments.get("repository_path", ".")),
            limit=int(arguments.get("limit", 5)),
        )
        return [_result_dict(result) for result in results]

    def _generate_troubleshooting_report(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query, source_root, top_k = self._search_arguments(arguments)
        state = self.agent_runner.run(query, source_root, top_k)
        report = build_troubleshooting_report(query, state.evidence)
        return {
            "query": report.query,
            "summary": report.summary,
            "findings": [
                {
                    "source_type": finding.source_type,
                    "citations": list(finding.citations),
                    "snippets": list(finding.snippets),
                }
                for finding in report.findings
            ],
            "next_steps": list(report.next_steps),
            "citations": list(report.citations),
            "evidence_sufficient": report.evidence_sufficient,
        }

    def _search_arguments(self, arguments: dict[str, Any]) -> tuple[str, str, int]:
        query, _, top_k = _search_arguments(arguments)
        return query, self._resolve_source_root(arguments), top_k

    def _resolve_source_root(self, arguments: dict[str, Any]) -> str:
        project_id = arguments.get("project_id")
        if project_id is None:
            return str(arguments.get("source_root", "sample-data"))
        if not isinstance(project_id, str) or not project_id.strip():
            raise ProjectRegistryError("project_id must be a non-empty string")
        resolved = self.project_registry.resolve_source_root(project_id)
        return resolved.relative_to(PROJECT_ROOT).as_posix()


def run_stdio_server() -> None:
    """Read one JSON-RPC message per line and write one response per line."""

    server = MCPServer()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = server.handle_request(request)
        except (json.JSONDecodeError, TypeError):
            response = _error_response(None, -32700, "invalid JSON")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def _search_arguments(arguments: dict[str, Any]) -> tuple[str, str, int]:
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query is required")
    top_k = int(arguments.get("top_k", 5))
    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20")
    return query, str(arguments.get("source_root", "sample-data")), top_k


def _result_dict(result) -> dict[str, Any]:
    return {
        "citation": result.citation,
        "source_path": result.chunk.source_path,
        "start_line": result.chunk.start_line,
        "end_line": result.chunk.end_line,
        "score": result.score,
        "matched_terms": list(result.matched_terms),
        "content": result.chunk.content,
    }


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


if __name__ == "__main__":
    run_stdio_server()
