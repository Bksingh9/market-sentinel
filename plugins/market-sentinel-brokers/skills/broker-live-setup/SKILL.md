---
name: broker-live-setup
description: Use when the user asks to set up, verify, or operate the Market Sentinel Groww and Alpaca broker path, including live-readiness checks, environment setup, credential handling guidance, static IP gates, and supervised order-confirmation flow.
---

# Market Sentinel Broker Live Setup

This skill supports the local Market Sentinel repository. It treats Alpaca and Groww as already wired broker adapters and focuses on live readiness, setup, verification, and safe operation.

## Safety Boundary

- Never retrieve, reveal, copy, paste, store, or reuse broker credentials from browser pages, chat messages, logs, screenshots, or clipboard-like context.
- If credentials were pasted into chat or exposed in browser context, tell the user to revoke and regenerate them before live use.
- Do not place or trigger a real-money order unless the local live preflight passes and the user confirms the exact order parameters in the current conversation: broker, symbol, side, quantity, limit price, stop loss, take profit, and product/session if applicable.
- Do not change `ready_to_trade` by hand. It must be produced by the preflight from real local environment values.
- Do not bypass Groww static IP, compliance, protected-order, or subscription gates.
- Prefer Groww as the primary broker when `MARKET_SENTINEL_PRIMARY_BROKER` is unset or the user has not explicitly switched broker.

## Repository Assumptions

- Main package: `market_sentinel`
- Preflight command: `python -m market_sentinel.cli live-preflight`
- Dashboard export command: `python -m market_sentinel.cli export-dashboard --path apps/control-center/public/status.json --model-dir data/models`
- Primary broker env: `MARKET_SENTINEL_PRIMARY_BROKER`
- Live-small mode env: `MARKET_SENTINEL_MODE=live-small`

## Broker Readiness

For Groww to be live-ready, the local environment must contain valid fresh values for:

- `MARKET_SENTINEL_PRIMARY_BROKER=groww`
- `MARKET_SENTINEL_MODE=live-small`
- `INDIA_LIVE_TRADING_ENABLED=true`
- `INDIA_ALGO_COMPLIANCE_VERIFIED=true`
- `GROWW_REAL_API_ENABLED=true`
- `GROWW_API_SUBSCRIPTION_ACTIVE=true`
- `GROWW_PROTECTED_ORDER_CLIENT=true`
- `GROWW_STATIC_OUTBOUND_IP=<public static IPv4>`
- `GROWW_STATIC_IP_ALLOWLISTED=true`
- `GROWW_ALGO_ID=<broker-approved algo id>`
- either `GROWW_ACCESS_TOKEN=<fresh token>` or both `GROWW_API_KEY=<fresh key>` and `GROWW_SECRET_KEY=<fresh secret>`

For Alpaca to be live-ready, the local environment must contain valid fresh values for:

- `MARKET_SENTINEL_PRIMARY_BROKER=alpaca`
- `MARKET_SENTINEL_MODE=live-small`
- `ALPACA_LIVE_TRADING_ENABLED=true`
- `ALPACA_REAL_API_ENABLED=true`
- `ALPACA_TRADING_ENDPOINT=https://api.alpaca.markets`
- `ALPACA_ACCOUNT_ID=<live account id>`
- `ALPACA_KEY_ID=<fresh key id>`
- `ALPACA_SECRET_KEY=<fresh secret>`

## Workflow

1. Acknowledge the requested broker path and state that credentials must be set locally, not retrieved from browser/chat.
2. Use `scripts/check-readiness.ps1` from this plugin when the user asks for readiness status.
3. Use `scripts/export-dashboard-status.ps1` when the user wants the dashboard refreshed after setting env values.
4. Use `scripts/start-live-session.ps1` when the user wants a local setup wizard. It prompts for secrets locally, does not echo them, runs preflight, refreshes the dashboard, and starts the local dashboard.
5. Use `scripts/submit-confirmed-order.ps1` only after preflight is ready and the user provides exact real-money order parameters and the confirmation phrase `I_CONFIRM_REAL_MONEY_ORDER`.
6. If preflight fails, report only the missing gate names, not secret values.
7. If preflight passes, state that the system is ready for supervised order submission, then ask for exact order parameters before any real order action.

## Script Usage

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File plugins\market-sentinel-brokers\scripts\check-readiness.ps1 -Broker groww
```

Refresh dashboard status:

```powershell
powershell -ExecutionPolicy Bypass -File plugins\market-sentinel-brokers\scripts\export-dashboard-status.ps1 -Broker groww
```

Run the local setup wizard:

```powershell
powershell -ExecutionPolicy Bypass -File plugins\market-sentinel-brokers\scripts\start-live-session.ps1 -Broker groww
```

Submit a confirmed live order only after the preflight is ready:

```powershell
powershell -ExecutionPolicy Bypass -File plugins\market-sentinel-brokers\scripts\submit-confirmed-order.ps1 -Broker groww -Symbol IDEA -Quantity 1 -LimitPrice 10.50 -StopLoss 10.00 -TakeProfit 11.50 -ConfirmRealMoney I_CONFIRM_REAL_MONEY_ORDER
```
