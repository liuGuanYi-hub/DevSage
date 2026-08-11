[CmdletBinding()]
param(
    [string]$ModelPath = "data/manual-models/multilingual-e5-large-qint8",
    [string]$CachePath = "data/models",
    [string]$ProjectId = "sample-data",
    [int]$TopK = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

if ([string]::IsNullOrWhiteSpace($env:DATABASE_URL)) {
    throw "DATABASE_URL must be configured in the current PowerShell session; the value is never printed"
}

$resolvedModelPath = (Resolve-Path $ModelPath -ErrorAction Stop).Path
$python = Join-Path $projectRoot "backend/.venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "backend/.venv is missing; install the optional local embedding requirements first"
}

$env:DEVSAGE_STORAGE = "postgres"
$env:EMBEDDING_PROVIDER = "local"
$env:LOCAL_EMBEDDING_MODEL = $resolvedModelPath
$env:LOCAL_EMBEDDING_CACHE = (Resolve-Path $CachePath -ErrorAction Stop).Path
$env:LOCAL_EMBEDDING_BACKEND = "onnx"
$env:LOCAL_EMBEDDING_FILE_NAME = "model_qint8_avx512_vnni.onnx"
$env:DEVSAGE_SMOKE_PROJECT_ID = $ProjectId
$env:DEVSAGE_SMOKE_TOP_K = [string]([Math]::Max(1, [Math]::Min(20, $TopK)))

$script = @'
import os

from backend.app.services.index_service import IndexService

service = IndexService()
provider = service.embedding_provider
project_id = os.environ["DEVSAGE_SMOKE_PROJECT_ID"]
top_k = int(os.environ["DEVSAGE_SMOKE_TOP_K"])
project_name, snapshot = service.build(project_id)
_, results = service.search_hybrid(project_id, "8080 端口被占用 应该怎么排查", top_k=top_k)

if provider.dimension != 1024:
    raise RuntimeError(f"expected a 1024-dimensional local model, got {provider.dimension}")
if not snapshot.chunks:
    raise RuntimeError("PostgreSQL local embedding smoke indexed no chunks")
if not results:
    raise RuntimeError("PostgreSQL local embedding smoke returned no results")
print(
    "PostgreSQL local embedding smoke passed: "
    f"project={project_name}, dimension={provider.dimension}, "
    f"documents={len(snapshot.documents)}, chunks={len(snapshot.chunks)}, "
    f"results={len(results)}"
)
'@

& $python -c $script
if ($LASTEXITCODE -ne 0) {
    throw "local embedding PostgreSQL smoke failed with exit code $LASTEXITCODE"
}
