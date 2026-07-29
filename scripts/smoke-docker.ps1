[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$KeepResources
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

function Invoke-Compose {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose command failed with exit code $LASTEXITCODE"
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker command was not found"
}

function Assert-DockerDaemon {
    $daemonAvailable = $false
    try {
        & docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
        $daemonAvailable = $LASTEXITCODE -eq 0
    } catch {
        $daemonAvailable = $false
    }
    if (-not $daemonAvailable) {
        throw "Docker daemon is unavailable; start Docker and rerun only after approving storage usage"
    }
}

$backendPort = if ([string]::IsNullOrWhiteSpace($env:BACKEND_PORT)) { "8000" } else { $env:BACKEND_PORT }

if (-not $Execute) {
    # Dry-run uses a clearly non-production placeholder only for Compose validation.
    $env:POSTGRES_PASSWORD = "devsage-smoke-only"
    $env:DATABASE_URL = "postgresql://devsage:devsage-smoke-only@db:5432/devsage"
    Invoke-Compose @("config", "--quiet")
    Write-Output "Compose configuration is valid. No image, container, volume, or database was created."
    Write-Output "Run with -Execute only after approving Docker storage usage."
    exit 0
}

Assert-DockerDaemon

if ([string]::IsNullOrWhiteSpace($env:POSTGRES_PASSWORD) -or [string]::IsNullOrWhiteSpace($env:DATABASE_URL)) {
    throw "-Execute requires POSTGRES_PASSWORD and DATABASE_URL in the current environment"
}

$existingResources = (& docker compose ps -q 2>$null | Where-Object { $_ -and $_.Trim() })
if ($existingResources) {
    throw "existing DevSage Compose resources were detected; inspect them before running smoke"
}

$started = $false
try {
    Invoke-Compose @("up", "-d", "--build")
    $started = $true

    $health = $null
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health" -TimeoutSec 5
            if ($health.status -eq "ok") {
                break
            }
        } catch {
            if ($attempt -eq 30) {
                throw
            }
        }
        Start-Sleep -Seconds 2
    }
    if ($null -eq $health -or $health.status -ne "ok") {
        throw "backend health check did not return status=ok"
    }

    $projects = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$backendPort/api/projects" `
        -Method Get
    $sampleProject = @($projects.items | Where-Object { $_.project_id -eq "sample-data" })
    if ($projects.total -le 0 -or $sampleProject.Count -ne 1) {
        throw "project discovery smoke did not return sample-data"
    }

    $indexBody = @{ project_id = "sample-data" } | ConvertTo-Json
    $index = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$backendPort/api/index" `
        -Method Post `
        -ContentType "application/json" `
        -Body $indexBody
    if ($index.chunk_count -le 0) {
        throw "index smoke returned no chunks"
    }

    $agentBody = @{
        query = "Spring Boot server.port"
        project_id = "sample-data"
        top_k = 5
        persist = $false
    } | ConvertTo-Json
    $agent = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$backendPort/api/agent/run" `
        -Method Post `
        -ContentType "application/json" `
        -Body $agentBody
    if ([string]::IsNullOrWhiteSpace($agent.answer) -or $agent.evidence.Count -le 0) {
        throw "Agent smoke returned no answer or evidence"
    }

    Write-Output ("Docker smoke passed: health=ok, documents={0}, chunks={1}, agent_status={2}, evidence={3}" -f `
        $index.document_count, $index.chunk_count, $agent.status, $agent.evidence.Count)
} finally {
    if ($started -and -not $KeepResources) {
        Invoke-Compose @("down")
        Write-Output "Compose services stopped; named volumes were preserved."
    } elseif ($started) {
        Write-Output "Compose services remain running because -KeepResources was supplied."
    }
}
