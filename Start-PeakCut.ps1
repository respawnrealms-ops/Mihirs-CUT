$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -m studio.server
    $peakcutExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $peakcutExitCode
