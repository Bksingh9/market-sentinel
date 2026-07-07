# Copy this file outside git, fill fresh broker values locally, then dot-source it
# in the same PowerShell session before running readiness checks.
#
# Example:
#   Copy-Item plugins\market-sentinel-brokers\scripts\local-env-template.ps1 .local-broker-env.ps1
#   notepad .local-broker-env.ps1
#   . .\.local-broker-env.ps1

$env:MARKET_SENTINEL_MODE = "live-small"
$env:MARKET_SENTINEL_PRIMARY_BROKER = "groww"

$env:INDIA_LIVE_TRADING_ENABLED = "true"
$env:INDIA_ALGO_COMPLIANCE_VERIFIED = "true"

$env:GROWW_REAL_API_ENABLED = "true"
$env:GROWW_API_SUBSCRIPTION_ACTIVE = "true"
$env:GROWW_PROTECTED_ORDER_CLIENT = "true"
$env:GROWW_STATIC_OUTBOUND_IP = ""
$env:GROWW_STATIC_IP_ALLOWLISTED = "false"
$env:GROWW_ALGO_ID = ""
$env:GROWW_API_KEY = ""
$env:GROWW_SECRET_KEY = ""
$env:GROWW_ACCESS_TOKEN = ""

$env:ALPACA_LIVE_TRADING_ENABLED = "false"
$env:ALPACA_REAL_API_ENABLED = "false"
$env:ALPACA_TRADING_ENDPOINT = "https://api.alpaca.markets"
$env:ALPACA_ACCOUNT_ID = ""
$env:ALPACA_KEY_ID = ""
$env:ALPACA_SECRET_KEY = ""
