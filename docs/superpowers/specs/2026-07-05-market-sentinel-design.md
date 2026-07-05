# Market Sentinel Design

## Approved Direction

Build Market Sentinel as a safe local trading automation scaffold plus a Sites-hosted control center. The first deliverable is not a profit guarantee and must not be described as one. It is a disciplined research, paper-trading, audit, and broker-integration foundation that defaults to disabled or mock execution.

The build is based on the referenced file:

`C:/Users/Dell/Documents/Codex/2026-07-05/create-me-a-never-losing-bot/outputs/market-sentinel-full-build-spec.md`

## Goals

- Provide a working local engine for market data validation, feature computation, strategy signals, risk checks, compliance gates, execution routing, portfolio accounting, and analysis.
- Provide a Sites control center that shows runtime mode, broker readiness, risk status, validation-gate progress, audit events, paper-trading state, and emergency status.
- Make mock or paper operation useful immediately.
- Include machine-learning training, model update, model versioning, and advisory inference from historical or paper-trading data.
- Include scheduled order intents so candidate orders can be queued for future evaluation without bypassing risk, compliance, or execution gates.
- Keep live-small operation blocked until broker credentials, account allowlists, explicit live flags, risk limits, and compliance checks are configured.
- Keep Groww India and Alpaca US broker boundaries isolated behind adapters.
- Make command-line simulation and backtesting incapable of live order submission, even if live broker credentials exist.
- Include GitHub-ready project structure, commits, and review flow.
- Include an Expo native-module lane as a deferred integration option, not as part of the first engine or Sites dashboard unless a mobile app becomes an explicit target.
- Include CodeRabbit as a post-change review gate once there is a git diff or pull request to review.

## Non-Goals

- Do not claim the bot can never lose.
- Do not provide personalized investment advice, suitability determinations, or guaranteed buy/sell recommendations.
- Do not build high-frequency trading, co-location, latency arbitrage, or exchange-direct order routing.
- Do not enable naked options or unsupported shorting.
- Do not build a mobile app in the first pass.
- Do not add LangGraph or external agent frameworks before the RUFLO/LangGraph adoption checklist item is reviewed.
- Do not make the Sites dashboard place live orders directly.
- Do not let model predictions or scheduled orders bypass the `RiskAgent`, `ComplianceGuard`, or `ExecutionAgent`.

## Project Shape

The current workspace has no source repo yet. The first implementation should create a repository-style project rooted at the current workspace:

- `market_sentinel/`: Python package for the trading engine.
- `tests/`: Python unit and integration-style tests using mocks.
- `apps/control-center/`: Sites-compatible React/vinext control center.
- `docs/`: design, implementation plan, broker notes, compliance checklist, and operating guide.
- `.openai/hosting.json`: Sites metadata once a site is created.
- `.env.example`: local development keys with no secrets.

## Engine Architecture

The Python engine should be split into focused modules:

- `config`: typed runtime settings, risk defaults, environment gates, and mode parsing.
- `models`: quote, bar, signal, order intent, order request, fill, position, account, portfolio, risk decision, compliance decision, and audit event types.
- `market_data`: `MarketDataAgent` that rejects stale, malformed, or impossible quotes.
- `features`: `FeatureStore` with leakage-safe rolling features shared by backtest and paper simulation.
- `prediction`: `MLPredictionAgent` as advisory-only baseline scoring. It can filter or rank signals but cannot create order authority.
- `training`: trainable baseline ML model creation from labeled historical or paper-trading examples.
- `model_store`: versioned model artifact persistence and activation metadata.
- `strategy`: `StrategyAgent` plugin host for simple rule-based strategies.
- `scheduler`: scheduled order intents that become eligible at a future time and then re-enter the normal risk/compliance/execution path.
- `risk`: `RiskAgent` for position sizing, stop-loss and take-profit requirements, drawdown caps, max position caps, and disallowed instrument checks.
- `compliance`: `ComplianceGuard` for account allowlists, mode gates, broker-session freshness, market hours, broker rate budgets, and India live-trading checks.
- `execution`: `ExecutionAgent`, the only component allowed to call broker `place_order`.
- `brokers`: mock broker, Groww adapter, and Alpaca adapter.
- `portfolio`: `PortfolioAgent` for fills, positions, cash, realized P&L, and unrealized P&L snapshots.
- `analysis`: `AnalysisAgent` for backtest summaries, equity curves, and validation metrics.
- `ruflo`: `RUFLOAgent` for coordination-only research, reports, and checklist status with no order authority.
- `audit`: append-only audit writer and reader.
- `cli`: commands for status, backtest, simulate-paper, broker-readiness, and emergency mode.

