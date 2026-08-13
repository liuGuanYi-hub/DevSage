[CmdletBinding()]
param(
    [ValidateRange(0, 3600)]
    [int]$DurationSeconds = 0,
    [string]$ObsidianVaultPath = ""
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
$previousObsidianVaultPath = $env:DEVSAGE_OBSIDIAN_VAULT_PATH
$loadedDotEnvVariables = @()

function Import-DotEnv {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }

    $loaded = [System.Collections.Generic.List[string]]::new()
    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
        if ($line -match '^\s*(?:export\s+)?(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?<value>.*)\s*$') {
            $name = $Matches.name
            $value = $Matches.value.Trim()
            if ($value.Length -ge 2) {
                $first = $value.Substring(0, 1)
                $last = $value.Substring($value.Length - 1, 1)
                if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
            }

            # An explicitly supplied process variable wins over the .env file.
            if ($null -eq [Environment]::GetEnvironmentVariable($name, "Process")) {
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
                $loaded.Add($name) | Out-Null
            }
        }
    }
    return $loaded.ToArray()
}

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

function Resolve-LocalVaultPath {
    param([string]$ExplicitPath, [string[]]$DotEnvVariables)

    if ($ExplicitPath.Trim()) {
        $resolved = Resolve-Path -LiteralPath $ExplicitPath -ErrorAction Stop
        if (-not (Test-Path -LiteralPath $resolved.Path -PathType Container)) {
            throw "Obsidian Vault path is not a directory: $ExplicitPath"
        }
        return $resolved.Path
    }

    $configuredPath = [Environment]::GetEnvironmentVariable("DEVSAGE_OBSIDIAN_VAULT_PATH", "Process")
    if ([string]::IsNullOrWhiteSpace($configuredPath)) {
        return ""
    }
    if (Test-Path -LiteralPath $configuredPath -PathType Container) {
        return (Resolve-Path -LiteralPath $configuredPath).Path
    }

    # Compose uses /vault inside the container; local demo uses the host path.
    $hostPath = [Environment]::GetEnvironmentVariable("DEVSAGE_OBSIDIAN_VAULT_HOST_PATH", "Process")
    if ($DotEnvVariables -contains "DEVSAGE_OBSIDIAN_VAULT_PATH" -and
        -not [string]::IsNullOrWhiteSpace($hostPath) -and
        (Test-Path -LiteralPath $hostPath -PathType Container)) {
        return (Resolve-Path -LiteralPath $hostPath).Path
    }

    throw "Configured Obsidian Vault path is not a local directory; pass -ObsidianVaultPath with a host path"
}

try {
    $loadedDotEnvVariables = @(Import-DotEnv -Path (Join-Path $projectRoot ".env"))
    $localVaultPath = Resolve-LocalVaultPath -ExplicitPath $ObsidianVaultPath -DotEnvVariables $loadedDotEnvVariables
    if ($localVaultPath) {
        $env:DEVSAGE_OBSIDIAN_VAULT_PATH = $localVaultPath
    }
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
    Start-Sleep -Milliseconds 250
    if ($backendProcess.HasExited) {
        throw "Backend process exited before health check"
    }

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
        if ($backendProcess.HasExited) {
            throw "Backend process exited before becoming healthy"
        }
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
    Write-Output ("Obsidian Vault: {0}" -f $(if ($env:DEVSAGE_OBSIDIAN_VAULT_PATH) { "external read-only enabled" } else { "not configured" }))

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
    if ($null -eq $previousObsidianVaultPath) {
        Remove-Item Env:DEVSAGE_OBSIDIAN_VAULT_PATH -ErrorAction SilentlyContinue
    } else {
        $env:DEVSAGE_OBSIDIAN_VAULT_PATH = $previousObsidianVaultPath
    }
    foreach ($name in $loadedDotEnvVariables) {
        [Environment]::SetEnvironmentVariable($name, $null, "Process")
    }
}
