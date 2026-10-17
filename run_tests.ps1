$ErrorActionPreference = 'Stop'
$taskPython = $env:CODEX_TITLE_UPDATER_PYTHON
if (-not $taskPython) { $taskPython = 'python' }
Push-Location $PSScriptRoot
try {
    & $taskPython -X utf8 -m unittest discover -s tests -v
    $taskExitCode = $LASTEXITCODE
} finally { Pop-Location }
exit $taskExitCode
