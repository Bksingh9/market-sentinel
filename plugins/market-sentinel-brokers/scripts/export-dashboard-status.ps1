param(
    [ValidateSet("groww", "alpaca", "any")]
    [string]$Broker = "groww",
    [string]$RepoRoot = "",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = $env:MARKET_SENTINEL_PYTHON
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = "python"
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}

Push-Location $RepoRoot
try {
    $env:MARKET_SENTINEL_PRIMARY_BROKER = $Broker
    $env:MARKET_SENTINEL_MODE = "live-small"
    & $PythonExe -m market_sentinel.cli export-dashboard --path apps\control-center\public\status.json --model-dir data\models
} finally {
    Pop-Location
}
