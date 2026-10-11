/**
 * check-after-edit — an OpenCode V2 local plugin.
 *
 * After the agent *successfully* runs a file-editing tool (write / edit /
 * apply_patch / ...) that touches a Python file inside this project, the plugin
 * runs the project's fixed runner `scripts/check.sh` and appends the result to
 * the tool result, so the model sees it in the same tool call:
 *
 *     AUTO CHECK PASS   — the runner exited with code 0
 *     AUTO CHECK FAIL   — the runner exited with a non-zero code
 *
 * Compatibility with OpenCode 2.0.20
 * ----------------------------------
 * The V2 plugin contract is a default export with `id` and `setup(ctx)`; the
 * docs also show `Plugin.define({...})`, which is an identity helper used for
 * typing. The SDK package installed for this OpenCode is
 * `@opencode-ai/plugin@1.18.29`, which does not export `Plugin.define` from its
 * entry point, and the runtime does not provide a bare `@opencode/plugin`
 * module. The V2 docs state that "V2 reads the default export's id and setup()",
 * so this plugin exports the equivalent plain definition object directly and
 * needs no SDK import. The hook itself uses the V2 runtime API
 * `ctx.tool.hook("execute.after", ...)`.
 *
 * Safety
 * ------
 * - The runner path is fixed and derived from *this file's* location, so it is
 *   independent of the agent's current working directory and the model cannot
 *   substitute another command.
 * - The check runs only for successful edits of `.py` files that live inside
 *   this project. Reads, searches, and ordinary shell commands are ignored.
 * - A recursion guard and a timeout protect against re-entrancy and hangs.
 * - Failures are reported verbatim; a failed check is never turned into a pass.
 */

import { spawnSync } from "node:child_process"
import { dirname, isAbsolute, relative, resolve } from "node:path"
import { fileURLToPath } from "node:url"

// <project>/.opencode/plugins/check-after-edit.js -> <project>
const PLUGIN_DIR = dirname(fileURLToPath(import.meta.url))
const PROJECT_DIR = resolve(PLUGIN_DIR, "..", "..")

// The single, fixed command this plugin is allowed to run.
const RUNNER = resolve(PROJECT_DIR, "scripts", "check.sh")

const RUNNER_TIMEOUT_MS = 60_000
const MAX_OUTPUT_CHARS = 4_000

const EDIT_TOOLS = new Set([
  "write",
  "edit",
  "multiedit",
  "apply_patch",
  "patch",
  "create",
  "update",
  "notebookedit",
])
const EDIT_TOOL_PATTERN = /(^|[^a-z])(write|edit|multiedit|apply_patch|patch)([^a-z]|$)/i

// Tool-input keys that carry a file path for write/edit-style tools.
const PATH_KEYS = ["filePath", "filepath", "file_path", "path", "file", "filename", "target"]
// Directives that name files inside an apply_patch / unified-diff payload.
const PATCH_PATH_PATTERNS = [
  /^\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+?)\s*$/,
  /^\*\*\*\s+Move\s+to:\s*(.+?)\s*$/,
  /^diff --git\s+a\/(.+?)\s+b\//,
  /^\+\+\+\s+b\/(.+?)\s*$/,
  /^---\s+a\/(.+?)\s*$/,
]

// Recursion guard: never let a check trigger another check.
let checkInProgress = false

function isEditTool(name) {
  if (!name) return false
  const value = String(name).toLowerCase()
  return EDIT_TOOLS.has(value) || EDIT_TOOL_PATTERN.test(value)
}

function collectStrings(value, out) {
  if (value == null) return
  if (typeof value === "string") {
    out.push(value)
  } else if (Array.isArray(value)) {
    for (const item of value) collectStrings(item, out)
  } else if (typeof value === "object") {
    for (const item of Object.values(value)) collectStrings(item, out)
  }
}

function resolveFromProjectAndCwd(candidate) {
  if (isAbsolute(candidate)) return [resolve(candidate)]
  // Try the path relative to the project root and relative to the agent's cwd.
  return [resolve(PROJECT_DIR, candidate), resolve(process.cwd(), candidate)]
}

function isInsideProject(absolutePath) {
  const rel = relative(PROJECT_DIR, absolutePath)
  return rel !== "" && !rel.startsWith("..") && !isAbsolute(rel)
}

// Collect values stored under known path-like keys (not arbitrary text).
function collectPathValues(value, out) {
  if (value == null || typeof value !== "object") return
  if (Array.isArray(value)) {
    for (const item of value) collectPathValues(item, out)
    return
  }
  for (const [key, item] of Object.entries(value)) {
    if (PATH_KEYS.includes(key)) {
      if (typeof item === "string") out.push(item)
      else if (Array.isArray(item)) for (const entry of item) if (typeof entry === "string") out.push(entry)
    }
    if (item && typeof item === "object") collectPathValues(item, out)
  }
}

