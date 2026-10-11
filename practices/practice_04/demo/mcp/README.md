# project-check-mcp

A local [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server
that exposes one tool, `run_project_check`, to OpenCode. The tool runs this
project's existing runner `scripts/check.sh` and returns the result.

## Why this is a real MCP server

The process implements the actual MCP protocol on the **stdio transport**:
newline-delimited JSON-RPC 2.0 messages on stdin/stdout, the `initialize`
handshake, `tools/list` and `tools/call`, and standard result/error shapes.
OpenCode launches it as a child process and calls the tool over that protocol.
It is not a plain Python function that happens to be named "MCP".

You can see the protocol directly with the bundled client `smoke_test.py`.

## Files

| File | Purpose |
| --- | --- |
| `mcp/project_check_server.py` | The MCP server (stdio transport, stdlib only). |
| `mcp/smoke_test.py` | A tiny MCP client that exercises the server over stdio. |
| `.opencode/opencode.jsonc` | Project-local OpenCode configuration that registers the server. |

## Dependencies / installation

**None.** The server uses only the Python standard library, so there is nothing
to install and no third-party package is added to the project. It runs with the
system `python3` (tested with CPython 3.14).

If a future change ever needed a third-party MCP SDK, it should be installed in
an isolated virtual environment (see "Isolation" below) and must not be added
to the Python service's dependencies.

### Isolation (only relevant if third-party packages are ever added)

```sh
python3 -m venv .opencode/mcp-venv
.opencode/mcp-venv/bin/pip install <package>
```

Then point the server `command` at `.opencode/mcp-venv/bin/python`. This is not
needed today.

## OpenCode configuration

The server is registered in `.opencode/opencode.jsonc` using the V2 shape
(`mcp.servers`, `type: "local"`, `command` as an array):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "project-check-mcp": {
        "type": "local",
        "command": ["python3", "mcp/project_check_server.py"],
        "cwd": ".",
        "disabled": false
      }
    }
  }
}
```

Verify the connection from `demo/`:

```sh
opencode mcp list
# ✓ project-check-mcp  connected
```

## Tool contract

Tool name: `run_project_check`

| Argument | Type | Notes |
| --- | --- | --- |
| `check` | string | Only supported value: `"tests"`. |

Result payload (also returned as the JSON text content of the MCP result):

```json
{
  "check": "tests",
  "success": true,
  "exit_code": 0,
  "stdout": "...",
  "stderr": "..."
}
```

* `success` is `true` only when the runner exits with code `0`.
* `stdout` and `stderr` are returned in full; a failing suite is never hidden
  (`isError` is set when `success` is `false`).
* The tool runs `scripts/check.sh` with the project root as the working
  directory, computed from the server file's own location, so it behaves the
  same no matter where the caller's current working directory is.

### Unsupported value

For any `check` other than `"tests"` the server **runs no command** and returns
a controlled error naming the allowed value:

```json
{
  "check": "deploy",
  "success": false,
  "error": "Unsupported check: 'deploy'. Allowed values: \"tests\"."
}
```

## Running the checks

```sh
# MCP-level smoke test (spawns the server, does the handshake, calls the tool)
python3 mcp/smoke_test.py
```

The project test suite stays the single source of truth:

```sh
./scripts/check.sh
```

## Safety

* The executable and its path are fixed in the server; the model cannot pass a
  shell command or a path.
* The only accepted argument is `check`, restricted to the allow-list
  `{"tests"}`.
* Server diagnostics never go to stdout (only protocol messages do).
