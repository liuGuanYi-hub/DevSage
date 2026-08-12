[CmdletBinding()]
param(
    [string]$Url = "http://127.0.0.1:5173/",
    [string]$OutputDirectory = "output/playwright"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    throw "npx was not found; install Node.js/npm before running browser verification"
}

$session = "devsage-browser-regression"
$outputPath = Join-Path $projectRoot $OutputDirectory
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

function Invoke-PlaywrightCli {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & npx --yes --package @playwright/cli playwright-cli "--session=$session" @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Playwright CLI failed with exit code $LASTEXITCODE"
    }
}

& npx --yes --package @playwright/cli playwright-cli "--session=$session" close 2>$null | Out-Null
& npx --yes --package @playwright/cli playwright-cli "--session=$session" open $Url
if ($LASTEXITCODE -ne 0) {
    throw "Playwright browser could not open with exit code $LASTEXITCODE"
}

$browserSmoke = @'
async (page) => {
  const failures = [];
  page.on("pageerror", (error) => failures.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") failures.push(`console: ${message.text()}`);
  });
  await page.reload();
  await page.locator(".example-group").nth(0).locator("button").first().click();
  await page.locator("button[type=submit]").click();
  await page.locator(".answer-card").waitFor({ state: "visible", timeout: 70000 });
  if (await page.locator(".answer-card").count() !== 1) throw new Error("sample answer card missing");
  if (await page.locator(".key-steps").count() !== 1) throw new Error("sample key steps missing");
  if (await page.locator(".evidence-section").count() !== 1) throw new Error("sample evidence missing");

  await page.locator(".example-group").nth(3).locator("button").first().click();
  await page.locator("button[type=submit]").click();
  await page.locator(".answer-card").waitFor({ state: "visible", timeout: 70000 });
  if (await page.locator(".vault-project-card").count() !== 1) throw new Error("Vault read-only card missing");
  if (await page.locator(".evidence-section").count() !== 1) throw new Error("Vault evidence missing");
  if (failures.length) throw new Error(failures.join(" | "));
}
'@

$browserSmokeFile = Join-Path $outputPath "browser-smoke.js"
[System.IO.File]::WriteAllText($browserSmokeFile, $browserSmoke, [System.Text.UTF8Encoding]::new($false))

Invoke-PlaywrightCli @("run-code", "--filename=$($OutputDirectory -replace '\\','/')/browser-smoke.js")
Invoke-PlaywrightCli @("screenshot", "--filename=$($OutputDirectory -replace '\\','/')/devsage-vault-answer.png", "--full-page")
Invoke-PlaywrightCli @("console")
Invoke-PlaywrightCli @("requests")
Write-Output "Browser regression passed: sample-data and obsidian-vault AI flows rendered with evidence and no page/console errors."
