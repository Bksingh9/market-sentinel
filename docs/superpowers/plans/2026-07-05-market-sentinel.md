# Market Sentinel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe-by-default Market Sentinel scaffold with a tested Python trading engine, advisory machine-learning training/update flow, scheduled order intents, and a Sites control center for status, risk, compliance, audit, model, schedule, and validation gates.

**Architecture:** The core trading logic lives in a dependency-light Python package with explicit models, trainable advisory ML artifacts, scheduled order intents, agents, broker boundaries, and CLI commands. The Sites control center reads generated status JSON and presents operational state without broker secrets or direct live-order controls. Live-small trading remains blocked unless environment gates, account allowlists, risk checks, and compliance checks all pass, and neither ML predictions nor scheduled intents can bypass those gates.

**Tech Stack:** Python 3 standard library, `unittest`, React 19, vinext, Sites, local Git, optional CodeRabbit CLI review after a meaningful diff exists.

---

## Runtime Commands

Use these bundled executables on this machine:

- Python: `C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`
- Git: `C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe`
- Node: `C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe`

Python tests should run without package downloads:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
```

---

## File Structure

- `pyproject.toml`: package metadata and CLI entry point.
- `.env.example`: local runtime keys with no secrets.
- `README.md`: safety summary and local commands.
- `market_sentinel/config.py`: strict runtime mode parsing, risk defaults, broker gates, and environment loading.
- `market_sentinel/models.py`: dataclasses and enums shared across agents.
- `market_sentinel/market_data.py`: quote validation.
- `market_sentinel/features.py`: leakage-safe rolling features.
- `market_sentinel/prediction.py`: advisory-only baseline scoring.
- `market_sentinel/model_training.py`: dependency-light model training and metrics.
- `market_sentinel/model_store.py`: versioned model artifact persistence and active-model pointer.
- `market_sentinel/strategy.py`: rule-based signal generation.
- `market_sentinel/scheduler.py`: scheduled order intents and due/expired state handling.
- `market_sentinel/risk.py`: sizing, stop/take-profit enforcement, drawdown and position caps.
- `market_sentinel/compliance.py`: mode, account, market-hours, live-small, and India algo gates.
- `market_sentinel/brokers.py`: mock, Groww, and Alpaca broker boundaries.
- `market_sentinel/execution.py`: only order placement boundary.
- `market_sentinel/portfolio.py`: cash, positions, fills, and P&L.
- `market_sentinel/analysis.py`: backtest and equity summaries.
- `market_sentinel/audit.py`: append-only JSONL audit writer and reader.
- `market_sentinel/ruflo.py`: coordination-only checklist reporting.
- `market_sentinel/cli.py`: `status`, `backtest`, `simulate-paper`, `broker-readiness`, `emergency`, and `export-dashboard`.
- `tests/`: unit and integration-style tests.
- `apps/control-center/`: vinext Sites app.
- `docs/compliance-checklist.md`: human verification gates.
- `docs/operating-guide.md`: safe operation guide.

---

### Task 1: Repository And Package Baseline

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `README.md`
- Create: `market_sentinel/__init__.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_smoke.py`:

```python
import unittest


