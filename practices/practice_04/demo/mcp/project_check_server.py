#!/usr/bin/env python3
"""project-check-mcp: a minimal Model Context Protocol (MCP) server over stdio.

It exposes exactly one tool, ``run_project_check``, which runs this project's
existing test runner (``scripts/check.sh``) and reports the outcome.

Why this is a real MCP server
-----------------------------
This process speaks the actual MCP protocol: JSON-RPC 2.0 messages framed one
per line on stdin/stdout (the MCP stdio transport), with the ``initialize``
handshake, ``tools/list`` and ``tools/call`` methods, and standard result and
error shapes. It is *not* a plain Python function that was renamed "MCP"; an
MCP client such as OpenCode can launch it and call the tool.

Safety properties
-----------------
* No third-party dependency: standard library only (see ``mcp/README.md``).
* The command that may be executed is fixed and derived from *this file's*
  location, so the tool behaves identically no matter which working directory
  the caller uses.
* The tool never accepts a shell command or a path from the model. Its only
  argument is ``check`` and the only supported value is ``"tests"``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SERVER_NAME = "project-check-mcp"
SERVER_VERSION = "1.0.0"

# __file__ is <demo>/mcp/project_check_server.py, so parents[1] is <demo>.
# Deriving the project root from the file (not from the current directory) is
# what makes the tool independent of the caller's working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The one and only command this server is allowed to run.
RUNNER = PROJECT_ROOT / "scripts" / "check.sh"

# check value -> script to run. Anything not in this map is rejected.
ALLOWED_CHECKS = {"tests": RUNNER}

DEFAULT_PROTOCOL_VERSION = "2024-11-05"
SUPPORTED_PROTOCOL_VERSIONS = {
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
}

RUN_TIMEOUT_SECONDS = 300

TOOL = {
    "name": "run_project_check",
    "description": (
        "Run this project's automated checks through the existing runner "
        "scripts/check.sh and return success, exit_code, stdout and stderr. "
        'Supported value for "check": "tests" (runs the unittest suite). '
        "Works regardless of the caller's current working directory."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "check": {
                "type": "string",
                "description": 'Which check to run. Supported value: "tests".',
            }
        },
        "required": ["check"],
        "additionalProperties": False,
    },
}


class ProtocolError(Exception):
    """A JSON-RPC protocol-level error (not a tool-result error)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def run_check(check):
    """Run the requested check and return ``(payload, is_error)``.

    ``payload`` is always a plain dict and is never a shell string, so the
    caller can always see success/exit_code/stdout/stderr or a clear error.
    """
    script = ALLOWED_CHECKS.get(check) if isinstance(check, str) else None
    if script is None:
        allowed = ", ".join(f'"{name}"' for name in sorted(ALLOWED_CHECKS))
        message = f"Unsupported check: {check!r}. Allowed values: {allowed}."
        return {"check": check, "success": False, "error": message}, True

    try:
        completed = subprocess.run(
            ["bash", str(script)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        payload = {
            "check": check,
            "success": False,
            "exit_code": None,
            "stdout": stdout,
            "stderr": f"{stderr}\n[timeout after {RUN_TIMEOUT_SECONDS}s]".strip(),
        }
        return payload, True

    success = completed.returncode == 0
    payload = {
        "check": check,
        "success": success,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    # A failing check is reported as an error result (and never hidden), but
    # the payload still carries the full output.
    return payload, not success


def handle_tools_call(params):
    name = params.get("name")
    if name != TOOL["name"]:
        raise ProtocolError(-32602, f"Unknown tool: {name!r}")
    arguments = params.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ProtocolError(-32602, "`arguments` must be an object")

    payload, is_error = run_check(arguments.get("check"))
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        "structuredContent": payload,
        "isError": is_error,
    }


def dispatch(message):
    """Handle one JSON-RPC message; return a response dict or None."""
    method = message.get("method")
    has_id = "id" in message
    request_id = message.get("id")

    if method == "initialize":
        params = message.get("params") or {}
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": [TOOL]}}

    if method == "tools/call":
        try:
            result = handle_tools_call(message.get("params") or {})
        except ProtocolError:
            raise
        except Exception as exc:  # never crash the loop on a tool error
            result = {
                "content": [{"type": "text", "text": f"Internal error: {exc}"}],
                "isError": True,
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"resources": []}}

    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"prompts": []}}

    if method == "logging/setLevel":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    # Notifications (no id) are acknowledged by doing nothing.
    if not has_id:
        return None

    raise ProtocolError(-32601, f"Method not found: {method!r}")


def send(message):
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}})
            continue

        batch = message if isinstance(message, list) else [message]
        responses = []
        for item in batch:
            try:
                response = dispatch(item)
            except ProtocolError as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": item.get("id"),
                    "error": {"code": exc.code, "message": exc.message},
                }
            if response is not None:
                responses.append(response)

        if responses:
            send(responses if isinstance(message, list) else responses[0])


if __name__ == "__main__":
    main()
