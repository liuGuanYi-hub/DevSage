[CmdletBinding()]
param(
    [int]$Port = 18001
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

function Invoke-ExpectedStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][int]$ExpectedStatus,
        [hashtable]$Headers = @{},
        [string]$Body = $null
    )

    try {
        $response = Invoke-WebRequest `
            -Uri $Uri `
            -Method $Method `
            -Headers $Headers `
            -ContentType "application/json" `
            -Body $Body `
            -TimeoutSec 5
        $actualStatus = [int]$response.StatusCode
    } catch {
        if ($null -eq $_.Exception.Response) {
            throw
        }
        $actualStatus = [int]$_.Exception.Response.StatusCode
    }

    if ($actualStatus -ne $ExpectedStatus) {
        throw "Expected HTTP $ExpectedStatus from $Method $Uri, got $actualStatus"
    }
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
            if ($health.status -eq "ok") { break }
        } catch {
            if ($attempt -eq 30) { throw }
            Start-Sleep -Milliseconds 500
        }
    }
    if ($null -eq $health -or $health.status -ne "ok") {
        throw "Actor HTTP health smoke failed"
    }

    $projects = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/projects" -Method Get
    $sampleProject = @($projects.items | Where-Object { $_.project_id -eq "sample-data" })
    if ($sampleProject.Count -ne 1 -or @($sampleProject[0].members).Count -lt 3) {
        throw "Actor project metadata smoke failed"
    }

    $viewerHeaders = @{ "X-DevSage-Actor" = "local-viewer" }
    $editorHeaders = @{ "X-DevSage-Actor" = "local-editor" }
    $viewerSearchBody = @{ project_id = "sample-data"; query = "8080 端口占用" } | ConvertTo-Json
    $viewerSearch = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$Port/api/search" `
        -Method Post `
        -Headers $viewerHeaders `
        -ContentType "application/json" `
        -Body $viewerSearchBody
    if (@($viewerSearch.results).Count -le 0) {
        throw "Viewer search smoke returned no evidence"
    }

    $indexBody = @{ project_id = "sample-data" } | ConvertTo-Json
    Invoke-ExpectedStatus `
        -Uri "http://127.0.0.1:$Port/api/index" `
        -Method "Post" `
        -ExpectedStatus 403 `
        -Headers $viewerHeaders `
        -Body $indexBody

    $noteBody = @{
        project_id = "sample-data"
        title = "Actor smoke note"
        content = "# Actor smoke note"
        target_path = "ActorSmoke/contract-note.md"
    } | ConvertTo-Json
    Invoke-ExpectedStatus `
        -Uri "http://127.0.0.1:$Port/api/knowledge-notes/preview" `
        -Method "Post" `
        -ExpectedStatus 403 `
        -Headers $viewerHeaders `
        -Body $noteBody
    $editorPreview = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$Port/api/knowledge-notes/preview" `
        -Method Post `
        -Headers $editorHeaders `
        -ContentType "application/json" `
        -Body $noteBody
    if ($editorPreview.status -ne "pending") {
        throw "Editor knowledge preview smoke failed"
    }

    $codeTarget = Join-Path $projectRoot "sample-data\repositories\springboot-demo\README.md"
    $originalCode = Get-Content -LiteralPath $codeTarget -Raw -Encoding utf8
    $codeBody = @{
        project_id = "sample-data"
        target_path = "repositories/springboot-demo/README.md"
        proposed_content = $originalCode + "`nActor smoke preview only`n"
        source_citations = @("sample-data/repositories/springboot-demo/README.md:1-4")
    } | ConvertTo-Json
    Invoke-ExpectedStatus `
        -Uri "http://127.0.0.1:$Port/api/code-changes/preview" `
        -Method "Post" `
        -ExpectedStatus 403 `
        -Headers $editorHeaders `
        -Body $codeBody
    $operatorPreview = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$Port/api/code-changes/preview" `
        -Method Post `
        -ContentType "application/json" `
        -Body $codeBody
    if ($operatorPreview.status -ne "pending" -or (Get-Content -LiteralPath $codeTarget -Raw -Encoding utf8) -ne $originalCode) {
        throw "Operator code preview smoke failed or wrote before approval"
    }

    Write-Output (
        "Actor smoke passed: viewer_search={0}, viewer_index=403, viewer_note=403, editor_note={1}, editor_code=403, operator_code={2}" -f `
            @($viewerSearch.results).Count, $editorPreview.status, $operatorPreview.status
    )
} finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
    if ($null -eq $previousStorage) {
        Remove-Item Env:DEVSAGE_STORAGE -ErrorAction SilentlyContinue
    } else {
        $env:DEVSAGE_STORAGE = $previousStorage
    }
}
