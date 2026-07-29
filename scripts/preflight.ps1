[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendDependencies = Test-Path -LiteralPath (Join-Path $projectRoot "frontend\node_modules") -PathType Container
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$pytestAvailable = $false
$dockerDaemonAvailable = $false

if ($null -ne $pythonCommand) {
    & $pythonCommand.Source -c "import pytest" 2>$null
    $pytestAvailable = $LASTEXITCODE -eq 0
}

if ($null -ne $dockerCommand) {
    try {
        & $dockerCommand.Source info --format '{{.ServerVersion}}' 2>$null | Out-Null
        $dockerDaemonAvailable = $LASTEXITCODE -eq 0
    } catch {
        $dockerDaemonAvailable = $false
    }
}

$cDrive = Get-PSDrive -Name C -ErrorAction SilentlyContinue
$dDrive = Get-PSDrive -Name D -ErrorAction SilentlyContinue

Write-Output "DevSage read-only preflight"
Write-Output ("project_root={0}" -f $projectRoot)
Write-Output ("python={0}" -f $(if ($null -ne $pythonCommand) { "available" } else { "missing" }))
Write-Output ("node={0}" -f $(if ($null -ne $nodeCommand) { "available" } else { "missing" }))
Write-Output ("npm={0}" -f $(if ($null -ne $npmCommand) { "available" } else { "missing" }))
Write-Output ("pytest={0}" -f $(if ($pytestAvailable) { "available" } else { "missing" }))
Write-Output ("frontend_dependencies={0}" -f $(if ($frontendDependencies) { "present" } else { "missing" }))
Write-Output ("docker_cli={0}" -f $(if ($null -ne $dockerCommand) { "available" } else { "missing" }))
Write-Output ("docker_daemon={0}" -f $(if ($dockerDaemonAvailable) { "running" } else { "unavailable" }))
if ($null -ne $cDrive) {
    Write-Output ("C_free_GB={0:N2}" -f ($cDrive.Free / 1GB))
}
if ($null -ne $dDrive) {
    Write-Output ("D_free_GB={0:N2}" -f ($dDrive.Free / 1GB))
}
Write-Output "No dependency install, Docker start, image pull, container creation, or volume creation was performed."
