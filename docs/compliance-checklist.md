# Market Sentinel Compliance Checklist

These gates require human verification before any live-small trading run.

## Broker And Regulatory Gates

- Verify Groww API permissions, order endpoints, and current India algo obligations.
- Verify India live trading has an assigned algo identifier when required.
- Verify Alpaca paper and live endpoint separation.
- Verify Alpaca account type, market-data tier, and trading permissions.
- Verify Twilio sender, recipient consent, delivery limits, and alert escalation policy.

## Operating Gates

- Unit tests pass.
- Backtest uses leakage-safe features and realistic fills/costs.
- Model training produces a versioned artifact with validation metrics.
- Model updates are audited before an active version changes.
- Scheduled order intents are rechecked when eligible and cannot bypass risk or compliance.
- Four full weeks of paper trading are complete.
- Daily reconciliation and audit logs are clean.
- P0 alert path is tested.
- Emergency drill is tested.
- Live-small starts with one market, one strategy, and minimal capital.

## Explicit Non-Advice Boundary

Market Sentinel outputs are research, simulation, risk, and operations artifacts. They are not personalized investment advice or a guarantee of future performance.