class SmokeTest(unittest.TestCase):
    def test_package_exposes_version(self):
        import market_sentinel

        self.assertEqual(market_sentinel.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_smoke -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'market_sentinel'`.

- [ ] **Step 3: Add the minimal package baseline**

Create `market_sentinel/__init__.py`:

```python
"""Market Sentinel safe trading automation scaffold."""

__version__ = "0.1.0"
```

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "market-sentinel"
version = "0.1.0"
description = "Safe-by-default market automation scaffold for research, paper trading, and gated broker execution."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "Proprietary" }
authors = [{ name = "Codex" }]

[project.scripts]
market-sentinel = "market_sentinel.cli:main"
```

Create `.env.example`:

```dotenv
MARKET_SENTINEL_MODE=disabled
MARKET_SENTINEL_ACCOUNT_ID=paper-local
MARKET_SENTINEL_ACCOUNT_ALLOWLIST=paper-local
INDIA_LIVE_TRADING_ENABLED=false
INDIA_ALGO_COMPLIANCE_VERIFIED=false
GROWW_ALGO_ID=
GROWW_ACCESS_TOKEN=
ALPACA_PAPER_TRADING_ENABLED=true
ALPACA_LIVE_TRADING_ENABLED=false
ALPACA_KEY_ID=
ALPACA_SECRET_KEY=
ALPACA_ACCOUNT_ID=
```

Create `README.md`:

```markdown
# Market Sentinel

Market Sentinel is a safe-by-default trading automation scaffold for research, backtesting, paper trading, and tightly gated broker integration.

It does not guarantee profits and does not provide personalized investment advice. Live-small trading is blocked until explicit broker, account, risk, and compliance gates are configured.

## Local Checks

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
```

## Default Mode

The default runtime mode is `disabled`. Backtests and simulations use simulator broker paths and must never submit live broker orders.
```

- [ ] **Step 4: Run the smoke test to verify it passes**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_smoke -v
```

Expected: PASS with `Ran 1 test`.

- [ ] **Step 5: Commit the package baseline**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add pyproject.toml .env.example README.md market_sentinel tests
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add market sentinel package baseline'
```

Expected: commit succeeds.

---

### Task 2: Runtime Config And Shared Models

**Files:**
- Create: `market_sentinel/config.py`
- Create: `market_sentinel/models.py`
- Test: `tests/test_config_and_models.py`

- [ ] **Step 1: Write failing config and model tests**

Create `tests/test_config_and_models.py`:

```python
import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from market_sentinel.config import RuntimeMode, load_settings
from market_sentinel.models import InstrumentType, OrderIntent, Side


class ConfigAndModelsTest(unittest.TestCase):
    def test_unknown_mode_fails_closed_to_disabled(self):
        with patch.dict(os.environ, {"MARKET_SENTINEL_MODE": "fast-live"}, clear=True):
            settings = load_settings()

        self.assertEqual(settings.mode, RuntimeMode.DISABLED)

    def test_risk_defaults_are_conservative(self):
        settings = load_settings({})

        self.assertEqual(settings.cash_etf_risk_per_trade, Decimal("0.0025"))
        self.assertEqual(settings.derivative_risk_per_trade, Decimal("0.0010"))
        self.assertEqual(settings.daily_loss_stop, Decimal("0.01"))
        self.assertEqual(settings.weekly_drawdown_stop, Decimal("0.03"))
        self.assertEqual(settings.monthly_drawdown_stop, Decimal("0.06"))
        self.assertEqual(settings.max_positions_per_market, 3)
        self.assertEqual(settings.max_positions_total, 6)

    def test_order_intent_requires_protection(self):
        intent = OrderIntent(
            symbol="SPY",
            market="US",
            instrument_type=InstrumentType.ETF,
            side=Side.BUY,
            quantity=Decimal("1"),
            limit_price=Decimal("500"),
            stop_loss=None,
            take_profit=Decimal("510"),
            strategy_id="mean-reversion",
        )

        self.assertFalse(intent.has_protection())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_config_and_models -v
```

Expected: FAIL with import errors for `market_sentinel.config` or `market_sentinel.models`.

- [ ] **Step 3: Add config and model implementation**

Create `market_sentinel/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
import os


class RuntimeMode(StrEnum):
    DISABLED = "disabled"
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE_SMALL = "live-small"
    EMERGENCY = "emergency"


@dataclass(frozen=True)
class Settings:
    mode: RuntimeMode = RuntimeMode.DISABLED
    account_id: str = "paper-local"
    account_allowlist: frozenset[str] = field(default_factory=lambda: frozenset({"paper-local"}))
    cash_etf_risk_per_trade: Decimal = Decimal("0.0025")
    derivative_risk_per_trade: Decimal = Decimal("0.0010")
    daily_loss_stop: Decimal = Decimal("0.01")
    weekly_drawdown_stop: Decimal = Decimal("0.03")
    monthly_drawdown_stop: Decimal = Decimal("0.06")
    max_positions_per_market: int = 3
    max_positions_total: int = 6
    india_live_trading_enabled: bool = False
    india_algo_compliance_verified: bool = False
    groww_algo_id: str | None = None
    alpaca_paper_trading_enabled: bool = True
    alpaca_live_trading_enabled: bool = False
    alpaca_account_id: str | None = None


def _parse_mode(value: str | None) -> RuntimeMode:
    if value in {mode.value for mode in RuntimeMode}:
        return RuntimeMode(value)
    return RuntimeMode.DISABLED


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_allowlist(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset({"paper-local"})
    entries = {item.strip() for item in value.split(",") if item.strip()}
    return frozenset(entries or {"paper-local"})


def load_settings(env: dict[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env
    groww_algo_id = source.get("GROWW_ALGO_ID") or None
    alpaca_account_id = source.get("ALPACA_ACCOUNT_ID") or None
    return Settings(
        mode=_parse_mode(source.get("MARKET_SENTINEL_MODE")),
        account_id=source.get("MARKET_SENTINEL_ACCOUNT_ID", "paper-local"),
        account_allowlist=_parse_allowlist(source.get("MARKET_SENTINEL_ACCOUNT_ALLOWLIST")),
        india_live_trading_enabled=_parse_bool(source.get("INDIA_LIVE_TRADING_ENABLED")),
        india_algo_compliance_verified=_parse_bool(source.get("INDIA_ALGO_COMPLIANCE_VERIFIED")),
        groww_algo_id=groww_algo_id,
        alpaca_paper_trading_enabled=_parse_bool(source.get("ALPACA_PAPER_TRADING_ENABLED"), default=True),
        alpaca_live_trading_enabled=_parse_bool(source.get("ALPACA_LIVE_TRADING_ENABLED")),
        alpaca_account_id=alpaca_account_id,
    )
```

Create `market_sentinel/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum


class InstrumentType(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    OPTION = "option"
    FUTURE = "future"
    COMMODITY = "commodity"
    CRYPTO = "crypto"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"
    SHORT = "short"
    COVER = "cover"


class DecisionStatus(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True)
class Quote:
    symbol: str
    market: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class Bar:
    symbol: str
    market: str
    close: Decimal
    high: Decimal
    low: Decimal
    volume: int
    timestamp: datetime


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    market: str
    instrument_type: InstrumentType
    side: Side
    quantity: Decimal
    limit_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    strategy_id: str

    def has_protection(self) -> bool:
        return self.stop_loss is not None and self.take_profit is not None


@dataclass(frozen=True)
class OrderRequest:
    intent: OrderIntent
    broker: str
    account_id: str
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    commission: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class Position:
    symbol: str
    market: str
    quantity: Decimal
    average_price: Decimal


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    cash: Decimal
    equity: Decimal
    daily_pnl: Decimal = Decimal("0")
    weekly_pnl: Decimal = Decimal("0")
    monthly_pnl: Decimal = Decimal("0")


@dataclass(frozen=True)
class Decision:
    status: DecisionStatus
    reasons: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.status == DecisionStatus.ALLOW

    @classmethod
    def allow(cls) -> "Decision":
        return cls(DecisionStatus.ALLOW, ())

    @classmethod
    def block(cls, *reasons: str) -> "Decision":
        return cls(DecisionStatus.BLOCK, tuple(reasons))


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    message: str
    severity: str = "info"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Run config and model tests to verify they pass**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_config_and_models -v
```

Expected: PASS with `Ran 3 tests`.

- [ ] **Step 5: Commit config and models**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel tests
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add runtime config and shared models'
```

Expected: commit succeeds.

---

### Task 3: Market Data, Features, Prediction, And Strategy

**Files:**
- Create: `market_sentinel/market_data.py`
- Create: `market_sentinel/features.py`
- Create: `market_sentinel/prediction.py`
- Create: `market_sentinel/strategy.py`
- Test: `tests/test_research_agents.py`

- [ ] **Step 1: Write failing research-agent tests**

Create `tests/test_research_agents.py`:

```python
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from market_sentinel.features import FeatureStore
from market_sentinel.market_data import MarketDataAgent
from market_sentinel.models import Bar, Quote
from market_sentinel.prediction import MLPredictionAgent
from market_sentinel.strategy import StrategyAgent


class ResearchAgentsTest(unittest.TestCase):
    def test_market_data_blocks_stale_quote(self):
        agent = MarketDataAgent(max_age_seconds=15)
        quote = Quote(
            symbol="SPY",
            market="US",
            bid=Decimal("499"),
            ask=Decimal("500"),
            last=Decimal("499.5"),
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=30),
        )

        decision = agent.validate_quote(quote, now=datetime.now(timezone.utc))

        self.assertFalse(decision.allowed)
        self.assertIn("quote is stale", decision.reasons)

    def test_features_use_only_prior_bars_for_momentum(self):
        bars = [
            Bar("SPY", "US", Decimal("100"), Decimal("101"), Decimal("99"), 1000, datetime(2026, 1, 1, tzinfo=timezone.utc)),
            Bar("SPY", "US", Decimal("103"), Decimal("104"), Decimal("102"), 1100, datetime(2026, 1, 2, tzinfo=timezone.utc)),
            Bar("SPY", "US", Decimal("150"), Decimal("151"), Decimal("149"), 1200, datetime(2026, 1, 3, tzinfo=timezone.utc)),
        ]

        features = FeatureStore(window=2).for_next_bar(bars)

        self.assertEqual(features["last_close"], Decimal("103"))
        self.assertEqual(features["momentum"], Decimal("0.03"))

    def test_strategy_emits_protected_signal(self):
        bars = [
            Bar("SPY", "US", Decimal("100"), Decimal("101"), Decimal("99"), 1000, datetime(2026, 1, 1, tzinfo=timezone.utc)),
            Bar("SPY", "US", Decimal("103"), Decimal("104"), Decimal("102"), 1100, datetime(2026, 1, 2, tzinfo=timezone.utc)),
        ]
        features = FeatureStore(window=2).for_next_bar(bars)
        prediction = MLPredictionAgent(min_score=Decimal("0.55")).score(features)

        intents = StrategyAgent(strategy_id="momentum-long").generate("SPY", "US", features, prediction)

        self.assertEqual(len(intents), 1)
        self.assertTrue(intents[0].has_protection())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_research_agents -v
```

Expected: FAIL with import errors for research modules.

- [ ] **Step 3: Add research-agent implementation**

Create `market_sentinel/market_data.py`:

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from market_sentinel.models import Decision, Quote


class MarketDataAgent:
    def __init__(self, max_age_seconds: int = 10):
        self.max_age_seconds = max_age_seconds

    def validate_quote(self, quote: Quote, *, now: datetime) -> Decision:
        reasons: list[str] = []
        if not quote.symbol or not quote.market:
            reasons.append("quote identity is missing")
        if quote.bid <= Decimal("0") or quote.ask <= Decimal("0") or quote.last <= Decimal("0"):
            reasons.append("quote price is non-positive")
        if quote.bid > quote.ask:
            reasons.append("quote bid exceeds ask")
        if (now - quote.timestamp).total_seconds() > self.max_age_seconds:
            reasons.append("quote is stale")
        if reasons:
            return Decision.block(*reasons)
        return Decision.allow()
```

Create `market_sentinel/features.py`:

```python
from __future__ import annotations

from decimal import Decimal

from market_sentinel.models import Bar


class FeatureStore:
    def __init__(self, window: int = 5):
        if window < 2:
            raise ValueError("window must be at least 2")
        self.window = window

    def for_next_bar(self, bars: list[Bar]) -> dict[str, Decimal]:
        if len(bars) < self.window:
            raise ValueError("not enough prior bars")
        prior = bars[-self.window :]
        first_close = prior[0].close
        last_close = prior[-1].close
        momentum = (last_close - first_close) / first_close
        average_volume = Decimal(sum(bar.volume for bar in prior)) / Decimal(len(prior))
        return {
            "last_close": last_close,
            "momentum": momentum.quantize(Decimal("0.0001")).normalize(),
            "average_volume": average_volume,
        }
```

Create `market_sentinel/prediction.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Prediction:
    score: Decimal
    passed: bool


class MLPredictionAgent:
    def __init__(self, min_score: Decimal = Decimal("0.55")):
        self.min_score = min_score

    def score(self, features: dict[str, Decimal]) -> Prediction:
        momentum = features.get("momentum", Decimal("0"))
        raw_score = Decimal("0.50") + (momentum * Decimal("2"))
        bounded = max(Decimal("0"), min(Decimal("1"), raw_score))
        return Prediction(score=bounded, passed=bounded >= self.min_score)
```

Create `market_sentinel/strategy.py`:

```python
from __future__ import annotations

from decimal import Decimal

from market_sentinel.models import InstrumentType, OrderIntent, Side
from market_sentinel.prediction import Prediction


class StrategyAgent:
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id

    def generate(
        self,
        symbol: str,
        market: str,
        features: dict[str, Decimal],
        prediction: Prediction,
    ) -> list[OrderIntent]:
        if not prediction.passed:
            return []
        if features.get("momentum", Decimal("0")) <= Decimal("0"):
            return []

        limit_price = features["last_close"]
        return [
            OrderIntent(
                symbol=symbol,
                market=market,
                instrument_type=InstrumentType.ETF if symbol in {"SPY", "NIFTYBEES"} else InstrumentType.EQUITY,
                side=Side.BUY,
                quantity=Decimal("1"),
                limit_price=limit_price,
                stop_loss=(limit_price * Decimal("0.98")).quantize(Decimal("0.01")),
                take_profit=(limit_price * Decimal("1.03")).quantize(Decimal("0.01")),
                strategy_id=self.strategy_id,
            )
        ]
```

- [ ] **Step 4: Run research-agent tests to verify they pass**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_research_agents -v
```

Expected: PASS with `Ran 3 tests`.

- [ ] **Step 5: Commit research agents**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel tests
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add market research agents'
```

Expected: commit succeeds.

---

### Task 4: ML Training, Model Updates, And Scheduled Intents

**Files:**
- Create: `market_sentinel/model_training.py`
- Create: `market_sentinel/model_store.py`
- Create: `market_sentinel/scheduler.py`
- Test: `tests/test_ml_training_and_scheduling.py`

- [ ] **Step 1: Write failing ML and scheduling tests**

Create `tests/test_ml_training_and_scheduling.py`:

```python
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from market_sentinel.model_store import ModelStore
from market_sentinel.model_training import TrainingExample, train_linear_model
from market_sentinel.models import InstrumentType, OrderIntent, Side
from market_sentinel.scheduler import ScheduledOrderBook, ScheduledOrderIntent, ScheduledOrderStatus


def protected_intent():
    return OrderIntent(
        symbol="SPY",
        market="US",
        instrument_type=InstrumentType.ETF,
        side=Side.BUY,
        quantity=Decimal("1"),
        limit_price=Decimal("500"),
        stop_loss=Decimal("490"),
        take_profit=Decimal("515"),
        strategy_id="momentum-long",
    )


class MLTrainingAndSchedulingTest(unittest.TestCase):
    def test_training_produces_model_that_scores_positive_example(self):
        examples = [
            TrainingExample({"momentum": Decimal("0.04"), "average_volume": Decimal("1000")}, 1),
            TrainingExample({"momentum": Decimal("-0.03"), "average_volume": Decimal("900")}, 0),
            TrainingExample({"momentum": Decimal("0.02"), "average_volume": Decimal("1100")}, 1),
        ]

        model = train_linear_model(examples, epochs=12)

        self.assertEqual(model.training_rows, 3)
        self.assertIn("momentum", model.feature_names)
        self.assertGreater(model.predict_score({"momentum": Decimal("0.04"), "average_volume": Decimal("1000")}), Decimal("0.5"))

    def test_model_store_round_trips_active_model(self):
        model = train_linear_model([
            TrainingExample({"momentum": Decimal("0.04")}, 1),
            TrainingExample({"momentum": Decimal("-0.03")}, 0),
        ])

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ModelStore(Path(temp_dir))
            store.save(model)
            store.activate(model.version)
            loaded = store.load_active()

        self.assertEqual(loaded.version, model.version)
        self.assertEqual(loaded.feature_names, model.feature_names)

    def test_scheduler_returns_only_eligible_unexpired_intents(self):
        now = datetime(2026, 7, 5, 10, 0, tzinfo=timezone.utc)
        book = ScheduledOrderBook()
        future = ScheduledOrderIntent(
            id="future",
            intent=protected_intent(),
            eligible_at=now + timedelta(minutes=5),
            expires_at=now + timedelta(minutes=30),
            reason="wait for open",
        )
        due = ScheduledOrderIntent(
            id="due",
            intent=protected_intent(),
            eligible_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(minutes=30),
            reason="scheduled model signal",
            model_version="model-1",
        )
        expired = ScheduledOrderIntent(
            id="expired",
            intent=protected_intent(),
            eligible_at=now - timedelta(minutes=30),
            expires_at=now - timedelta(minutes=1),
            reason="old signal",
        )

        book.add(future)
        book.add(due)
        book.add(expired)
        due_items = book.due_intents(now)

        self.assertEqual([item.id for item in due_items], ["due"])
        self.assertEqual(book.get("future").status, ScheduledOrderStatus.PENDING)
        self.assertEqual(book.get("due").status, ScheduledOrderStatus.ELIGIBLE)
        self.assertEqual(book.get("expired").status, ScheduledOrderStatus.EXPIRED)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_training_and_scheduling -v
```

Expected: FAIL with import errors for model and scheduler modules.

- [ ] **Step 3: Add ML training and model store implementation**

Create `market_sentinel/model_training.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class TrainingExample:
    features: dict[str, Decimal]
    label: int


@dataclass(frozen=True)
class LinearModel:
    version: str
    feature_names: tuple[str, ...]
    weights: dict[str, Decimal]
    bias: Decimal
    training_rows: int
    accuracy: Decimal
    created_at: str

    def predict_score(self, features: dict[str, Decimal]) -> Decimal:
        linear = self.bias
        for name in self.feature_names:
            linear += self.weights.get(name, Decimal("0")) * features.get(name, Decimal("0"))
        score = Decimal("0.5") + linear
        bounded = max(Decimal("0"), min(Decimal("1"), score))
        return bounded.quantize(Decimal("0.0001"))

    def to_payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "feature_names": list(self.feature_names),
            "weights": {name: str(value) for name, value in self.weights.items()},
            "bias": str(self.bias),
            "training_rows": self.training_rows,
            "accuracy": str(self.accuracy),
            "created_at": self.created_at,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "LinearModel":
        weights_payload = payload["weights"]
        if not isinstance(weights_payload, dict):
            raise ValueError("weights payload must be an object")
        return cls(
            version=str(payload["version"]),
            feature_names=tuple(str(item) for item in payload["feature_names"]),
            weights={str(name): Decimal(str(value)) for name, value in weights_payload.items()},
            bias=Decimal(str(payload["bias"])),
            training_rows=int(payload["training_rows"]),
            accuracy=Decimal(str(payload["accuracy"])),
            created_at=str(payload["created_at"]),
        )


def _linear_score(weights: dict[str, Decimal], bias: Decimal, feature_names: tuple[str, ...], features: dict[str, Decimal]) -> Decimal:
    score = bias
    for name in feature_names:
        score += weights[name] * features.get(name, Decimal("0"))
    return score


def train_linear_model(examples: list[TrainingExample], *, epochs: int = 10, learning_rate: Decimal = Decimal("0.1")) -> LinearModel:
    if not examples:
        raise ValueError("at least one training example is required")
    feature_names = tuple(sorted({name for example in examples for name in example.features}))
    weights = {name: Decimal("0") for name in feature_names}
    bias = Decimal("0")

    for _ in range(epochs):
        for example in examples:
            predicted = 1 if _linear_score(weights, bias, feature_names, example.features) >= 0 else 0
            error = Decimal(example.label - predicted)
            bias += learning_rate * error
            for name in feature_names:
                weights[name] += learning_rate * error * example.features.get(name, Decimal("0"))

    correct = 0
    for example in examples:
        predicted_score = Decimal("0.5") + _linear_score(weights, bias, feature_names, example.features)
        predicted = 1 if predicted_score >= Decimal("0.5") else 0
        if predicted == example.label:
            correct += 1
    accuracy = (Decimal(correct) / Decimal(len(examples))).quantize(Decimal("0.0001"))
    created = datetime.now(timezone.utc)
    return LinearModel(
        version=f"model-{created.strftime('%Y%m%d%H%M%S%f')}",
        feature_names=feature_names,
        weights=weights,
        bias=bias,
        training_rows=len(examples),
        accuracy=accuracy,
        created_at=created.isoformat(),
    )
```

Create `market_sentinel/model_store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from market_sentinel.model_training import LinearModel


class ModelStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.active_path = self.root / "active_model.txt"

    def save(self, model: LinearModel) -> Path:
        path = self.root / f"{model.version}.json"
        path.write_text(json.dumps(model.to_payload(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def activate(self, version: str) -> None:
        path = self.root / f"{version}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        self.active_path.write_text(version, encoding="utf-8")

    def load(self, version: str) -> LinearModel:
        payload = json.loads((self.root / f"{version}.json").read_text(encoding="utf-8"))
        return LinearModel.from_payload(payload)

    def load_active(self) -> LinearModel:
        version = self.active_path.read_text(encoding="utf-8").strip()
        return self.load(version)
```

- [ ] **Step 4: Add scheduled order implementation**

Create `market_sentinel/scheduler.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from market_sentinel.models import OrderIntent


class ScheduledOrderStatus(StrEnum):
    PENDING = "pending"
    ELIGIBLE = "eligible"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"


@dataclass
class ScheduledOrderIntent:
    id: str
    intent: OrderIntent
    eligible_at: datetime
    expires_at: datetime
    reason: str
    model_version: str | None = None
    status: ScheduledOrderStatus = ScheduledOrderStatus.PENDING
    block_reason: str | None = None


class ScheduledOrderBook:
    def __init__(self):
        self._items: dict[str, ScheduledOrderIntent] = {}

    def add(self, scheduled: ScheduledOrderIntent) -> None:
        self._items[scheduled.id] = scheduled

    def get(self, scheduled_id: str) -> ScheduledOrderIntent:
        return self._items[scheduled_id]

    def due_intents(self, now: datetime) -> list[ScheduledOrderIntent]:
        due: list[ScheduledOrderIntent] = []
        for scheduled in self._items.values():
            if scheduled.status != ScheduledOrderStatus.PENDING:
                continue
            if now > scheduled.expires_at:
                scheduled.status = ScheduledOrderStatus.EXPIRED
                continue
            if now >= scheduled.eligible_at:
                scheduled.status = ScheduledOrderStatus.ELIGIBLE
                due.append(scheduled)
        return due

    def mark_blocked(self, scheduled_id: str, reason: str) -> None:
        scheduled = self.get(scheduled_id)
        scheduled.status = ScheduledOrderStatus.BLOCKED
        scheduled.block_reason = reason
```

- [ ] **Step 5: Run ML and scheduling tests to verify they pass**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_training_and_scheduling -v
```

Expected: PASS with `Ran 3 tests`.

- [ ] **Step 6: Commit ML training and scheduling**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel tests
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add model training and scheduled intents'
```

Expected: commit succeeds.

---

### Task 5: Risk And Compliance Gates

**Files:**
- Create: `market_sentinel/risk.py`
- Create: `market_sentinel/compliance.py`
- Test: `tests/test_risk_and_compliance.py`

- [ ] **Step 1: Write failing risk and compliance tests**

Create `tests/test_risk_and_compliance.py`:

```python
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from market_sentinel.compliance import ComplianceGuard
from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.models import AccountSnapshot, InstrumentType, OrderIntent, Position, Side
from market_sentinel.risk import RiskAgent


def protected_intent(symbol="SPY", market="US"):
    return OrderIntent(
        symbol=symbol,
        market=market,
        instrument_type=InstrumentType.ETF,
        side=Side.BUY,
        quantity=Decimal("1"),
        limit_price=Decimal("500"),
        stop_loss=Decimal("490"),
        take_profit=Decimal("515"),
        strategy_id="momentum-long",
    )


class RiskAndComplianceTest(unittest.TestCase):
    def test_risk_blocks_unprotected_intent(self):
        intent = protected_intent()
        unprotected = OrderIntent(
            symbol=intent.symbol,
            market=intent.market,
            instrument_type=intent.instrument_type,
            side=intent.side,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            stop_loss=None,
            take_profit=intent.take_profit,
            strategy_id=intent.strategy_id,
        )

        decision = RiskAgent(Settings()).evaluate(
            unprotected,
            AccountSnapshot("paper-local", Decimal("100000"), Decimal("100000")),
            [],
        )

        self.assertFalse(decision.allowed)
        self.assertIn("missing stop-loss or take-profit", decision.reasons)

    def test_risk_blocks_total_position_cap(self):
        positions = [
            Position(f"S{i}", "US", Decimal("1"), Decimal("10"))
            for i in range(6)
        ]

        decision = RiskAgent(Settings()).evaluate(
            protected_intent("AAPL"),
            AccountSnapshot("paper-local", Decimal("100000"), Decimal("100000")),
            positions,
        )

        self.assertFalse(decision.allowed)
        self.assertIn("total position cap reached", decision.reasons)

    def test_compliance_blocks_india_live_without_algo_id(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            groww_algo_id=None,
        )

        decision = ComplianceGuard(settings).evaluate(
            protected_intent("NIFTYBEES", "IN"),
            broker="groww",
            now=datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
        )

        self.assertFalse(decision.allowed)
        self.assertIn("Groww algo id is missing", decision.reasons)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_risk_and_compliance -v
```

Expected: FAIL with import errors for `risk` and `compliance`.

- [ ] **Step 3: Add risk and compliance implementation**

Create `market_sentinel/risk.py`:

```python
from __future__ import annotations

from decimal import Decimal

from market_sentinel.config import Settings
from market_sentinel.models import AccountSnapshot, Decision, InstrumentType, OrderIntent, Position, Side


DERIVATIVE_TYPES = {
    InstrumentType.OPTION,
    InstrumentType.FUTURE,
    InstrumentType.COMMODITY,
    InstrumentType.CRYPTO,
}


class RiskAgent:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
        positions: list[Position],
    ) -> Decision:
        reasons: list[str] = []
        if not intent.has_protection():
            reasons.append("missing stop-loss or take-profit")
        if intent.side == Side.SHORT:
            reasons.append("unsupported shorting")
        if intent.instrument_type == InstrumentType.OPTION and intent.side == Side.SELL:
            reasons.append("naked options are not supported")
        if len(positions) >= self.settings.max_positions_total:
            reasons.append("total position cap reached")
        market_positions = [position for position in positions if position.market == intent.market]
        if len(market_positions) >= self.settings.max_positions_per_market:
            reasons.append("market position cap reached")
        if account.daily_pnl <= -(account.equity * self.settings.daily_loss_stop):
            reasons.append("daily loss stop reached")

        risk_fraction = (
            self.settings.derivative_risk_per_trade
            if intent.instrument_type in DERIVATIVE_TYPES
            else self.settings.cash_etf_risk_per_trade
        )
        max_loss = account.equity * risk_fraction
        if intent.stop_loss is not None:
            estimated_loss = abs(intent.limit_price - intent.stop_loss) * intent.quantity
            if estimated_loss > max_loss:
                reasons.append("per-trade risk budget exceeded")

        if reasons:
            return Decision.block(*reasons)
        return Decision.allow()
```

Create `market_sentinel/compliance.py`:

```python
from __future__ import annotations

from datetime import datetime

from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.models import Decision, OrderIntent


class ComplianceGuard:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(self, intent: OrderIntent, *, broker: str, now: datetime) -> Decision:
        reasons: list[str] = []
        if self.settings.mode in {RuntimeMode.DISABLED, RuntimeMode.EMERGENCY}:
            reasons.append(f"mode blocks new orders: {self.settings.mode.value}")
        if self.settings.mode == RuntimeMode.BACKTEST:
            reasons.append("backtest mode cannot submit broker orders")
        if self.settings.account_id not in self.settings.account_allowlist:
            reasons.append("account is not allowlisted")
        if not intent.has_protection():
            reasons.append("missing stop-loss or take-profit")
        if broker == "groww" and self.settings.mode == RuntimeMode.LIVE_SMALL:
            if intent.market != "IN":
                reasons.append("Groww live-small is limited to India market")
            if not self.settings.india_live_trading_enabled:
                reasons.append("India live trading flag is disabled")
            if not self.settings.india_algo_compliance_verified:
                reasons.append("India algo compliance is not verified")
            if not self.settings.groww_algo_id:
                reasons.append("Groww algo id is missing")
        if broker == "alpaca" and self.settings.mode == RuntimeMode.LIVE_SMALL:
            if intent.market != "US":
                reasons.append("Alpaca live-small is limited to US market")
            if not self.settings.alpaca_live_trading_enabled:
                reasons.append("Alpaca live trading flag is disabled")
            if not self.settings.alpaca_account_id:
                reasons.append("Alpaca account id is missing")
        if now.tzinfo is None:
            reasons.append("timestamp must be timezone-aware")
        if reasons:
            return Decision.block(*reasons)
        return Decision.allow()
```

- [ ] **Step 4: Run risk and compliance tests to verify they pass**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_risk_and_compliance -v
```

Expected: PASS with `Ran 3 tests`.

- [ ] **Step 5: Commit risk and compliance gates**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel tests
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add risk and compliance gates'
```

Expected: commit succeeds.

---

### Task 6: Broker Adapters And Execution Boundary

**Files:**
- Create: `market_sentinel/brokers.py`
- Create: `market_sentinel/execution.py`
- Test: `tests/test_brokers_and_execution.py`

- [ ] **Step 1: Write failing broker and execution tests**

Create `tests/test_brokers_and_execution.py`:

```python
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from market_sentinel.brokers import AlpacaBrokerAdapter, BrokerReject, GrowwBrokerAdapter, MockBrokerAdapter
from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.execution import ExecutionAgent
from market_sentinel.models import AccountSnapshot, InstrumentType, OrderIntent, Position, Side


def intent():
    return OrderIntent(
        symbol="SPY",
        market="US",
        instrument_type=InstrumentType.ETF,
        side=Side.BUY,
        quantity=Decimal("1"),
        limit_price=Decimal("500"),
        stop_loss=Decimal("490"),
        take_profit=Decimal("515"),
        strategy_id="momentum-long",
    )


class BrokerExecutionTest(unittest.TestCase):
    def test_mock_broker_returns_fill(self):
        fill = MockBrokerAdapter().place_order(intent())

        self.assertEqual(fill.symbol, "SPY")
        self.assertEqual(fill.price, Decimal("500"))

    def test_groww_live_blocks_without_compliance_flags(self):
        broker = GrowwBrokerAdapter(Settings(mode=RuntimeMode.LIVE_SMALL))

        with self.assertRaises(BrokerReject):
            broker.place_order(intent())

    def test_execution_agent_blocks_before_broker_call(self):
        class ExplodingBroker:
            name = "alpaca"

            def place_order(self, order_intent):
                raise AssertionError("broker should not be called")

        agent = ExecutionAgent(Settings(mode=RuntimeMode.DISABLED), ExplodingBroker())
        result = agent.submit(
            intent(),
            AccountSnapshot("paper-local", Decimal("100000"), Decimal("100000")),
            [],
            now=datetime.now(timezone.utc),
        )

        self.assertFalse(result.allowed)
        self.assertIn("mode blocks new orders: disabled", result.reasons)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_brokers_and_execution -v
```

Expected: FAIL with import errors for broker and execution modules.

- [ ] **Step 3: Add broker and execution implementation**

Create `market_sentinel/brokers.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol

from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.models import Fill, OrderIntent


class BrokerReject(RuntimeError):
    pass


class BrokerAdapter(Protocol):
    name: str

    def place_order(self, order_intent: OrderIntent) -> Fill:
        ...


class MockBrokerAdapter:
    name = "mock"

    def place_order(self, order_intent: OrderIntent) -> Fill:
        return Fill(
            symbol=order_intent.symbol,
            side=order_intent.side,
            quantity=order_intent.quantity,
            price=order_intent.limit_price,
            commission=Decimal("0"),
            timestamp=datetime.now(timezone.utc),
        )


class GrowwBrokerAdapter:
    name = "groww"

    def __init__(self, settings: Settings):
        self.settings = settings

    def place_order(self, order_intent: OrderIntent) -> Fill:
        if self.settings.mode != RuntimeMode.PAPER:
            if not (
                self.settings.mode == RuntimeMode.LIVE_SMALL
                and self.settings.india_live_trading_enabled
                and self.settings.india_algo_compliance_verified
                and self.settings.groww_algo_id
            ):
                raise BrokerReject("Groww live order blocked by adapter gate")
        return MockBrokerAdapter().place_order(order_intent)


class AlpacaBrokerAdapter:
    name = "alpaca"

    def __init__(self, settings: Settings):
        self.settings = settings

    def place_order(self, order_intent: OrderIntent) -> Fill:
        if self.settings.mode == RuntimeMode.PAPER and self.settings.alpaca_paper_trading_enabled:
            return MockBrokerAdapter().place_order(order_intent)
        if not (
            self.settings.mode == RuntimeMode.LIVE_SMALL
            and self.settings.alpaca_live_trading_enabled
            and self.settings.alpaca_account_id
        ):
            raise BrokerReject("Alpaca live order blocked by adapter gate")
        return MockBrokerAdapter().place_order(order_intent)
```

Create `market_sentinel/execution.py`:

```python
from __future__ import annotations

from datetime import datetime

from market_sentinel.brokers import BrokerAdapter
from market_sentinel.compliance import ComplianceGuard
from market_sentinel.config import Settings
from market_sentinel.models import AccountSnapshot, Decision, OrderIntent, Position
from market_sentinel.risk import RiskAgent


class ExecutionAgent:
    def __init__(self, settings: Settings, broker: BrokerAdapter):
        self.settings = settings
        self.broker = broker

    def submit(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
        positions: list[Position],
        *,
        now: datetime,
    ) -> Decision:
        risk_decision = RiskAgent(self.settings).evaluate(intent, account, positions)
        if not risk_decision.allowed:
            return risk_decision

        compliance_decision = ComplianceGuard(self.settings).evaluate(
            intent,
            broker=self.broker.name,
            now=now,
        )
        if not compliance_decision.allowed:
            return compliance_decision

        self.broker.place_order(intent)
        return Decision.allow()
```

- [ ] **Step 4: Run broker and execution tests to verify they pass**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_brokers_and_execution -v
```

Expected: PASS with `Ran 3 tests`.

- [ ] **Step 5: Commit broker and execution boundary**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel tests
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add broker adapters and execution boundary'
```

Expected: commit succeeds.

---

### Task 7: Portfolio, Analysis, Audit, RUFLO, And CLI

**Files:**
- Create: `market_sentinel/portfolio.py`
- Create: `market_sentinel/analysis.py`
- Create: `market_sentinel/audit.py`
- Create: `market_sentinel/ruflo.py`
- Create: `market_sentinel/cli.py`
- Test: `tests/test_operations.py`

- [ ] **Step 1: Write failing operations tests**

Create `tests/test_operations.py`:

```python
import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from market_sentinel.analysis import AnalysisAgent
from market_sentinel.audit import AuditLog
from market_sentinel.cli import _export_dashboard
from market_sentinel.models import AuditEvent, Fill, Side
from market_sentinel.portfolio import PortfolioAgent
from market_sentinel.ruflo import RUFLOAgent


class OperationsTest(unittest.TestCase):
    def test_portfolio_applies_buy_fill(self):
        portfolio = PortfolioAgent(cash=Decimal("1000"))
        portfolio.apply_fill(Fill("SPY", Side.BUY, Decimal("1"), Decimal("500"), Decimal("1"), datetime.now(timezone.utc)))

        snapshot = portfolio.snapshot("paper-local")

        self.assertEqual(snapshot.cash, Decimal("499"))
        self.assertEqual(snapshot.equity, Decimal("999"))

    def test_audit_log_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit.jsonl"
            log = AuditLog(path)
            log.append(AuditEvent("risk.block", "blocked for test", "warning", details={"reason": "cap"}))

            events = log.read_latest(limit=1)

        self.assertEqual(events[0]["event_type"], "risk.block")
        self.assertEqual(events[0]["details"]["reason"], "cap")

    def test_analysis_reports_drawdown(self):
        summary = AnalysisAgent().summarize_equity([Decimal("100"), Decimal("110"), Decimal("90")])

        self.assertEqual(summary["max_drawdown"], Decimal("0.1818"))

    def test_ruflo_has_no_order_authority(self):
        report = RUFLOAgent().checklist_status()

        self.assertFalse(report["can_place_orders"])

    def test_dashboard_export_includes_model_and_scheduled_orders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.json"
            _export_dashboard(path)
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["model"]["mode"], "advisory")
        self.assertEqual(data["scheduled_orders"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_operations -v
```

Expected: FAIL with import errors for operations modules.

- [ ] **Step 3: Add operations implementation**

Create `market_sentinel/portfolio.py`:

```python
from __future__ import annotations

from decimal import Decimal

from market_sentinel.models import AccountSnapshot, Fill, Position, Side


class PortfolioAgent:
    def __init__(self, cash: Decimal):
        self.cash = cash
        self.positions: dict[str, Position] = {}

    def apply_fill(self, fill: Fill) -> None:
        total_cost = (fill.quantity * fill.price) + fill.commission
        if fill.side == Side.BUY:
            self.cash -= total_cost
            current = self.positions.get(fill.symbol)
            if current is None:
                self.positions[fill.symbol] = Position(fill.symbol, "US", fill.quantity, fill.price)
            else:
                total_quantity = current.quantity + fill.quantity
                average = ((current.quantity * current.average_price) + (fill.quantity * fill.price)) / total_quantity
                self.positions[fill.symbol] = Position(current.symbol, current.market, total_quantity, average)
        elif fill.side == Side.SELL:
            self.cash += (fill.quantity * fill.price) - fill.commission

    def snapshot(self, account_id: str) -> AccountSnapshot:
        position_value = sum(position.quantity * position.average_price for position in self.positions.values())
        return AccountSnapshot(account_id=account_id, cash=self.cash, equity=self.cash + position_value)
```

Create `market_sentinel/analysis.py`:

```python
from __future__ import annotations

from decimal import Decimal


class AnalysisAgent:
    def summarize_equity(self, equity_curve: list[Decimal]) -> dict[str, Decimal]:
        if not equity_curve:
            return {"start": Decimal("0"), "end": Decimal("0"), "return": Decimal("0"), "max_drawdown": Decimal("0")}
        peak = equity_curve[0]
        max_drawdown = Decimal("0")
        for value in equity_curve:
            peak = max(peak, value)
            if peak > 0:
                drawdown = (peak - value) / peak
                max_drawdown = max(max_drawdown, drawdown)
        start = equity_curve[0]
        end = equity_curve[-1]
        total_return = Decimal("0") if start == 0 else (end - start) / start
        return {
            "start": start,
            "end": end,
            "return": total_return.quantize(Decimal("0.0001")),
            "max_drawdown": max_drawdown.quantize(Decimal("0.0001")),
        }
```

Create `market_sentinel/audit.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from market_sentinel.models import AuditEvent


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), default=_json_default, sort_keys=True) + "\n")

    def read_latest(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:]]
```

Create `market_sentinel/ruflo.py`:

```python
from __future__ import annotations


class RUFLOAgent:
    def checklist_status(self) -> dict[str, object]:
        return {
            "can_place_orders": False,
            "role": "coordination-only",
            "checks": [
                "dependency license review",
                "Groww permissions and India algo obligations",
                "Alpaca account and endpoint separation",
                "four-week paper gate",
            ],
        }
```

Create `market_sentinel/cli.py`:

```python
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from market_sentinel.analysis import AnalysisAgent
from market_sentinel.config import load_settings
from market_sentinel.ruflo import RUFLOAgent


def _status() -> dict[str, object]:
    settings = load_settings()
    return {
        "mode": settings.mode.value,
        "account_id": settings.account_id,
        "live_small_blocked_by_default": settings.mode.value != "live-small",
        "ruflo": RUFLOAgent().checklist_status(),
    }


def _export_dashboard(path: Path) -> None:
    data = {
        "status": _status(),
        "model": {
            "mode": "advisory",
            "active_version": "untrained-baseline",
            "last_trained_at": None,
            "accuracy": None,
            "feature_set": ["momentum", "average_volume"],
            "can_place_orders": False,
        },
        "scheduled_orders": [
            {
                "id": "paper-open-check",
                "symbol": "SPY",
                "market": "US",
                "eligible_at": "2026-07-06T13:30:00+00:00",
                "expires_at": "2026-07-06T20:00:00+00:00",
                "status": "pending",
                "model_version": "untrained-baseline",
                "gate": "must pass fresh risk and compliance checks",
            }
        ],
        "equity_summary": {
            key: str(value)
            for key, value in AnalysisAgent().summarize_equity([Decimal("100000"), Decimal("100500"), Decimal("100100")]).items()
        },
        "validation_gates": [
            {"name": "Unit tests", "state": "ready"},
            {"name": "Four-week paper gate", "state": "not-started"},
            {"name": "Live-small compliance", "state": "blocked"},
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="market-sentinel")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    export_parser = subcommands.add_parser("export-dashboard")
    export_parser.add_argument("--path", default="apps/control-center/public/status.json")
    args = parser.parse_args(argv)

    if args.command == "status":
        print(json.dumps(_status(), indent=2, sort_keys=True))
        return 0
    if args.command == "export-dashboard":
        _export_dashboard(Path(args.path))
        return 0
    return 2
```

- [ ] **Step 4: Run operations tests to verify they pass**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_operations -v
```

Expected: PASS with `Ran 5 tests`.

- [ ] **Step 5: Run all Python tests**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
```

Expected: PASS for all tests created so far.

- [ ] **Step 6: Commit operations modules**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel tests
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add operations and dashboard export'
```

Expected: commit succeeds.

---

### Task 8: Sites Control Center

**Files:**
- Create directory from starter: `apps/control-center/`
- Modify: `apps/control-center/package.json`
- Modify: `apps/control-center/app/layout.tsx`
- Modify: `apps/control-center/app/page.tsx`
- Modify: `apps/control-center/app/globals.css`
- Create: `apps/control-center/public/status.json`

- [ ] **Step 1: Copy the Sites starter**

Run:

```powershell
Copy-Item -Recurse -Force 'C:\Users\Dell\.codex\plugins\cache\openai-bundled\sites\0.1.21\skills\sites-building\templates\vinext-starter' 'apps\control-center'
```

Expected: `apps/control-center/package.json` exists.

- [ ] **Step 2: Generate the dashboard fixture**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli export-dashboard --path apps/control-center/public/status.json
```

Expected: `apps/control-center/public/status.json` contains status, equity summary, and validation gates.

- [ ] **Step 3: Update package metadata**

Replace `apps/control-center/package.json` `name` value with:

```json
"name": "market-sentinel-control-center"
```

Keep the starter scripts and dependencies unchanged.

- [ ] **Step 4: Update layout metadata**

Replace `apps/control-center/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Market Sentinel Control Center",
  description: "Safe-by-default trading scaffold operations dashboard.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Replace the dashboard page**

Replace `apps/control-center/app/page.tsx` with:

```tsx
import statusData from "../public/status.json";

type Gate = {
  name: string;
  state: string;
};

function StatePill({ state }: { state: string }) {
  const tone =
    state === "ready"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : state === "blocked"
        ? "bg-rose-50 text-rose-700 ring-rose-200"
        : "bg-amber-50 text-amber-800 ring-amber-200";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${tone}`}>
      {state}
    </span>
  );
}

export default function Home() {
  const data = statusData as {
    status: {
      mode: string;
      account_id: string;
      live_small_blocked_by_default: boolean;
      ruflo: {
        role: string;
        can_place_orders: boolean;
        checks: string[];
      };
    };
    model: {
      mode: string;
      active_version: string;
      last_trained_at: string | null;
      accuracy: string | null;
      feature_set: string[];
      can_place_orders: boolean;
    };
    scheduled_orders: Array<{
      id: string;
      symbol: string;
      market: string;
      eligible_at: string;
      expires_at: string;
      status: string;
      model_version: string;
      gate: string;
    }>;
    equity_summary: Record<string, string>;
    validation_gates: Gate[];
  };

  return (
    <main className="min-h-screen bg-[#f7f8f4] text-[#18201c]">
      <section className="border-b border-[#d8ded2] bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-5 py-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-[#5e6d62]">
              Market Sentinel
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal md:text-4xl">
              Control Center
            </h1>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-5">
            <div className="border border-[#d8ded2] bg-[#f7f8f4] p-3">
              <p className="text-[#5e6d62]">Mode</p>
              <p className="mt-1 font-semibold">{data.status.mode}</p>
            </div>
            <div className="border border-[#d8ded2] bg-[#f7f8f4] p-3">
              <p className="text-[#5e6d62]">Account</p>
              <p className="mt-1 font-semibold">{data.status.account_id}</p>
            </div>
            <div className="border border-[#d8ded2] bg-[#f7f8f4] p-3">
              <p className="text-[#5e6d62]">Live-small</p>
              <p className="mt-1 font-semibold">
                {data.status.live_small_blocked_by_default ? "blocked" : "armed"}
              </p>
            </div>
            <div className="border border-[#d8ded2] bg-[#f7f8f4] p-3">
              <p className="text-[#5e6d62]">RUFLO</p>
              <p className="mt-1 font-semibold">{data.status.ruflo.role}</p>
            </div>
            <div className="border border-[#d8ded2] bg-[#f7f8f4] p-3">
              <p className="text-[#5e6d62]">ML</p>
              <p className="mt-1 font-semibold">{data.model.mode}</p>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto grid max-w-7xl gap-5 px-5 py-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="border border-[#d8ded2] bg-white p-5">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">Validation Gates</h2>
            <StatePill state="blocked" />
          </div>
          <div className="mt-5 divide-y divide-[#e3e7df]">
            {data.validation_gates.map((gate) => (
              <div className="flex items-center justify-between gap-4 py-3" key={gate.name}>
                <span className="font-medium">{gate.name}</span>
                <StatePill state={gate.state} />
              </div>
            ))}
          </div>
        </section>

        <section className="border border-[#d8ded2] bg-white p-5">
          <h2 className="text-xl font-semibold">Equity Summary</h2>
          <dl className="mt-5 grid grid-cols-2 gap-3">
            {Object.entries(data.equity_summary).map(([key, value]) => (
              <div className="border border-[#e3e7df] p-3" key={key}>
                <dt className="text-sm capitalize text-[#5e6d62]">{key.replace("_", " ")}</dt>
                <dd className="mt-1 font-mono text-lg">{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="border border-[#d8ded2] bg-white p-5">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">ML Model</h2>
            <StatePill state={data.model.mode} />
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-3">
            <div className="border border-[#e3e7df] p-3">
              <dt className="text-sm text-[#5e6d62]">Active version</dt>
              <dd className="mt-1 font-mono text-sm">{data.model.active_version}</dd>
            </div>
            <div className="border border-[#e3e7df] p-3">
              <dt className="text-sm text-[#5e6d62]">Accuracy</dt>
              <dd className="mt-1 font-mono text-sm">{data.model.accuracy ?? "not trained"}</dd>
            </div>
            <div className="col-span-2 border border-[#e3e7df] p-3">
              <dt className="text-sm text-[#5e6d62]">Feature set</dt>
              <dd className="mt-1 text-sm font-medium">{data.model.feature_set.join(", ")}</dd>
            </div>
          </dl>
        </section>

        <section className="border border-[#d8ded2] bg-white p-5">
          <h2 className="text-xl font-semibold">Scheduled Intents</h2>
          <div className="mt-5 divide-y divide-[#e3e7df]">
            {data.scheduled_orders.map((order) => (
              <div className="py-3" key={order.id}>
                <div className="flex items-center justify-between gap-4">
                  <p className="font-medium">{order.symbol} / {order.market}</p>
                  <StatePill state={order.status} />
                </div>
                <p className="mt-2 text-sm text-[#5e6d62]">{order.gate}</p>
                <p className="mt-2 font-mono text-xs text-[#5e6d62]">
                  {order.eligible_at} to {order.expires_at}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="border border-[#d8ded2] bg-white p-5 lg:col-span-2">
          <h2 className="text-xl font-semibold">Compliance Checklist</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {data.status.ruflo.checks.map((check) => (
              <div className="border border-[#e3e7df] bg-[#fbfcf8] p-4" key={check}>
                <p className="font-medium">{check}</p>
                <p className="mt-2 text-sm text-[#5e6d62]">
                  Human verification required before live-small trading can be considered.
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
```

- [ ] **Step 6: Replace dashboard CSS**

Replace `apps/control-center/app/globals.css` with:

```css
@import "tailwindcss";

:root {
  --background: #f7f8f4;
  --foreground: #18201c;
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--background);
  color: var(--foreground);
  font-family: Arial, Helvetica, sans-serif;
}
```

- [ ] **Step 7: Install and build the Sites app**

Run:

```powershell
Set-Location apps\control-center
npm ci
npm run build
```

Expected: `npm run build` exits 0 and creates `apps/control-center/dist`.

- [ ] **Step 8: Commit the control center**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add apps/control-center
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add market sentinel control center'
```

Expected: commit succeeds.

---

### Task 9: Operating Docs, Review, And Publish Readiness

**Files:**
- Create: `docs/compliance-checklist.md`
- Create: `docs/operating-guide.md`
- Create: `docs/github-resources.md`
- Modify: `README.md`

- [ ] **Step 1: Add the compliance checklist**

Create `docs/compliance-checklist.md`:

```markdown
# Market Sentinel Compliance Checklist

These gates require human verification before any live-small trading run.

## Broker And Regulatory Gates

- Verify Groww API permissions, order endpoints, and current India algo obligations.
- Verify India live trading has an assigned algo identifier when required.
- Verify Alpaca paper and live endpoint separation.
- Verify Alpaca account type, market-data tier, and trading permissions.

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
```

- [ ] **Step 2: Add the operating guide**

Create `docs/operating-guide.md`:

```markdown
# Market Sentinel Operating Guide

## Default Operation

The default mode is `disabled`. Use `paper` for mock or broker paper workflows. Use `backtest` for historical simulation.

## Commands

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli status
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m market_sentinel.cli export-dashboard --path apps/control-center/public/status.json
```

## Machine Learning

The first ML model is advisory. It can score, rank, or filter strategy signals, but it cannot place orders, override blocked orders, or enable live-small mode. Model updates must produce versioned artifacts and audit events.

## Scheduled Intents

Scheduled order intents are queued candidates. When they become eligible, they must pass fresh market data, risk, compliance, account allowlist, runtime mode, and broker-readiness checks before the execution boundary can submit anything.

## Emergency Mode

Set `MARKET_SENTINEL_MODE=emergency` to block new orders. Future flatten-only behavior must keep new order creation blocked unless the operation is explicitly classified as risk-reducing.

## Live-Small Boundary

Live-small trading is unavailable until broker credentials, account allowlists, explicit live flags, compliance verification, risk gates, and audit paths are configured.
```

- [ ] **Step 3: Add GitHub resource notes**

Create `docs/github-resources.md`:

```markdown
# GitHub Resources

The local workspace is initialized as a git repository. A remote GitHub repository has not been selected.

When a repository target is available:

1. Push the `main` branch.
2. Open a draft pull request.
3. Attach this design spec and implementation plan in the PR description.
4. Run CI and CodeRabbit review.
5. Address review feedback with tests before merging.
```

- [ ] **Step 4: Update README with docs links**

Append to `README.md`:

```markdown
## Documents

- `docs/superpowers/specs/2026-07-05-market-sentinel-design.md`
- `docs/superpowers/plans/2026-07-05-market-sentinel.md`
- `docs/compliance-checklist.md`
- `docs/operating-guide.md`
- `docs/github-resources.md`
```

- [ ] **Step 5: Run full local verification**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
Set-Location apps\control-center
npm run build
```

Expected: Python tests pass and Sites build exits 0.

- [ ] **Step 6: Commit docs and verification updates**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add README.md docs
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'docs: add operating and publishing guidance'
```

Expected: commit succeeds.

- [ ] **Step 7: Run CodeRabbit review when available**

Prerequisites:

- The workspace is inside this git repository.
- CodeRabbit CLI is installed and authenticated.
- There is a meaningful committed or uncommitted diff to review.

Run:

```powershell
coderabbit --version
coderabbit auth status --agent
coderabbit review --agent
```

Expected: CodeRabbit reports issues or `CodeRabbit raised 0 issues.` Any reported issues should be fixed with tests before publication.

- [ ] **Step 8: Prepare Sites deployment only after local success**

Run local build first:

```powershell
Set-Location apps\control-center
npm run build
```

Expected: build exits 0. After that, use the Sites connector flow to create or reuse a site, save a version from committed source, and deploy according to the configured access rules.

---

## Self-Review Notes

- Spec coverage: the plan covers safe defaults, all named agents, advisory ML training and model updates, scheduled order intents, broker boundaries, risk defaults, runtime modes, validation gates, GitHub readiness, Sites control center, CodeRabbit review, Expo deferral, and public-equity guardrails.
- Scope: the first build creates a working scaffold and dashboard. The four-week paper gate remains an operating requirement because it cannot be satisfied by initial code.
- Type consistency: `Settings`, `RuntimeMode`, `OrderIntent`, `Decision`, `AccountSnapshot`, `Position`, `LinearModel`, `ScheduledOrderIntent`, and broker names are used consistently across tasks.
