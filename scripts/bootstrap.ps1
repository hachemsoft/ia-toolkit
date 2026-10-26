# Compatible with Windows PowerShell 5.1 and PowerShell 7.
$ErrorActionPreference = 'Stop'
$kitRoot = Split-Path -Parent $PSScriptRoot
$kitArguments = @($args)
if ($kitArguments.Count -eq 0) { $kitArguments = @('setup') }
# update: first fetch the new version when the kit folder is a git clone without local changes; never blocks the update.
if ($kitArguments[0] -eq 'update' -and (Test-Path (Join-Path $kitRoot '.git')) -and (Get-Command git -ErrorAction SilentlyContinue)) {
    & git -C $kitRoot diff --quiet; $unstaged = $LASTEXITCODE
    & git -C $kitRoot diff --cached --quiet; $staged = $LASTEXITCODE
    if ($unstaged -eq 0 -and $staged -eq 0) {
        & git -C $kitRoot pull --ff-only --quiet
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Could not fetch the new version (network or diverging history): updating from the current folder.' }
    } else {
        Write-Warning 'Local changes in the kit folder: no git pull; updating from the current folder.'
    }
}
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
