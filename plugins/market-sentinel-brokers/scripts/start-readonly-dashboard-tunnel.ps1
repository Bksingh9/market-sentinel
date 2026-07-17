param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,
    [string]$TunnelName = "market-sentinel-control",
    [string]$CloudflaredExe = "cloudflared"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Named tunnel config not found. Copy ops\tunnel\cloudflared-market-sentinel.example.yml to a private path and fill in the tunnel values."
}

$cloudflared = Get-Command $CloudflaredExe -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    throw "cloudflared was not found on PATH. Install the official cloudflare/cloudflared client, then retry."
}

Write-Host "Starting read-only Market Sentinel dashboard tunnel through a named cloudflared tunnel."
Write-Host "Confirm Cloudflare Access is enabled for the hostname before sharing the URL."
& $cloudflared.Source tunnel --config $ConfigPath run $TunnelName