// Extract file names referenced by apply_patch / unified-diff directives.
function collectPatchPaths(input, out) {
  const strings = []
  collectStrings(input, strings)
  for (const text of strings) {
    for (const line of String(text).split(/\r?\n/)) {
      for (const pattern of PATCH_PATH_PATTERNS) {
        const match = line.match(pattern)
        if (match) out.push(match[1].trim())
      }
    }
  }
}

// Return the `.py` files inside the project that a tool input refers to. Only
// explicit path fields and patch directives are considered, never file content.
function changedPythonFiles(input) {
  const candidates = []
  collectPathValues(input, candidates)
  collectPatchPaths(input, candidates)

  const inside = new Set()
  for (const candidate of candidates) {
    for (const absolute of resolveFromProjectAndCwd(candidate)) {
      if (/\.py$/i.test(absolute) && isInsideProject(absolute)) inside.add(absolute)
    }
  }
  return [...inside]
}

function tail(text) {
  const value = (text ?? "").toString()
  if (!value) return "(empty)"
  if (value.length <= MAX_OUTPUT_CHARS) return value
  const omitted = value.length - MAX_OUTPUT_CHARS
  return `…(${omitted} chars omitted)…\n${value.slice(-MAX_OUTPUT_CHARS)}`
}

function runRunner() {
  const startedAt = Date.now()
  const result = spawnSync("bash", [RUNNER], {
    cwd: PROJECT_DIR,
    encoding: "utf8",
    timeout: RUNNER_TIMEOUT_MS,
    maxBuffer: 10 * 1024 * 1024,
    env: process.env,
  })

  const timedOut = Boolean(
    result.error &&
      (result.error.code === "ETIMEDOUT" ||
        result.signal === "SIGTERM" ||
        result.signal === "SIGKILL"),
  )
  const exitCode = timedOut
    ? null
    : typeof result.status === "number"
      ? result.status
      : 1
  const success = exitCode === 0
  const verdict = success ? "AUTO CHECK PASS" : "AUTO CHECK FAIL"

  const text = [
    verdict,
    "runner: ./scripts/check.sh",
    `exit code: ${exitCode === null ? `timeout after ${RUNNER_TIMEOUT_MS}ms` : exitCode}`,
    `duration: ${Date.now() - startedAt}ms`,
    "",
    "----- stdout -----",
    tail(result.stdout),
    "----- stderr -----",
    tail(result.stderr),
  ].join("\n")

  return { success, text }
}

// Attach the check output to the tool result so the model can see it.
// `marker` is one of "pass" | "fail" | "skipped" | "error".
function attachResult(event, text, marker) {
  if (event.result && typeof event.result === "object" && !Array.isArray(event.result)) {
    const next = { ...event.result }
    const metadata =
      next.metadata && typeof next.metadata === "object" && !Array.isArray(next.metadata)
        ? { ...next.metadata }
        : {}
    metadata.autoCheck = marker
    next.metadata = metadata

    if (typeof next.output === "string") next.output = `${next.output}\n\n${text}`
    else if (next.output === undefined) next.output = text

    if (Array.isArray(next.content)) next.content = [...next.content, { type: "text", text }]

    event.result = next
    return
  }

  if (typeof event.result === "string") {
    event.result = `${event.result}\n\n${text}`
    return
  }

  event.result = text
}

async function onToolExecuted(event) {
  // Only react to successful runs of editing tools.
  if (!event || event.status !== "completed") return
  if (!isEditTool(event.tool ?? event.name ?? event.toolName)) return

  const input = event.input ?? event.args ?? event.arguments ?? {}
  const pythonFiles = changedPythonFiles(input)
  if (pythonFiles.length === 0) return

  const changed = pythonFiles.map((p) => relative(PROJECT_DIR, p)).join(", ")

  if (checkInProgress) {
    attachResult(
      event,
      `AUTO CHECK SKIP — a check is already running (recursion guard).\nchanged: ${changed}`,
      "skipped",
    )
    return
  }

  checkInProgress = true
  try {
    const outcome = runRunner()
    attachResult(
      event,
      `Python files changed: ${changed}\n\n${outcome.text}`,
      outcome.success ? "pass" : "fail",
    )
  } finally {
    checkInProgress = false
  }
}

export default {
  id: "check-after-edit",
  async setup(ctx) {
    console.error(`[check-after-edit] loaded (runner=${RUNNER})`)
    await ctx.tool.hook("execute.after", async (event) => {
      // Never let a check failure break the agent's tool call; report it instead.
      try {
        await onToolExecuted(event)
      } catch (error) {
        const message = error && error.message ? error.message : String(error)
        try {
          attachResult(event, `AUTO CHECK ERROR — ${message}`, "error")
        } catch {
          console.error(`[check-after-edit] failed: ${message}`)
        }
      }
    })
  },
}
