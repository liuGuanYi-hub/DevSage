[CmdletBinding()]
param(
    [ValidateRange(0, 3600)]
    [int]$DurationSeconds = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $projectRoot "frontend"
$viteEntry = Join-Path $frontendRoot "node_modules\vite\bin\vite.js"
$backendPort = 8000
$frontendPort = 5173
$backendProcess = $null
$frontendProcess = $null
$previousStorage = $env:DEVSAGE_STORAGE

function Assert-PortAvailable {
    param([Parameter(Mandatory = $true)][int]$Port)

    $listeners = @(
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    )
    if ($listeners.Count -gt 0) {
        throw "Port $Port is already in use; refusing to take over another service"
    }
}

function Stop-DemoProcess {
    param([System.Diagnostics.Process]$Process)

    if ($null -eq $Process) {
        return
    }
    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {
        # The process may have exited already; continue cleaning up other resources.
    }
}

try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "python command was not found"
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw "node command was not found"
    }
    if (-not (Test-Path -LiteralPath $viteEntry -PathType Leaf)) {
        throw "Frontend dependencies are missing: $viteEntry; install frontend dependencies first"
    }

    Assert-PortAvailable -Port $backendPort
    Assert-PortAvailable -Port $frontendPort

    $env:DEVSAGE_STORAGE = "memory"
    $backendProcess = Start-Process `
        -FilePath "python" `
        -ArgumentList @(
            "-m", "uvicorn", "app.main:app", "--app-dir", "backend",
            "--host", "127.0.0.1", "--port", "$backendPort"
        ) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -PassThru

    $frontendProcess = Start-Process `
        -FilePath "node" `
        -ArgumentList @(
            ('"' + $viteEntry + '"'),
            "--host", "127.0.0.1", "--port", "$frontendPort"
        ) `
        -WorkingDirectory $frontendRoot `
        -WindowStyle Hidden `
        -PassThru

    $backendReady = $false
    $frontendReady = $false
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health" -TimeoutSec 2
            $backendReady = $health.status -eq "ok"
        } catch {
            $backendReady = $false
        }
        try {
            $page = Invoke-WebRequest -Uri "http://127.0.0.1:$frontendPort" -TimeoutSec 2
            $frontendReady = $page.StatusCode -eq 200
        } catch {
            $frontendReady = $false
        }
        if ($backendReady -and $frontendReady) {
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not ($backendReady -and $frontendReady)) {
        throw "Local demo services did not become ready in time"
    }
    if ($null -eq $page -or $page.Content -notmatch 'id="app"') {
        throw "Frontend page did not expose the expected Vue app mount point"
    }

    Write-Output "DevSage demo running: http://127.0.0.1:$frontendPort"
    Write-Output "Backend health: http://127.0.0.1:$backendPort/health"
    Write-Output "Storage: memory (no Docker, no database volume)"

    if ($DurationSeconds -gt 0) {
        Start-Sleep -Seconds $DurationSeconds
        return
    }

    Write-Output "Press Ctrl+C to stop the demo and clean up only its two processes."
    while ($true) {
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
            throw "A local demo process exited unexpectedly"
        }
        Start-Sleep -Seconds 1
    }
} finally {
    Stop-DemoProcess -Process $frontendProcess
    Stop-DemoProcess -Process $backendProcess
    if ($null -eq $previousStorage) {
        Remove-Item Env:DEVSAGE_STORAGE -ErrorAction SilentlyContinue
    } else {
        $env:DEVSAGE_STORAGE = $previousStorage
    }
}
