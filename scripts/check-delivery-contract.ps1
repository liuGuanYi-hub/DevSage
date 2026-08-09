[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$requiredFiles = @(
    "README.md",
    "backend/app/main.py",
    "backend/app/ingestion/indexer.py",
    "backend/app/retrieval/hybrid_search.py",
    "backend/app/agents/runner.py",
    "backend/app/mcp/server.py",
    "frontend/src/App.vue",
    "scripts/start-demo.ps1",
    "scripts/smoke-http.ps1",
    "scripts/smoke-actors.ps1",
    "scripts/verify-offline.ps1",
    "evaluation/datasets/devmind_mvp_questions.json",
    "evaluation/scripts/generate_offline_report.py",
    "evaluation/reports/offline-baseline.json",
    "evaluation/reports/offline-baseline.md",
    "docker-compose.yml"
)

$missingFiles = @(
    $requiredFiles | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $projectRoot $_) -PathType Leaf)
    }
)
if ($missingFiles.Count -gt 0) {
    throw ("delivery contract missing files: {0}" -f ($missingFiles -join ", "))
}
$demoDocuments = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot "docs") -Filter "DevSage*.md" -File)
if ($demoDocuments.Count -eq 0) {
    throw "delivery contract found no DevSage Markdown demonstration document"
}

$datasetPath = Join-Path $projectRoot "evaluation/datasets/devmind_mvp_questions.json"
$reportPath = Join-Path $projectRoot "evaluation/reports/offline-baseline.json"
$dataset = Get-Content -LiteralPath $datasetPath -Raw -Encoding UTF8 | ConvertFrom-Json
$datasetCount = @($dataset).Count
$report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json

if ($datasetCount -ne 50) {
    throw ("delivery contract expected 50 evaluation questions, found {0}" -f $datasetCount)
}
if ([int]$report.schema_version -ne 1) {
    throw "delivery contract report schema_version must be 1"
}
if ([int]$report.dataset.questions -ne $datasetCount) {
    throw "delivery contract report question count does not match dataset"
}
$datasetHash = (Get-FileHash -LiteralPath $datasetPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ([string]$report.dataset.sha256 -ne $datasetHash) {
    throw "delivery contract report dataset hash does not match the current dataset"
}

$requiredMetricNames = @(
    "agent_grounding",
    "tool_call_accuracy",
    "context_quality",
    "retrieval_strategies"
)
foreach ($metricName in $requiredMetricNames) {
    if ($null -eq $report.metrics.$metricName) {
        throw ("delivery contract report is missing metric: {0}" -f $metricName)
    }
}

Write-Output ("Delivery contract passed: required_files={0}, dataset_questions={1}, report_schema={2}" -f `
    $requiredFiles.Count, $datasetCount, $report.schema_version)
exit 0
