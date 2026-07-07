param(
    [ValidateSet("groww", "alpaca")]
    [string]$Broker = "groww",
    [Parameter(Mandatory = $true)]
    [string]$Symbol,
    [ValidateSet("IN", "US")]
    [string]$Market = "",
    [ValidateSet("equity", "etf")]
    [string]$InstrumentType = "equity",
    [ValidateSet("buy", "sell")]
    [string]$Side = "buy",
    [Parameter(Mandatory = $true)]
    [string]$Quantity,
    [Parameter(Mandatory = $true)]
    [string]$LimitPrice,
    [Parameter(Mandatory = $true)]
    [string]$StopLoss,
    [Parameter(Mandatory = $true)]
    [string]$TakeProfit,
    [string]$StrategyId = "manual-supervised",
    [string]$AccountCash = "100000",
    [string]$AccountEquity = "100000",
    [string]$RepoRoot = "",
    [string]$PythonExe = "",
    [string]$ConfirmRealMoney = ""
)

$ErrorActionPreference = "Stop"

if ($ConfirmRealMoney -ne "I_CONFIRM_REAL_MONEY_ORDER") {
    throw "ConfirmRealMoney must be I_CONFIRM_REAL_MONEY_ORDER"
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = $env:MARKET_SENTINEL_PYTHON
}
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = "python"
}
if ([string]::IsNullOrWhiteSpace($Market)) {
    $Market = if ($Broker -eq "groww") { "IN" } else { "US" }
}

Push-Location $RepoRoot
try {
    & $PythonExe -m market_sentinel.cli submit-order `
        --broker $Broker `
        --symbol $Symbol `
        --market $Market `
        --instrument-type $InstrumentType `
        --side $Side `
        --quantity $Quantity `
        --limit-price $LimitPrice `
        --stop-loss $StopLoss `
        --take-profit $TakeProfit `
        --strategy-id $StrategyId `
        --account-cash $AccountCash `
        --account-equity $AccountEquity `
        --confirm-real-money I_CONFIRM_REAL_MONEY_ORDER
} finally {
    Pop-Location
}

