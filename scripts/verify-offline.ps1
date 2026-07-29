[CmdletBinding()]
param(
    [switch]$SkipFrontend
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Write-Output "== $Name =="
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

$python = (Get-Command python -ErrorAction Stop).Source
$powershell = (Get-Command powershell -ErrorAction Stop).Source
$stepCount = 0

Invoke-CheckedCommand "dataset validation" $python @("evaluation/scripts/validate_mvp_dataset.py")
$stepCount++
Invoke-CheckedCommand "agent grounding evaluation" $python @("evaluation/scripts/evaluate_agent_grounding.py")
$stepCount++
Invoke-CheckedCommand "tool accuracy evaluation" $python @("evaluation/scripts/evaluate_tool_call_accuracy.py")
$stepCount++
Invoke-CheckedCommand "context quality evaluation" $python @("evaluation/scripts/evaluate_context_quality.py")
$stepCount++
Invoke-CheckedCommand "retrieval strategy evaluation" $python @("evaluation/scripts/evaluate_retrieval_strategies.py")
$stepCount++
Invoke-CheckedCommand "backend tests" $python @("-m", "unittest", "discover", "-s", "backend/tests", "-p", "test_*.py")
$stepCount++
Invoke-CheckedCommand "evaluation tests" $python @("-m", "unittest", "discover", "-s", "evaluation/tests", "-p", "test_*.py")
$stepCount++
Invoke-CheckedCommand "Python compilation" $python @("-m", "compileall", "-q", "backend", "evaluation/scripts")
$stepCount++
Invoke-CheckedCommand "MCP smoke" $python @("evaluation/scripts/smoke_mcp.py")
$stepCount++
Invoke-CheckedCommand "optional LangGraph smoke" $python @("evaluation/scripts/smoke_langgraph.py")
$stepCount++

$localLangGraphPython = Join-Path $projectRoot "backend\.venv\Scripts\python.exe"
if (Test-Path -LiteralPath $localLangGraphPython) {
    Invoke-CheckedCommand "installed LangGraph smoke" $localLangGraphPython @("evaluation/scripts/smoke_langgraph.py")
    $stepCount++
} else {
    Write-Output "== installed LangGraph smoke: skipped (backend/.venv is unavailable) =="
}

if (-not $SkipFrontend) {
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    Invoke-CheckedCommand "frontend production build" $npm @("run", "build", "--prefix", "frontend")
    $stepCount++
}

Invoke-CheckedCommand "local HTTP smoke" $powershell @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $projectRoot "scripts\smoke-http.ps1")
)
$stepCount++
Invoke-CheckedCommand "Docker Compose dry-run" $powershell @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $projectRoot "scripts\smoke-docker.ps1")
)
$stepCount++

Write-Output "Offline verification passed: steps=$stepCount, Docker execute was not requested."