## Broker Boundaries

### Groww

Groww support starts as mock/paper by default. The adapter may expose a real SDK boundary later, but live India trading must stay blocked unless all of these are true:

- `INDIA_LIVE_TRADING_ENABLED=true`
- `INDIA_ALGO_COMPLIANCE_VERIFIED=true`
- `GROWW_ALGO_ID` is present
- the account is on the configured allowlist
- the mode is `live-small`
- the strategy, market, and instrument are within the configured live-small allowlist
- the order has stop-loss and take-profit protection
- broker-session freshness and market-hours checks pass

The implementation should model Groww rate-limit budgets for order, live data, and non-trading calls so the compliance layer can block bursts before they reach the adapter.

### Alpaca

Alpaca support starts with mock and paper paths. The adapter should keep paper and live endpoint configuration separate. Live Alpaca trading requires:

- explicit `ALPACA_LIVE_TRADING_ENABLED=true`
- account allowlist match
- mode `live-small`
- one configured market and one configured strategy
- risk and compliance approval
- stop-loss and take-profit protection on every order

### Simulator and Backtest Safety

Backtest and simulation commands must use simulator broker interfaces only. These commands must not instantiate real broker adapters that can submit live HTTP orders. Tests should prove this by injecting a broker that fails the test if live `place_order` is touched.

## Machine Learning Lifecycle

The first implementation should include real machine-learning plumbing while staying dependency-light:

- train a baseline linear scoring model from leakage-safe features and labeled outcomes;
- save model artifacts as versioned JSON files with feature names, weights, bias, training window, metrics, and creation timestamp;
- load the active model for advisory inference;
- update the active model only after validation metrics and audit logging;
- expose model version, last trained timestamp, feature set, and validation metrics in CLI output and the Sites control center.

The ML model can rank, filter, or annotate strategy signals. It cannot independently place orders, override a block, change runtime mode, or mark live-small trading as compliant. Backtest and paper performance reports should show model metrics next to drawdown and rejected-order data so the UI does not overstate model quality.

## Scheduled Order Intents

Scheduled orders should be represented as scheduled order intents, not broker-native live orders in the first pass. A scheduled intent includes:

- order intent;
- scheduled eligibility time;
- expiration time;
- reason or strategy source;
- created model version when ML influenced the schedule;
- status such as `pending`, `eligible`, `expired`, `blocked`, `submitted`, or `cancelled`.

When a scheduled intent becomes eligible, it must be re-evaluated against fresh market data, risk limits, compliance gates, account allowlists, runtime mode, and broker readiness. If any gate blocks the intent, the scheduler records the block reason and does not call the broker.

## Risk Defaults

The first implementation should encode these defaults:

- Cash and ETF risk per trade: 0.25 percent.
- Options, F&O, commodity, and crypto risk per trade: 0.10 percent.
- Daily loss stop: 1 percent.
- Weekly drawdown stop: 3 percent.
- Monthly drawdown stop: 6 percent.
- Max positions: 3 per market, 6 total.
- No naked options.
- No unsupported shorting.
- Every order intent must include stop-loss and take-profit protection before execution.

Risk decisions should be explicit allow/block objects with reasons. Blocks should be shown in CLI output, audit logs, and the Sites control center.

## Public Equity Investing Guardrails

The scaffold may compute signals, risk decisions, backtest metrics, and paper-trading summaries for listed equities and ETFs. Those outputs are research and operations artifacts, not personalized investment advice. The UI and CLI should describe strategy outputs as signals or order intents that remain subject to risk, compliance, and user-controlled operating gates.

