# Market Sentinel

Market Sentinel is a safe-by-default trading automation scaffold for research, backtesting, paper trading, and tightly gated broker integration.

It does not guarantee profits and does not provide personalized investment advice. Live-small trading is blocked until explicit broker, account, risk, and compliance gates are configured.

## Local Checks

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
```

## Default Mode

The default runtime mode is `disabled`. Backtests and simulations use simulator broker paths and must never submit live broker orders.
