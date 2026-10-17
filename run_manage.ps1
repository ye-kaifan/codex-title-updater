# Native Windows entry point. A full Python path (without quotes/arguments) may
# be supplied in CODEX_TITLE_UPDATER_PYTHON, including Codex's bundled Python.
$ErrorActionPreference = 'Stop'
$taskPython = $env:CODEX_TITLE_UPDATER_PYTHON
if (-not $taskPython) { $taskPython = 'python' }
& $taskPython -X utf8 (Join-Path $PSScriptRoot 'manage.py') @args
exit $LASTEXITCODE
