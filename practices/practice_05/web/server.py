#!/usr/bin/env python3
"""Local-only HTTP adapter for the C++ ICPC Mini Judge."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(__file__).resolve().parent / "static"
MAX_REQUEST_BYTES = 256 * 1024
PROBLEM_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
TEST_RESULT_PATTERN = re.compile(
    r"^Test (.+): (AC|WA|CE|RE|TLE) \(([0-9]+) ms\)$"
)
VERDICTS = {"AC", "WA", "CE", "RE", "TLE"}


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class AppConfig:
    judge_binary: Path
    problems_root: Path
    static_root: Path = STATIC_ROOT
    submissions: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(2)
    )

    def validate(self) -> None:
        self.judge_binary = self.judge_binary.resolve()
        self.problems_root = self.problems_root.resolve()
        self.static_root = self.static_root.resolve()
        if not self.judge_binary.is_file() or not os.access(self.judge_binary, os.X_OK):
            raise RuntimeError(
                f"judge binary is unavailable: {self.judge_binary}; build the C++ project first"
            )
        if not self.problems_root.is_dir():
            raise RuntimeError(f"problems directory is unavailable: {self.problems_root}")
        if not self.static_root.is_dir():
            raise RuntimeError(f"static directory is unavailable: {self.static_root}")


def is_valid_problem_id(problem_id: str) -> bool:
    return PROBLEM_ID_PATTERN.fullmatch(problem_id) is not None


def run_judge(
    config: AppConfig, arguments: list[str], timeout: float = 30.0
) -> subprocess.CompletedProcess[str]:
    command = [
        str(config.judge_binary),
        "--problems-root",
        str(config.problems_root),
        *arguments,
    ]
    environment = os.environ.copy()
    environment["LC_ALL"] = "C.UTF-8"
    try:
        return subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ApiError(HTTPStatus.GATEWAY_TIMEOUT, "Judge process timed out") from error
    except OSError as error:
        raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "Cannot start judge process") from error


def list_problems(config: AppConfig) -> list[dict[str, Any]]:
    result = run_judge(config, ["list"], timeout=5.0)
    if result.returncode != 0:
        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, result.stderr.strip() or "Judge failed")

    problems: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not is_valid_problem_id(parts[0]):
            raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "Judge returned an invalid problem list")
        limit_match = re.fullmatch(r"([0-9]+) ms", parts[2])
        if limit_match is None:
            raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "Judge returned an invalid time limit")
        problems.append(
            {
                "id": parts[0],
                "title": parts[1],
                "time_limit_ms": int(limit_match.group(1)),
            }
        )
    return problems


def get_problem(config: AppConfig, problem_id: str) -> dict[str, Any]:
    if not is_valid_problem_id(problem_id):
        raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid problem id")
    result = run_judge(config, ["show", problem_id], timeout=5.0)
    if result.returncode != 0:
        if "unknown problem" in result.stderr.lower():
            raise ApiError(HTTPStatus.NOT_FOUND, "Problem not found")
        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, result.stderr.strip() or "Judge failed")

    header, separator, statement = result.stdout.partition("\n\n")
    header_lines = header.splitlines()
    if not separator or len(header_lines) != 2 or " — " not in header_lines[0]:
        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "Judge returned an invalid statement")
    returned_id, title = header_lines[0].split(" — ", 1)
    limit_match = re.fullmatch(r"Time limit: ([0-9]+) ms", header_lines[1])
    if returned_id != problem_id or limit_match is None:
        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "Judge returned invalid problem metadata")
    return {
        "id": returned_id,
        "title": title,
        "time_limit_ms": int(limit_match.group(1)),
        "statement": statement,
    }


def parse_submission_output(output: str) -> dict[str, Any]:
    tests: list[dict[str, Any]] = []
    diagnostic_lines: list[str] = []
    verdict: str | None = None
    results_started = False

    for line in output.splitlines():
        test_match = TEST_RESULT_PATTERN.fullmatch(line)
        if test_match:
            results_started = True
            tests.append(
                {
                    "name": test_match.group(1),
                    "verdict": test_match.group(2),
                    "elapsed_ms": int(test_match.group(3)),
                }
            )
            continue
        if line.startswith("Verdict: "):
            candidate = line.removeprefix("Verdict: ")
            if candidate in VERDICTS:
                verdict = candidate
                results_started = True
                continue
        if not results_started:
            diagnostic_lines.append(line)

    if verdict is None:
        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "Judge returned no verdict")
    return {
        "verdict": verdict,
        "tests": tests,
        "compiler_output": "\n".join(diagnostic_lines).strip(),
        "raw_output": output.rstrip(),
    }


def submit_code(config: AppConfig, problem_id: str, code: str) -> dict[str, Any]:
    if not is_valid_problem_id(problem_id):
        raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid problem id")
    if not code.strip():
        raise ApiError(HTTPStatus.BAD_REQUEST, "C++ source code is empty")
    if len(code.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Source code is too large")

    known_ids = {problem["id"] for problem in list_problems(config)}
    if problem_id not in known_ids:
        raise ApiError(HTTPStatus.NOT_FOUND, "Problem not found")
    if not config.submissions.acquire(timeout=0.25):
        raise ApiError(HTTPStatus.TOO_MANY_REQUESTS, "Judge is busy; try again shortly")
    try:
        with tempfile.TemporaryDirectory(prefix="icpc-mini-judge-web-") as directory:
            solution_path = Path(directory) / "solution.cpp"
            solution_path.write_text(code, encoding="utf-8")
            result = run_judge(
                config,
                ["submit", problem_id, str(solution_path)],
                timeout=30.0,
            )
            if result.returncode != 0:
                raise ApiError(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    result.stderr.strip() or "Judge failed to evaluate the submission",
                )
            return parse_submission_output(result.stdout)
    finally:
        config.submissions.release()


def make_handler(config: AppConfig) -> type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        server_version = "ICPCMiniJudge/0.1"
        sys_version = ""

        def log_message(self, message: str, *arguments: object) -> None:
            print(f"[{self.log_date_time_string()}] {message % arguments}")

        def send_common_headers(self, content_type: str, length: int) -> None:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")

        def send_json(self, status: int, payload: dict[str, Any] | list[Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_common_headers("application/json; charset=utf-8", len(body))
            self.end_headers()
            self.wfile.write(body)

        def send_error_json(self, error: ApiError) -> None:
            self.send_json(error.status, {"error": error.message})

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            try:
                path = urlsplit(self.path).path
                if path == "/api/problems":
                    self.send_json(HTTPStatus.OK, {"problems": list_problems(config)})
                    return
                if path.startswith("/api/problems/"):
                    problem_id = unquote(path.removeprefix("/api/problems/"))
                    self.send_json(HTTPStatus.OK, get_problem(config, problem_id))
                    return
                static_files = {
                    "/": ("index.html", "text/html; charset=utf-8"),
                    "/index.html": ("index.html", "text/html; charset=utf-8"),
                    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                }
                if path not in static_files:
                    raise ApiError(HTTPStatus.NOT_FOUND, "Not found")
                file_name, content_type = static_files[path]
                body = (config.static_root / file_name).read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_common_headers(content_type, len(body))
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "img-src 'self'; connect-src 'self'; base-uri 'none'; "
                    "form-action 'none'; frame-ancestors 'none'",
                )
                self.end_headers()
                self.wfile.write(body)
            except ApiError as error:
                self.send_error_json(error)
            except OSError:
                self.send_error_json(ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "Cannot read resource"))

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            try:
                path = urlsplit(self.path).path
                if path != "/api/submit":
                    raise ApiError(HTTPStatus.NOT_FOUND, "Not found")
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
                if content_type != "application/json":
                    raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Expected application/json")
                raw_length = self.headers.get("Content-Length")
                if raw_length is None:
                    raise ApiError(HTTPStatus.LENGTH_REQUIRED, "Content-Length is required")
                try:
                    length = int(raw_length)
                except ValueError as error:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length") from error
                if length < 0:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length")
                if length > MAX_REQUEST_BYTES:
                    raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large")
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Incomplete request body")
                try:
                    payload = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid JSON body") from error
                if not isinstance(payload, dict):
                    raise ApiError(HTTPStatus.BAD_REQUEST, "JSON body must be an object")
                problem_id = payload.get("problem_id")
                code = payload.get("code")
                if not isinstance(problem_id, str) or not isinstance(code, str):
                    raise ApiError(HTTPStatus.BAD_REQUEST, "problem_id and code must be strings")
                self.send_json(HTTPStatus.OK, submit_code(config, problem_id, code))
            except ApiError as error:
                self.send_error_json(error)

    return RequestHandler


def create_server(config: AppConfig, port: int) -> ThreadingHTTPServer:
    config.validate()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(config))
    server.daemon_threads = True
    return server


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local ICPC Mini Judge web UI")
    parser.add_argument("--port", type=int, default=8080, help="localhost port (default: 8080)")
    parser.add_argument(
        "--judge",
        type=Path,
        default=PROJECT_ROOT / "build" / "icpc-judge",
        help="path to the built icpc-judge executable",
    )
    parser.add_argument(
        "--problems-root",
        type=Path,
        default=PROJECT_ROOT / "problems",
        help="path to the problems directory",
    )
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    return arguments


def main() -> None:
    arguments = parse_arguments()
    config = AppConfig(arguments.judge, arguments.problems_root)
    server = create_server(config, arguments.port)
    print(f"ICPC Mini Judge is ready at http://127.0.0.1:{server.server_port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
