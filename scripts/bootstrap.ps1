# Compatible with Windows PowerShell 5.1 and PowerShell 7.
$ErrorActionPreference = 'Stop'
$kitRoot = Split-Path -Parent $PSScriptRoot
$kitArguments = @($args)
if ($kitArguments.Count -eq 0) { $kitArguments = @('setup') }
# The current folder stays the user's: a relative path (--json, --home) resolves there, not in the kit.
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ($previousPythonPath) { "$kitRoot;$previousPythonPath" } else { $kitRoot }
try {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m installer @kitArguments
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m installer @kitArguments
    } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        & python3 -m installer @kitArguments
    } else {
        throw 'Python not found. Ask IT support to make Python available in the terminal.'
    }
    $kitExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
exit $kitExitCode
