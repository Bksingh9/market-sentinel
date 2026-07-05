# Market Sentinel Operating Guide

## Default Operation

The default mode is `disabled`. Use `paper` for mock or broker paper workflows. Use `backtest` for historical simulation.

## Commands

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli status
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli train-model --model-dir data\models
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli export-dashboard --path apps\control-center\public\status.json --model-dir data\models
```

## Real API Switches

Real API wiring is present but disabled by default.

- Alpaca paper/live HTTP order requests require `ALPACA_REAL_API_ENABLED=true`, `ALPACA_KEY_ID`, and `ALPACA_SECRET_KEY`.
- Alpaca live-small also requires `ALPACA_LIVE_TRADING_ENABLED=true`, `ALPACA_ACCOUNT_ID`, mode `live-small`, and passing risk/compliance gates.
- Groww live-small SDK order requests require `GROWW_REAL_API_ENABLED=true`, `GROWW_ACCESS_TOKEN`, `GROWW_ALGO_ID`, India live/compliance flags, mode `live-small`, and passing risk/compliance gates.
- Twilio alerts require `TWILIO_ALERTS_ENABLED=true`, account credentials, recipient, and either `TWILIO_MESSAGING_SERVICE_SID` for production sender pools or `TWILIO_FROM` for direct SMS. Set `TWILIO_STATUS_CALLBACK_URL` to receive delivery events.

## Machine Learning

The first ML model is advisory. It can score, rank, or filter strategy signals, but it cannot place orders, override blocked orders, or enable live-small mode. Model updates produce versioned artifacts and should be audited.

## Scheduled Intents

Scheduled order intents are queued candidates. When they become eligible, they must pass fresh market data, risk, compliance, account allowlist, runtime mode, and broker-readiness checks before the execution boundary can submit anything.

## Emergency Mode

Set `MARKET_SENTINEL_MODE=emergency` to block new orders. Future flatten-only behavior must keep new order creation blocked unless the operation is explicitly classified as risk-reducing.

## Live-Small Boundary

Live-small trading is unavailable until broker credentials, account allowlists, explicit live flags, compliance verification, risk gates, and audit paths are configured.
