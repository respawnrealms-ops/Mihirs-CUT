# Run this file yourself to reload the local app after a code update.
# It checks for recording, rendering and uploading before stopping this app only.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($PSScriptRoot)
$base = 'http://127.0.0.1:8765'
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $jobs = Invoke-RestMethod "$base/api/jobs" -TimeoutSec 10
    $overview = Invoke-RestMethod "$base/api/overview" -TimeoutSec 10
    $busy = @($jobs | Where-Object { $_.status -notin @('done','error','cancelled','canceled','stopped') }).Count
    $busy += @($jobs | ForEach-Object { $_.clips } | Where-Object { $_.status -in @('queued','rendering') }).Count
    $busy += @($overview.posts | Where-Object { $_.state -in @('uploading','preparing','posting') -or $_.status -in @('uploading','preparing','posting') }).Count
    if ($busy) { throw 'Mihis Cut is recording, processing or uploading. Wait until it finishes, then run this again.' }
    $server = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    $allowed = @((Join-Path $root '.runtime\python\python.exe'), (Join-Path $root '.venv\Scripts\python.exe'))
    if ($server.ExecutablePath -notin $allowed -or $server.CommandLine -notlike '*studio.server*') {
        throw 'Another program owns this port. It was left running.'
    }
    Stop-Process -Id $server.ProcessId
    Wait-Process -Id $server.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
}
$python = Join-Path $root '.venv\Scripts\python.exe'
$app = Start-Process -FilePath $python -ArgumentList '-m','studio.server' -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $root 'data\server.stdout.log') `
    -RedirectStandardError (Join-Path $root 'data\server.stderr.log') -PassThru
$app.Id | Set-Content -LiteralPath (Join-Path $root 'data\server.pid')
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    try {
        $null = Invoke-RestMethod "$base/healthz" -TimeoutSec 2
        Write-Host "Mihis Cut restarted. Refresh $base/app"
        exit 0
    } catch { Start-Sleep -Seconds 1 }
}
throw 'The app did not answer yet. Check data\server.stderr.log.'
