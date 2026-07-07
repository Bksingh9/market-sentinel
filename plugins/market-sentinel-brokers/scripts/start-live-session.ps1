param(
    [ValidateSet("groww", "alpaca")]
    [string]$Broker = "groww",
    [string]$RepoRoot = "",
    [string]$PythonExe = "",
    [string]$NodeExe = "",
    [int]$Port = 4181,
    [switch]$NoDashboard
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
    }
    return (Resolve-Path $Value).Path
}

function Read-SecretText {
    param([string]$Prompt)
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

function Read-RequiredText {
    param([string]$Prompt, [string]$Default = "")
    if ([string]::IsNullOrWhiteSpace($Default)) {
        $value = Read-Host -Prompt $Prompt
    } else {
        $value = Read-Host -Prompt "$Prompt [$Default]"
        if ([string]::IsNullOrWhiteSpace($value)) {
            $value = $Default
        }
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "$Prompt is required"
    }
    return $value.Trim()
}

function Read-Yes {
    param([string]$Prompt)
    $value = Read-Host -Prompt "$Prompt Type YES to confirm"
    return $value -eq "YES"
}

function Read-CredentialMode {
    while ($true) {
        $value = Read-RequiredText "Credential mode only. Type access-token or key-secret" "key-secret"
        $value = $value.Trim().ToLowerInvariant()
        if ($value -in @("access-token", "key-secret")) {
            return $value
        }
        Write-Host "That was not a credential mode. Do not paste keys here; type only access-token or key-secret." -ForegroundColor Yellow
    }
}

$RepoRoot = Resolve-RepoRoot $RepoRoot
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = $env:MARKET_SENTINEL_PYTHON
}
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = "python"
}
if ([string]::IsNullOrWhiteSpace($NodeExe)) {
    $NodeExe = $env:MARKET_SENTINEL_NODE
}
if ([string]::IsNullOrWhiteSpace($NodeExe)) {
    $NodeExe = "node"
}

Push-Location $RepoRoot
try {
    $accountId = Read-RequiredText "Market Sentinel account id" "paper-local"
    $env:MARKET_SENTINEL_MODE = "live-small"
    $env:MARKET_SENTINEL_PRIMARY_BROKER = $Broker
    $env:MARKET_SENTINEL_ACCOUNT_ID = $accountId
    $env:MARKET_SENTINEL_ACCOUNT_ALLOWLIST = $accountId

    if ($Broker -eq "groww") {
        $env:INDIA_LIVE_TRADING_ENABLED = "true"
        $env:INDIA_ALGO_COMPLIANCE_VERIFIED = if (Read-Yes "India algo/compliance obligations are verified") { "true" } else { "false" }
        $env:GROWW_REAL_API_ENABLED = "true"
        $env:GROWW_API_SUBSCRIPTION_ACTIVE = if (Read-Yes "Groww API subscription is active") { "true" } else { "false" }
        $env:GROWW_PROTECTED_ORDER_CLIENT = if (Read-Yes "Groww protected order flow is configured for stop-loss/take-profit") { "true" } else { "false" }
        $env:GROWW_STATIC_OUTBOUND_IP = Read-RequiredText "Groww allowlisted static public IPv4"
        $env:GROWW_STATIC_IP_ALLOWLISTED = if (Read-Yes "That static IP is allowlisted in Groww") { "true" } else { "false" }
        $env:GROWW_ALGO_ID = Read-RequiredText "Groww broker-approved algo id"

        $credentialMode = Read-CredentialMode
        $env:GROWW_ACCESS_TOKEN = ""
        $env:GROWW_API_KEY = ""
        $env:GROWW_SECRET_KEY = ""
        if ($credentialMode -eq "access-token") {
            $env:GROWW_ACCESS_TOKEN = Read-SecretText "Groww access token"
        } elseif ($credentialMode -eq "key-secret") {
            $env:GROWW_API_KEY = Read-SecretText "Groww API key"
            $env:GROWW_SECRET_KEY = Read-SecretText "Groww secret key"
        }
    } elseif ($Broker -eq "alpaca") {
        $env:ALPACA_LIVE_TRADING_ENABLED = "true"
        $env:ALPACA_REAL_API_ENABLED = "true"
        $env:ALPACA_TRADING_ENDPOINT = "https://api.alpaca.markets"
        $env:ALPACA_ACCOUNT_ID = Read-RequiredText "Alpaca live account id"
        $env:ALPACA_KEY_ID = Read-SecretText "Alpaca key id"
        $env:ALPACA_SECRET_KEY = Read-SecretText "Alpaca secret key"
    }

    Write-Host "Running live preflight..."
    $preflightText = & $PythonExe -m market_sentinel.cli live-preflight
    $preflightText

    Write-Host "Refreshing dashboard status..."
    & $PythonExe -m market_sentinel.cli export-dashboard --path apps\control-center\public\status.json --model-dir data\models

    if (-not $NoDashboard) {
        $app = Join-Path $RepoRoot "apps\control-center"
        $out = Join-Path $RepoRoot "vinext-start-$Port.out.log"
        $err = Join-Path $RepoRoot "vinext-start-$Port.err.log"
        Start-Process -FilePath $NodeExe -ArgumentList @("node_modules\vinext\dist\cli.js", "dev", "--host", "127.0.0.1", "--port", "$Port") -WorkingDirectory $app -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
        Write-Host "Dashboard requested at http://localhost:$Port/"
        Start-Process "http://localhost:$Port/"
    }

    Write-Host "Session complete. Secrets were kept in this PowerShell process and child processes only."
} finally {
    Pop-Location
}
