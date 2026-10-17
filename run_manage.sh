#!/bin/bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
task_python="${CODEX_TITLE_UPDATER_PYTHON:-python3}"
exec "$task_python" -X utf8 "$task_root/manage.py" "$@"
