# Compatibility with older instructions that ran scripts\bootstrap.ps1: hands over to Installer.cmd, which does the work.
# It runs only where the workstation's script policy already allows it: nothing here changes that policy. Where scripts
# are blocked, run Installer.cmd from a Command Prompt instead (double-click, or: Installer.cmd setup).
$installer = Join-Path (Split-Path -Parent $PSScriptRoot) 'Installer.cmd'
& $installer @args
exit $LASTEXITCODE
