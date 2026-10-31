#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = PROJECT_ROOT / "web" / "server.py"
SPEC = importlib.util.spec_from_file_location("icpc_web_server", SERVER_PATH)
assert SPEC is not None and SPEC.loader is not None
SERVER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SERVER
SPEC.loader.exec_module(SERVER)


CORRECT_SOLUTION = r"""
#include <iostream>
int main() {
    long long a, b;
    std::cin >> a >> b;
    std::cout << a + b << '\n';
}
"""

WRONG_SOLUTION = r"""
#include <iostream>
int main() {
    long long a, b;
    std::cin >> a >> b;
    std::cout << a - b << '\n';
}
"""


class WebBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        judge = Path(os.environ.get("ICPC_JUDGE_BINARY", PROJECT_ROOT / "build" / "icpc-judge"))
        cls.config = SERVER.AppConfig(judge, PROJECT_ROOT / "problems")
        cls.config.validate()

    def test_problem_list_and_statement(self) -> None:
        problems = SERVER.list_problems(self.config)
        self.assertEqual(
            [problem["id"] for problem in problems],
            ["a-plus-b", "binary-search", "prefix-sums"],
        )

        problem = SERVER.get_problem(self.config, "a-plus-b")
        self.assertEqual(problem["title"], "A + B")
        self.assertEqual(problem["time_limit_ms"], 1000)
        self.assertIn("Даны два целых числа", problem["statement"])

    def test_correct_submission(self) -> None:
        result = SERVER.submit_code(self.config, "a-plus-b", CORRECT_SOLUTION)
        self.assertEqual(result["verdict"], "AC")
        self.assertEqual([test["verdict"] for test in result["tests"]], ["AC", "AC", "AC"])

    def test_wrong_submission(self) -> None:
        result = SERVER.submit_code(self.config, "a-plus-b", WRONG_SOLUTION)
        self.assertEqual(result["verdict"], "WA")
        self.assertEqual(len(result["tests"]), 1)

    def test_rejects_invalid_problem_id(self) -> None:
        self.assertFalse(SERVER.is_valid_problem_id("../secret"))
        with self.assertRaises(SERVER.ApiError) as context:
            SERVER.get_problem(self.config, "../secret")
        self.assertEqual(context.exception.status, 400)

    def test_rejects_oversized_source(self) -> None:
        oversized = "x" * (SERVER.MAX_REQUEST_BYTES + 1)
        with self.assertRaises(SERVER.ApiError) as context:
            SERVER.submit_code(self.config, "a-plus-b", oversized)
        self.assertEqual(context.exception.status, 413)

    def test_submission_parser_handles_compilation_error(self) -> None:
        parsed = SERVER.parse_submission_output("main.cpp: error: expected ;\nVerdict: CE\n")
        self.assertEqual(parsed["verdict"], "CE")
        self.assertIn("expected ;", parsed["compiler_output"])

    def test_frontend_uses_safe_dynamic_output(self) -> None:
        html = (PROJECT_ROOT / "web" / "static" / "index.html").read_text(encoding="utf-8")
        javascript = (PROJECT_ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("ICPC Mini Judge", html)
        self.assertIn("textContent", javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_http_handler_is_constructible(self) -> None:
        handler = SERVER.make_handler(self.config)
        self.assertTrue(issubclass(handler, SERVER.BaseHTTPRequestHandler))


if __name__ == "__main__":
    unittest.main(verbosity=2)
