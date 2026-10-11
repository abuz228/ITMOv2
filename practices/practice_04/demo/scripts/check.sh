#!/usr/bin/env bash
# Single runner for Practice 4. Works from any current directory.
set -euo pipefail

# Directory of this script: <project>/scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Project root: <project>
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

python3 -m unittest discover -s tests -v
