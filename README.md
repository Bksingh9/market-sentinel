# Market Sentinel

Market Sentinel is a dual-market research and paper-observation system for `SPY` and `NIFTYBEES`. It downloads broker-supplied daily history, creates point-in-time features and cost-aware labels, evaluates calibrated logistic meta-labelers with purged walk-forward folds, and keeps US and India paper evidence separate.

Historical and paper results do not guarantee future performance. This workflow stops at paper evidence and does not activate real-money trading.

## Local Setup

Use environment variables or the existing local secret-entry workflow for broker credentials. Do not place credentials in commands, source files, datasets, model artifacts, or dashboard JSON.

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip install -e .
```

## Research Workflow

Download canonical daily history. Alpaca uses the official market-data endpoint; Groww uses the pinned official SDK operation.

```powershell
market-sentinel download-data --market US --symbol SPY --start 2021-01-01 --end 2026-07-16
market-sentinel download-data --market IN --symbol NIFTYBEES --start 2021-01-01 --end 2026-07-16
```

Build a candidate dataset with a reviewed, effective-dated cost profile. The cost profile is a local JSON file containing `market`, `currency`, `version`, and one or more schedules with `effective_from`, basis-point cost fields, `flat_fee`, and `source_notes`.

```powershell
market-sentinel build-dataset --market US --symbol SPY --dataset-id <dataset-id> --cost-profile <cost-profile.json>
market-sentinel build-dataset --market IN --symbol NIFTYBEES --dataset-id <dataset-id> --cost-profile <cost-profile.json> --corporate-action-record <reviewed-record.json>
```

Train and validate one market-specific challenger. The command records all calibration attempts, scores each test candidate once, saves failed trials, and does not change the active paper pointer.

```powershell
market-sentinel train-market-model --market US --symbol SPY --dataset-id <dataset-id>
market-sentinel validate-market-model --market US --symbol SPY --version <model-version>
```

Only an artifact that passed every mandatory fold gate can be promoted to its isolated paper lane.

```powershell
market-sentinel promote-to-paper --market US --symbol SPY --version <model-version>
market-sentinel paper-status --market US --symbol SPY
market-sentinel export-dashboard
```

`SPY` paper execution is restricted to `https://paper-api.alpaca.markets`. `NIFTYBEES` paper execution uses the local simulator and never submits a Groww order. Each lane requires 60 newly completed exchange sessions before becoming eligible for human review.

## Verification

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd' --dir apps/control-center run build
```

The read-only control center displays separate data, validation, drift, and paper evidence for each lane. It contains no credential fields, order controls, or combined trading-readiness switch.

## Documents

- `docs/superpowers/specs/2026-07-17-dual-market-ml-meta-label-design.md`
- `docs/superpowers/plans/2026-07-17-dual-market-ml-meta-label.md`
- `docs/compliance-checklist.md`
- `docs/operating-guide.md`
- `docs/deployment-and-tunnel-runbook.md`