When the system reports performance, it should include drawdown, costs, rejected orders, blocked orders, and validation status alongside returns. It should avoid isolated win-rate claims and should not imply future performance from backtests or paper results.

## Runtime Modes

- `disabled`: no orders.
- `backtest`: historical simulation only.
- `paper`: mock or broker paper flow.
- `live-small`: gated live trading only after explicit flags and compliance checks.
- `emergency`: blocks new orders and supports future flatten-only behavior.

Mode parsing should be strict. Unknown values should fail closed to `disabled`.

## Sites Control Center

The control center should be an operational dashboard, not a marketing page. The first screen should show the system state immediately:

- current mode and emergency status
- broker readiness for Groww and Alpaca
- active ML model version, last trained timestamp, and validation metrics
- scheduled order intents and their current gate status
- risk budget and drawdown status
- validation gates
- latest audit events
- paper-trading equity summary
- blocked-order reasons
- compliance checklist status

The dashboard may read from static JSON fixtures or generated local artifacts in the first pass. It must not expose live secrets. It must not directly place live orders. Controls may stage local mode files or show disabled/live-blocked state, but any live trading enablement must remain engine-side and environment-gated.

If the user asks to deploy, the Sites flow should create `.openai/hosting.json`, create or reuse a Sites project, validate the build, save a version from committed source, and deploy only according to the Sites access rules.

## GitHub Flow

Because the current workspace is not a git repository, implementation should initialize a local repo before the first commit unless the user provides an existing repository target. The first meaningful commits should be:

1. design spec
2. implementation plan
3. engine foundation and tests
4. broker safety gates and tests
5. control center
6. validation and operating docs

If a remote repository is provided later, use the GitHub connector or local git/gh as appropriate to push and open a draft pull request.

## Expo Lane

Expo native-module work is deferred from the first build. It becomes relevant if the user asks for a mobile app or native device capability such as secure local credential storage, push-alert integration, biometric approval, or background status checks.

If activated later, scaffold the native module with `create-expo-module` first, rename the generated local module directory to the intended kebab-case name, remove generated boilerplate, and keep the module limited to the specific native capability requested.

## CodeRabbit Review Gate

CodeRabbit should run after there is a git repository and a meaningful committed or uncommitted diff. It should not be used before code exists. The review output should be treated as review feedback, not as proof of correctness. Any accepted findings should be fixed with tests.

## Testing Strategy

Use test-driven development for production behavior:

- config and mode parsing tests
- quote validation tests
- leakage-safe feature tests
- model training, model save/load, model update, and advisory inference tests
- scheduled order tests for pending, eligible, expired, and blocked states
- strategy signal tests
- risk sizing and block-reason tests
- compliance gate tests for disabled, backtest, paper, live-small, and emergency modes
- Groww and Alpaca adapter tests using mocks for rejects, partial fills, disconnects, and rate limits
- execution-agent tests proving only `ExecutionAgent` can place orders
- simulator/backtest tests proving live broker HTTP paths are unreachable
- portfolio accounting tests
- analysis summary tests
- dashboard data fixture tests
- Sites build validation

## Validation Gates

The first software milestone is complete only when:

- unit tests pass
- backtest uses leakage-safe features and realistic fills/costs
- paper simulation can run without live credentials
- model training and update commands produce versioned artifacts and audit events
- scheduled order intents cannot bypass risk, compliance, or execution gates
- daily reconciliation and audit log paths exist
- P0 alert and emergency drill hooks exist
- live-small remains blocked without explicit compliance settings
- adapter integration tests cover mocked rejects, partial fills, and disconnects
- dependency licenses are listed for review
- Groww, Alpaca, and India algo compliance checklist items are documented as required human verification gates

The four-week paper gate is a real operating requirement and cannot be marked complete by initial scaffolding.

## Open Decisions

- Remote GitHub repository target is not known yet.
- Sites deployment should wait until the control center exists and the user confirms deployment if access cannot be verified as owner-only.
- Expo mobile/native functionality is deferred until requested.
- Live-small trading must remain unavailable until the human compliance checklist is completed outside this build.
