"""Run a dependency-free smoke test against the MCP stdio server."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


REQUESTS = [
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18"},
    },
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_documents",
            "arguments": {
                "query": "8080 端口占用",
                "source_root": "sample-data",
                "top_k": 5,
            },
        },
    },
]


def main() -> None:
    payload = "\n".join(json.dumps(request, ensure_ascii=False) for request in REQUESTS) + "\n"
    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.mcp.server"],
        cwd=PROJECT_ROOT,
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=True,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    if len(responses) != 3:
        raise RuntimeError(f"expected 3 MCP responses, got {len(responses)}")
    if responses[0].get("result", {}).get("serverInfo", {}).get("name") != "devsage":
        raise RuntimeError("MCP initialize response did not identify devsage")
    tools = {
        tool["name"]
        for tool in responses[1].get("result", {}).get("tools", [])
    }
    required_tools = {
        "search_documents",
        "search_code",
        "read_file",
        "get_git_history",
        "generate_troubleshooting_report",
    }
    if not required_tools.issubset(tools):
        raise RuntimeError(f"MCP tool list is missing: {sorted(required_tools - tools)}")
    call_result = responses[2].get("result", {})
    if call_result.get("isError") or not call_result.get("content"):
        raise RuntimeError("MCP search_documents call did not return content")
    evidence = json.loads(call_result["content"][0]["text"])
    if not evidence or not evidence[0].get("citation"):
        raise RuntimeError("MCP search result did not include a citation")
    print(f"MCP smoke passed: tools={len(tools)}, citations={len(evidence)}")


if __name__ == "__main__":
    main()
