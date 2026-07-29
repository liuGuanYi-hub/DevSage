[CmdletBinding()]
param(
    [int]$Port = 18000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$smokeTarget = Join-Path $projectRoot "data\approved-notes\projects\sample-data\HttpSmoke\contract-note.md"
if (Test-Path -LiteralPath $smokeTarget) {
    throw "Smoke target already exists; refusing to overwrite user data: $smokeTarget"
}

$previousStorage = $env:DEVSAGE_STORAGE
$env:DEVSAGE_STORAGE = "memory"
$server = $null

try {
    $server = Start-Process `
        -FilePath "python" `
        -ArgumentList @(
            "-m", "uvicorn", "app.main:app", "--app-dir", "backend",
            "--host", "127.0.0.1", "--port", "$Port"
        ) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -PassThru

    $health = $null
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
            if ($health.status -eq "ok") {
                break
            }
        } catch {
            if ($attempt -eq 30) {
                throw
            }
            Start-Sleep -Milliseconds 500
        }
    }
    if ($null -eq $health -or $health.status -ne "ok") {
        throw "HTTP health smoke failed"
    }

    $projects = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/projects" -Method Get
    $sampleProject = @($projects.items | Where-Object { $_.project_id -eq "sample-data" })
    if ($projects.total -le 0 -or $sampleProject.Count -ne 1) {
        throw "HTTP project discovery smoke failed"
    }

    $index = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$Port/api/index" `
        -Method Post `
        -ContentType "application/json" `
        -Body (@{ project_id = "sample-data" } | ConvertTo-Json)
    if ($index.chunk_count -le 0) {
        throw "HTTP index smoke returned no chunks"
    }

    $agent = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$Port/api/agent/run" `
        -Method Post `
        -ContentType "application/json" `
        -Body (@{
            project_id = "sample-data"
            query = "server.port"
            top_k = 5
            persist = $false
        } | ConvertTo-Json)
    if ([string]::IsNullOrWhiteSpace($agent.answer) -or @($agent.evidence).Count -le 0) {
        throw "HTTP Agent smoke returned no answer or evidence"
    }

    $codeTarget = Join-Path $projectRoot "sample-data\repositories\springboot-demo\README.md"
    $originalCode = Get-Content -LiteralPath $codeTarget -Raw -Encoding utf8
    $codePreview = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$Port/api/code-changes/preview" `
        -Method Post `
        -ContentType "application/json" `
        -Body (@{
            project_id = "sample-data"
            target_path = "repositories/springboot-demo/README.md"
            proposed_content = $originalCode + "`nHTTP smoke preview only`n"
            source_citations = @("sample-data/repositories/springboot-demo/README.md:1-4")
        } | ConvertTo-Json)
    if ($codePreview.status -ne "pending" -or (Get-Content -LiteralPath $codeTarget -Raw -Encoding utf8) -ne $originalCode) {
        throw "HTTP code change preview smoke failed or wrote before approval"
    }

    $preview = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$Port/api/knowledge-notes/preview" `
        -Method Post `
        -ContentType "application/json" `
        -Body (@{
            project_id = "sample-data"
            title = "HTTP smoke note"
            content = "# HTTP smoke note"
            target_path = "HttpSmoke/contract-note.md"
            source_citations = @("sample-data/docs/springboot-errors.md:1-2")
        } | ConvertTo-Json)
    if ($preview.status -ne "pending" -or $preview.target_path -ne "projects/sample-data/HttpSmoke/contract-note.md") {
        throw "HTTP knowledge preview smoke failed"
    }

    $approved = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$Port/api/knowledge-notes/$($preview.preview_id)/approve" `
        -Method Post
    if ($approved.status -ne "approved" -or -not (Test-Path -LiteralPath $smokeTarget)) {
        throw "HTTP knowledge approval smoke failed"
    }

    Write-Output (
        "HTTP smoke passed: projects={0}, documents={1}, chunks={2}, agent_status={3}, code_preview={4}, preview={5}, approval={6}" -f `
            $projects.total, $index.document_count, $index.chunk_count,
            $agent.status, $codePreview.status, $preview.status, $approved.status
    )
} finally {
    if (Test-Path -LiteralPath $smokeTarget) {
        Remove-Item -LiteralPath $smokeTarget -Force
    }
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
    if ($null -eq $previousStorage) {
        Remove-Item Env:DEVSAGE_STORAGE -ErrorAction SilentlyContinue
    } else {
        $env:DEVSAGE_STORAGE = $previousStorage
    }
}
