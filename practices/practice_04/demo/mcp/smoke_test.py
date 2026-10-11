#!/usr/bin/env python3
"""Smoke test that talks to project_check_server.py over the real MCP stdio
transport.

It is an MCP *client*: it spawns the server as a subprocess, performs the
``initialize`` handshake, lists tools, then calls the tool with a good value
and a bad value.

To prove working-directory independence, the server is launched with a
working directory that is deliberately *not* the project directory.

Run:

    python3 mcp/smoke_test.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER = HERE / "project_check_server.py"

# Deliberately run the server from a directory that is *not* the project root,
# to prove the tool is independent of the caller's working directory. A project
# subdirectory is used so no path outside the project is required.
FOREIGN_CWD = str(HERE.parent / "tests")


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=FOREIGN_CWD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    next_id = 0

    def call(method, params=None, notify=False):
        nonlocal next_id
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notify:
            next_id += 1
            message["id"] = next_id
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
        if notify:
            return None
        line = proc.stdout.readline()
        return json.loads(line)

    init = call(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "1.0.0"},
        },
    )
    print("== initialize ==")
    print(json.dumps(init, ensure_ascii=False, indent=2))

    call("notifications/initialized", notify=True)

    tools = call("tools/list")
    print("\n== tools/list ==")
    print(json.dumps([t["name"] for t in tools["result"]["tools"]], ensure_ascii=False))

    good = call("tools/call", {"name": "run_project_check", "arguments": {"check": "tests"}})
    print("\n== tools/call check=tests ==")
    print(json.dumps(good, ensure_ascii=False, indent=2))

    bad = call("tools/call", {"name": "run_project_check", "arguments": {"check": "deploy"}})
    print("\n== tools/call check=deploy (unsupported) ==")
    print(json.dumps(bad, ensure_ascii=False, indent=2))

    proc.stdin.close()
    proc.terminate()
    proc.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
