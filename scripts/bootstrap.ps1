# Compatible Windows PowerShell 5.1 et PowerShell 7.
$ErrorActionPreference = 'Stop'
$kitRoot = Split-Path -Parent $PSScriptRoot
$kitArguments = @($args)
if ($kitArguments.Count -eq 0) { $kitArguments = @('setup') }
# Le dossier courant reste celui de l'utilisateur : un chemin relatif (--json, --home) se résout chez lui, pas dans le kit.
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
        throw 'Python introuvable. Demander au support IT de rendre Python accessible dans le terminal.'
    }
    $kitExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
exit $kitExitCode
