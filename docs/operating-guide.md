# Market Sentinel Operating Guide

## Default Operation

The default mode is `disabled`. Use `paper` for mock or broker paper workflows. Use `backtest` for historical simulation.

## Commands

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli status
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli live-preflight
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli ruflo-run-once
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli train-model --model-dir data\models
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli export-dashboard --path apps\control-center\public\status.json --model-dir data\models
```

## Real API Switches

Real API wiring is present but disabled by default.

- Set `MARKET_SENTINEL_PRIMARY_BROKER=groww` when Groww is the only allowed live broker. With a primary broker selected, other broker readiness does not make `ready_to_trade=true`.
- Alpaca paper/live HTTP order requests require `ALPACA_REAL_API_ENABLED=true`, `ALPACA_KEY_ID`, and `ALPACA_SECRET_KEY`.
- Alpaca live-small also requires `ALPACA_LIVE_TRADING_ENABLED=true`, `ALPACA_ACCOUNT_ID`, `ALPACA_TRADING_ENDPOINT=https://api.alpaca.markets`, mode `live-small`, and passing risk/compliance gates.
- Keep Alpaca keys in process environment variables or a private secret manager only. Do not commit keys, secrets, account IDs, or generated `.env` files.
- Groww live-small SDK order requests require an active Groww API subscription, the official `growwapi` SDK, either a locally generated `GROWW_ACCESS_TOKEN` or local-only `GROWW_API_KEY` plus `GROWW_SECRET_KEY`, `GROWW_REAL_API_ENABLED=true`, `GROWW_API_SUBSCRIPTION_ACTIVE=true`, `GROWW_PROTECTED_ORDER_CLIENT=true`, `GROWW_ALGO_ID`, India live/compliance flags, mode `live-small`, and passing risk/compliance gates.
- If Groww asks for static IP allowlisting, run the bot from a host with a fixed public IPv4 address, add that IP on the Groww Cloud API key page, then set `GROWW_STATIC_OUTBOUND_IP` and `GROWW_STATIC_IP_ALLOWLISTED=true`. A home broadband or hotspot IP is usually dynamic unless your ISP explicitly gives you a static IPv4.
- Do not run standalone Groww sample scripts that buy, sleep, and sell from this repository. Convert them into protected `OrderIntent` flows so every leg passes fresh risk, compliance, account allowlist, and broker-readiness checks.
- The Groww SDK bridge follows the official Python SDK flow: generate an access token from API key and secret, initialize `GrowwAPI(access_token)`, then submit protected limit orders with `order_reference_id`.
- Dhan live-small order requests use `POST https://api.dhan.co/v2/orders` with `access-token` and `dhanClientId`. Dhan order placement, modification, and cancellation require static IP whitelisting. Configure `DHAN_CLIENT_ID`, `DHAN_ACCESS_TOKEN`, `DHAN_REAL_API_ENABLED=true`, `DHAN_STATIC_OUTBOUND_IP`, `DHAN_STATIC_IP_ALLOWLISTED=true`, `DHAN_PROTECTED_ORDER_CLIENT=true`, and `DHAN_SECURITY_ID_MAP` such as `IDEA:14366,NIFTYBEES:10576`.
- Groww normal orders and Groww Smart Orders are separate API surfaces. The protected live client must attach or coordinate stop-loss/take-profit protection through the sanctioned Smart Orders/OCO/GTT flow before the broker adapter is allowed to submit live orders.
- Twilio alerts require `TWILIO_ALERTS_ENABLED=true`, account credentials, recipient, and either `TWILIO_MESSAGING_SERVICE_SID` for production sender pools or `TWILIO_FROM` for direct SMS. Set `TWILIO_STATUS_CALLBACK_URL` to receive delivery events.

## Machine Learning

The first ML model is advisory. It can score, rank, or filter strategy signals, but it cannot place orders, override blocked orders, or enable live-small mode. Model updates produce versioned artifacts and should be audited.

## Scheduled Intents

Scheduled order intents are queued candidates. When they become eligible, they must pass fresh market data, risk, compliance, account allowlist, runtime mode, and broker-readiness checks before the execution boundary can submit anything.

## Emergency Mode

Set `MARKET_SENTINEL_MODE=emergency` to block new orders. Future flatten-only behavior must keep new order creation blocked unless the operation is explicitly classified as risk-reducing.

## Live-Small Boundary

Live-small trading is unavailable until broker credentials, account allowlists, explicit live flags, compliance verification, risk gates, and audit paths are configured.

## RUFLO Runtime Boundary

RUFLO can retrieve sanitized live API readiness, coordinate gate checks, and run a paper-only supervised execution check. RUFLO cannot make discretionary trading calls, book profit autonomously, reveal secrets, or bypass `ExecutionAgent`, risk, compliance, broker, and runtime gates.
