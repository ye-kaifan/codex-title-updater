#!/bin/bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
task_python="${CODEX_TITLE_UPDATER_PYTHON:-python3}"
cd "$task_root"
exec "$task_python" -X utf8 -m unittest discover -s tests -v
