# Dual-Market ML Meta-Label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the synthetic demonstration model with independently trained, leakage-safe SPY and NIFTYBEES logistic meta-labelers that can become eligible for market-specific paper observation only after passing cost-aware walk-forward validation.

**Architecture:** The build has three boundaries: provider adapters normalize immutable daily data, a research pipeline builds point-in-time candidates and out-of-sample model evidence, and a paper coordinator consumes only compatible promoted artifacts. The ML layer returns pass or abstain and has no broker, execution, position-sizing, runtime-mode, or live-activation authority; SPY paper orders use only Alpaca's paper endpoint and NIFTYBEES uses only the local simulator.

**Tech Stack:** Python 3.11, standard-library `unittest`, `scikit-learn==1.9.0`, `pandas-market-calendars==5.4.0`, `growwapi==1.5.0`, JSON/JSONL artifacts, Decimal-based trade accounting, Next.js control center, PowerShell, Git.

## Global Constraints

- Support exactly two isolated lanes: `SPY` / market `US` / currency `USD`, and `NIFTYBEES` / market `IN` / currency `INR`.
- Use Alpaca `GET https://data.alpaca.markets/v2/stocks/bars` with `timeframe=1Day`, `sort=asc`, `adjustment=all`, explicit dates, and complete pagination.
- Use Groww's current historical candle operation corresponding to `GET /v1/historical/candles`; reject the deprecated `/v1/historical/candle/range` path.
- Preserve exchange trading dates and validate them with the NYSE or NSE calendar; a UTC conversion must not move a daily bar to a neighboring date.
- Generate features after session `D` closes, using bars through `D`; the earliest entry is session `D+1`.
- Use exactly the eight `daily-meta-v1` features from the approved design and require at least 61 completed bars.
- The deterministic candidate rule is long-only and requires positive 20-session return, close above the 60-session average, positive and sufficient liquidity, and 20-session volatility below the configured maximum.
- Label with a 2 percent stop, 3 percent target, and 10-session maximum hold after all effective-dated market costs; same-bar ambiguity resolves stop first.
- Use regularized logistic regression with `C` in `{0.1, 1.0, 10.0}` and thresholds in `{0.55, 0.60, 0.65}` only.
- Use at least three expanding walk-forward test folds, a 20 percent chronological calibration slice with at least 40 rows and both classes, and 10-session gaps before calibration and test.
- Require at least 150 one-time out-of-sample candidates, at least 30 positive and 30 negative labels, and at least 30 candidates per test fold.
- Promotion requires positive filtered replay expectancy in every fold, aggregate expectancy above baseline, drawdown no worse than baseline in every fold, Brier score below the training-prevalence baseline, and 10 to 80 percent acceptance coverage.
- A runtime feature beyond eight fit-slice standard deviations blocks the candidate; after 60 scored candidates, PSI above `0.25` for any feature blocks the lane.
- Paper observation requires 60 newly completed market sessions per lane and cannot be backfilled; a behavioral model replacement restarts that lane's clock.
- Store models as auditable JSON data only. Do not deserialize pickle or joblib model files.
- Credentials stay in process environment or the existing local secret workflow. Never read, print, persist, or recover them from Chrome, browser storage, chat, screenshots, clipboard history, manifests, artifacts, or logs.
- Do not manually set `ready_to_trade`, weaken broker preflight, bypass a static-IP or compliance gate, promise accuracy or profit, or submit a real-money order.
- The Groww generic Algo ID correction remains a separate broker-integration prerequisite; this ML plan neither invents nor bypasses it.
- RUFLO remains supervised and cannot select models, alter thresholds, place orders, or promote a lane.

---

## File Structure

### New Python Modules

- `market_sentinel/historical_data.py`: canonical daily-bar, dataset-manifest, calendar, and data-quality contracts.
- `market_sentinel/historical_clients.py`: credential-sanitized Alpaca and Groww historical-data adapters.
- `market_sentinel/dataset_store.py`: immutable JSONL bar artifacts and checksum-verified manifests.
- `market_sentinel/ml_features.py`: versioned point-in-time feature rows and deterministic market candidacy.
- `market_sentinel/ml_labels.py`: effective-dated costs and conservative protected-trade labels.
- `market_sentinel/ml_validation.py`: expanding fit/calibration/test fold construction with purge gaps.
- `market_sentinel/ml_evaluation.py`: chronological replay, classification metrics, calibration buckets, and promotion decisions.
- `market_sentinel/trial_ledger.py`: append-only JSONL experiment records.
- `market_sentinel/paper_validation.py`: independent paper-lane state and execution-target enforcement.

### Modified Python Modules

- `market_sentinel/api_clients.py`: add authenticated query-string `GET` support without logging headers.
- `market_sentinel/config.py`: add allowlisted historical endpoints and market-data settings.
- `market_sentinel/model_training.py`: replace the handwritten linear demonstration with fold-local sklearn fitting, sigmoid calibration, and JSON-safe artifacts.
- `market_sentinel/model_store.py`: store market-specific versions and active pointers with compatibility checks.
- `market_sentinel/prediction.py`: load an active artifact, enforce compatibility/outlier/drift gates, and return pass or abstain.
- `market_sentinel/strategy.py`: consume the deterministic candidate decision before ML and preserve existing protected-intent ownership.
- `market_sentinel/cli.py`: replace synthetic promotion with explicit download, dataset, train, validate, paper-promotion, and paper-status commands.
- `market_sentinel/ruflo.py`: report research and paper status without gaining model or broker authority.

### Tests And User Surfaces

- `tests/test_historical_data.py`: calendar and canonical-bar validation.
- `tests/test_historical_clients.py`: provider request mapping, pagination, instrument resolution, and redaction.
- `tests/test_dataset_store.py`: immutability and checksum lineage.
- `tests/test_ml_features.py`: feature formulas, warmup, timestamp boundaries, and candidacy.
- `tests/test_ml_labels.py`: costs and conservative daily-bar fills.
- `tests/test_ml_validation.py`: chronological slices, gaps, counts, and one-time OOS membership.
- `tests/test_market_model_training.py`: fold-local scaling, calibration, thresholds, and JSON artifacts.
- `tests/test_ml_evaluation.py`: replay and every promotion gate.
- `tests/test_trial_ledger_and_model_store.py`: immutable trials and isolated active pointers.
- `tests/test_ml_runtime_and_drift.py`: compatibility, stale data, hard outliers, PSI, and authority boundaries.
- `tests/test_paper_validation.py`: execution-target isolation and independent 60-session clocks.
- `tests/test_operations.py`: CLI and dashboard integration without synthetic activation.
- `tests/test_research_agents.py`: RUFLO remains supervised and paper-only.
- `apps/control-center/app/page.tsx`: separate lane evidence panels with no order controls.
- `apps/control-center/public/status.json`: blocked-by-default generated example, with no fabricated accuracy or promotion.
- `README.md`: reproducible research and paper commands plus limitations.
- `.gitignore`: ignore runtime datasets, trials, model artifacts, and paper state.
- `pyproject.toml`: pin the two runtime dependencies.

---

### Task 1: Canonical Daily Bars And Exchange Calendars

**Files:**
- Modify: `pyproject.toml`
- Create: `market_sentinel/historical_data.py`
- Create: `tests/test_historical_data.py`

**Interfaces:**
- Consumes: Python `date`, `datetime`, and `Decimal` values from provider adapters.
- Produces: `AdjustmentMode`, `CanonicalDailyBar`, `DatasetManifest`, `expected_sessions(market, start, end)`, and `validate_daily_bars(...)` for Tasks 2-5.

- [ ] **Step 1: Write failing calendar and OHLCV-contract tests**

```python
# tests/test_historical_data.py
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

from market_sentinel.historical_data import (
    AdjustmentMode,
    CanonicalDailyBar,
    expected_sessions,
    validate_daily_bars,
)


def bar(day: date, *, high: str = "102", source_date: date | None = None) -> CanonicalDailyBar:
    return CanonicalDailyBar(
        provider="alpaca",
        provider_symbol="SPY",
        symbol="SPY",
        market="US",
        currency="USD",
        trading_date=source_date or day,
        source_timezone="America/New_York",
        open=Decimal("100"),
        high=Decimal(high),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=1000,
        adjustment_mode=AdjustmentMode.ALL,
        retrieved_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
        source_checksum="a" * 64,
    )


class HistoricalDataTest(unittest.TestCase):
    def test_nyse_calendar_excludes_independence_day_observed(self):
        sessions = expected_sessions("US", date(2026, 7, 2), date(2026, 7, 6))
        self.assertEqual(sessions, (date(2026, 7, 2), date(2026, 7, 6)))

    def test_validation_preserves_exchange_date_and_rejects_bad_high(self):
        valid = validate_daily_bars(
            (bar(date(2026, 7, 16)),),
            expected_symbol="SPY",
            expected_market="US",
            expected_currency="USD",
            expected_adjustment=AdjustmentMode.ALL,
            last_completed_session=date(2026, 7, 16),
        )
        self.assertEqual(valid[0].trading_date, date(2026, 7, 16))
        with self.assertRaisesRegex(ValueError, "high is below OHLC value"):
            validate_daily_bars(
                (bar(date(2026, 7, 16), high="100"),),
                expected_symbol="SPY",
                expected_market="US",
                expected_currency="USD",
                expected_adjustment=AdjustmentMode.ALL,
                last_completed_session=date(2026, 7, 16),
            )

    def test_validation_rejects_unexplained_session_gap(self):
        with self.assertRaisesRegex(ValueError, "missing exchange sessions: 2026-07-15"):
            validate_daily_bars(
                (bar(date(2026, 7, 14)), bar(date(2026, 7, 16))),
                expected_symbol="SPY",
                expected_market="US",
                expected_currency="USD",
                expected_adjustment=AdjustmentMode.ALL,
                last_completed_session=date(2026, 7, 16),
            )

    def test_provider_unspecified_series_blocks_unreconciled_large_gap(self):
        first = replace(bar(date(2026, 7, 15)), provider="groww", provider_symbol="NSE-NIFTYBEES", symbol="NIFTYBEES", market="IN", currency="INR", source_timezone="Asia/Kolkata", adjustment_mode=AdjustmentMode.PROVIDER_UNSPECIFIED)
        second = replace(first, trading_date=date(2026, 7, 16), open=Decimal("50"), high=Decimal("51"), low=Decimal("49"), close=Decimal("50"))
        with self.assertRaisesRegex(ValueError, "unreconciled distribution discontinuity"):
            validate_daily_bars((first, second), expected_symbol="NIFTYBEES", expected_market="IN", expected_currency="INR", expected_adjustment=AdjustmentMode.PROVIDER_UNSPECIFIED, last_completed_session=date(2026, 7, 16))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and confirm the missing module failure**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_historical_data -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'market_sentinel.historical_data'`.

- [ ] **Step 3: Pin dependencies and implement the canonical contract**

Add this exact dependency block to `pyproject.toml`:

```toml
dependencies = [
  "growwapi==1.5.0",
  "pandas-market-calendars==5.4.0",
  "scikit-learn==1.9.0",
]
```

Implement these exact public definitions in `market_sentinel/historical_data.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import pandas_market_calendars as mcal


class AdjustmentMode(StrEnum):
    ALL = "all"
    PROVIDER_UNSPECIFIED = "provider-unspecified"


@dataclass(frozen=True)
class CanonicalDailyBar:
    provider: str
    provider_symbol: str
    symbol: str
    market: str
    currency: str
    trading_date: date
    source_timezone: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjustment_mode: AdjustmentMode
    retrieved_at: datetime
    source_checksum: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_symbol": self.provider_symbol,
            "symbol": self.symbol,
            "market": self.market,
            "currency": self.currency,
            "trading_date": self.trading_date.isoformat(),
            "source_timezone": self.source_timezone,
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": self.volume,
            "adjustment_mode": self.adjustment_mode.value,
            "retrieved_at": self.retrieved_at.isoformat(),
            "source_checksum": self.source_checksum,
        }


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    provider: str
    provider_symbol: str
    symbol: str
    market: str
    currency: str
    interval: str
    adjustment_mode: AdjustmentMode
    requested_start: date
    requested_end: date
    first_trading_date: date
    last_trading_date: date
    retrieved_at: datetime
    response_page_count: int
    requested_feed: str | None
    source_checksum: str
    row_count: int
    reconciliation_record_id: str | None


def expected_sessions(market: str, start: date, end: date) -> tuple[date, ...]:
    calendar_name = {"US": "NYSE", "IN": "NSE"}.get(market)
    if calendar_name is None:
        raise ValueError(f"unsupported market: {market}")
    schedule = mcal.get_calendar(calendar_name).schedule(start_date=start, end_date=end)
    return tuple(timestamp.date() for timestamp in schedule.index)


def validate_daily_bars(
    bars: tuple[CanonicalDailyBar, ...],
    *,
    expected_symbol: str,
    expected_market: str,
    expected_currency: str,
    expected_adjustment: AdjustmentMode,
    last_completed_session: date,
    reconciled_discontinuity_dates: frozenset[date] = frozenset(),
) -> tuple[CanonicalDailyBar, ...]:
    if not bars:
        raise ValueError("daily-bar dataset is empty")
    dates: list[date] = []
    previous: CanonicalDailyBar | None = None
    for item in bars:
        if (item.symbol, item.market, item.currency, item.adjustment_mode) != (
            expected_symbol,
            expected_market,
            expected_currency,
            expected_adjustment,
        ):
            raise ValueError("unexpected symbol, market, currency, or adjustment mode")
        if item.trading_date > last_completed_session:
            raise ValueError("bar is later than the last completed session")
        if min(item.open, item.high, item.low, item.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if item.volume < 0:
            raise ValueError("volume must be non-negative")
        if item.high < max(item.open, item.close, item.low):
            raise ValueError("high is below OHLC value")
        if item.low > min(item.open, item.close, item.high):
            raise ValueError("low is above OHLC value")
        if previous is not None and expected_adjustment == AdjustmentMode.PROVIDER_UNSPECIFIED:
            opening_gap = abs((item.open / previous.close) - Decimal("1"))
            if opening_gap >= Decimal("0.35") and item.trading_date not in reconciled_discontinuity_dates:
                raise ValueError(f"unreconciled distribution discontinuity on {item.trading_date.isoformat()}")
        dates.append(item.trading_date)
        previous = item
    if dates != sorted(set(dates)):
        raise ValueError("trading dates must be unique and strictly increasing")
    expected = expected_sessions(expected_market, dates[0], dates[-1])
    missing = [day for day in expected if day not in set(dates)]
    if missing:
        rendered = ", ".join(day.isoformat() for day in missing)
        raise ValueError(f"missing exchange sessions: {rendered}")
    return bars
```

- [ ] **Step 4: Install and verify Task 1**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip install -e .
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_historical_data -v
```

Expected: editable installation succeeds and all `HistoricalDataTest` tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add pyproject.toml market_sentinel/historical_data.py tests/test_historical_data.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add canonical daily market data'
```

### Task 2: Historical Provider Clients And Secret Redaction

**Files:**
- Modify: `market_sentinel/api_clients.py`
- Modify: `market_sentinel/config.py`
- Create: `market_sentinel/historical_clients.py`
- Create: `tests/test_historical_clients.py`

**Interfaces:**
- Consumes: `CanonicalDailyBar` and `AdjustmentMode` from Task 1; `Settings` credential fields.
- Produces: `HttpClient.get_json(...)`, `HistoricalDownload`, `AlpacaHistoricalClient.download(...)`, `GrowwHistoricalClient.download(...)`, and `sanitize_provider_error(...)`.

- [ ] **Step 1: Write failing provider-contract tests**

```python
# tests/test_historical_clients.py
import unittest
from datetime import date

from market_sentinel.api_clients import HttpResponse
from market_sentinel.historical_clients import AlpacaHistoricalClient, GrowwHistoricalClient, sanitize_provider_error


class RecordingHttp:
    def __init__(self, responses: list[HttpResponse]):
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def get_json(self, url: str, *, headers: dict[str, str], query: dict[str, str]) -> HttpResponse:
        self.calls.append((url, headers, query))
        return self.responses.pop(0)


class FakeGrowwSDK:
    EXCHANGE_NSE = "NSE"
    SEGMENT_CASH = "CASH"
    CANDLE_INTERVAL_DAY = "1 day"

    def __init__(self):
        self.historical_calls: list[dict[str, str]] = []

    def get_instrument_by_exchange_and_trading_symbol(self, *, exchange: str, trading_symbol: str) -> dict[str, object]:
        return {"exchange": exchange, "trading_symbol": trading_symbol, "groww_symbol": f"NSE-{trading_symbol}", "segment": "CASH"}

    def get_historical_candles(self, **kwargs: str) -> dict[str, object]:
        self.historical_calls.append(kwargs)
        return {"candles": [[kwargs["start_time"][:10], 250, 255, 249, 254, 10000, None]]}


class HistoricalClientsTest(unittest.TestCase):
    def test_alpaca_requests_adjusted_daily_bars_and_paginates(self):
        http = RecordingHttp([
            HttpResponse(200, {"bars": {"SPY": [{"t": "2026-07-15T04:00:00Z", "o": 100, "h": 102, "l": 99, "c": 101, "v": 10}]}, "next_page_token": "next"}),
            HttpResponse(200, {"bars": {"SPY": [{"t": "2026-07-16T04:00:00Z", "o": 101, "h": 103, "l": 100, "c": 102, "v": 11}]}}),
        ])
        download = AlpacaHistoricalClient(http, key_id="key", secret_key="secret").download(
            symbol="SPY", start=date(2026, 7, 15), end=date(2026, 7, 16), feed="iex"
        )
        self.assertEqual(download.page_count, 2)
        self.assertEqual(http.calls[0][0], "https://data.alpaca.markets/v2/stocks/bars")
        self.assertEqual(http.calls[0][2]["adjustment"], "all")
        self.assertEqual(http.calls[1][2]["page_token"], "next")
        self.assertEqual(download.bars[0].trading_date, date(2026, 7, 15))

    def test_groww_resolves_nse_cash_symbol_and_uses_current_path(self):
        sdk = FakeGrowwSDK()
        download = GrowwHistoricalClient(sdk).download(symbol="NIFTYBEES", start=date(2026, 7, 16), end=date(2026, 7, 16))
        self.assertEqual(sdk.historical_calls[0]["exchange"], "NSE")
        self.assertEqual(sdk.historical_calls[0]["segment"], "CASH")
        self.assertEqual(sdk.historical_calls[0]["groww_symbol"], "NSE-NIFTYBEES")
        self.assertEqual(sdk.historical_calls[0]["candle_interval"], "1 day")
        self.assertEqual(download.bars[0].adjustment_mode.value, "provider-unspecified")

    def test_groww_splits_daily_history_into_supported_180_day_windows(self):
        sdk = FakeGrowwSDK()
        GrowwHistoricalClient(sdk).download(symbol="NIFTYBEES", start=date(2026, 1, 1), end=date(2026, 7, 16))
        self.assertEqual(len(sdk.historical_calls), 2)

    def test_provider_error_redacts_market_specific_secrets(self):
        text = sanitize_provider_error("key=ALPACA123 token=GROWW456", ("ALPACA123", "GROWW456"))
        self.assertEqual(text, "key=[REDACTED] token=[REDACTED]")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and confirm imports fail**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_historical_clients -v
```

Expected: FAIL because `market_sentinel.historical_clients` and `HttpClient.get_json` do not exist.

- [ ] **Step 3: Implement GET support and provider adapters**

Add to `HttpClient` and `UrllibHttpClient` in `market_sentinel/api_clients.py`:

```python
    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        query: dict[str, str],
    ) -> HttpResponse:
        encoded_url = f"{url}?{parse.urlencode(query)}" if query else url
        req = request.Request(encoded_url, headers=headers, method="GET")
        with request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
            return HttpResponse(response.status, json.loads(text) if text else {})
```

Add `alpaca_market_data_endpoint: str = "https://data.alpaca.markets"` to `Settings`, parse it with `_parse_endpoint`, and allow only that exact HTTPS host. The Groww lane uses the pinned official SDK operation, not a hand-built or deprecated URL.

Implement this public surface in `market_sentinel/historical_clients.py`; response hashing must use canonical JSON bytes with sorted keys and compact separators:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Protocol

from market_sentinel.api_clients import HttpClient
from market_sentinel.historical_data import AdjustmentMode, CanonicalDailyBar


@dataclass(frozen=True)
class HistoricalDownload:
    bars: tuple[CanonicalDailyBar, ...]
    page_count: int
    source_query: dict[str, str]
    response_checksum: str


def sanitize_provider_error(message: str, secrets: tuple[str, ...]) -> str:
    sanitized = message
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized


def _checksum(payloads: list[dict[str, Any]]) -> str:
    encoded = json.dumps(payloads, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AlpacaHistoricalClient:
    endpoint = "https://data.alpaca.markets/v2/stocks/bars"

    def __init__(self, http: HttpClient, *, key_id: str, secret_key: str):
        self.http = http
        self.headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key}

    def download(self, *, symbol: str, start: date, end: date, feed: str) -> HistoricalDownload:
        query = {"symbols": symbol, "timeframe": "1Day", "start": start.isoformat(), "end": end.isoformat(), "sort": "asc", "adjustment": "all", "feed": feed}
        pages: list[dict[str, Any]] = []
        raw_bars: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            request_query = dict(query)
            if page_token is not None:
                request_query["page_token"] = page_token
            response = self.http.get_json(self.endpoint, headers=self.headers, query=request_query)
            if response.status_code != 200:
                raise RuntimeError(f"Alpaca historical request failed with status {response.status_code}")
            pages.append(response.payload)
            raw_bars.extend(response.payload.get("bars", {}).get(symbol, []))
            page_token = response.payload.get("next_page_token")
            if not page_token:
                break
        checksum = _checksum(pages)
        retrieved_at = datetime.now(timezone.utc)
        bars = tuple(CanonicalDailyBar(
            provider="alpaca", provider_symbol=symbol, symbol=symbol, market="US", currency="USD",
            trading_date=date.fromisoformat(str(item["t"])[:10]), source_timezone="America/New_York",
            open=Decimal(str(item["o"])), high=Decimal(str(item["h"])), low=Decimal(str(item["l"])),
            close=Decimal(str(item["c"])), volume=int(item["v"]), adjustment_mode=AdjustmentMode.ALL,
            retrieved_at=retrieved_at, source_checksum=checksum,
        ) for item in raw_bars)
        return HistoricalDownload(bars, len(pages), query, checksum)


class GrowwHistoricalSDK(Protocol):
    EXCHANGE_NSE: str
    SEGMENT_CASH: str
    CANDLE_INTERVAL_DAY: str

    def get_instrument_by_exchange_and_trading_symbol(self, *, exchange: str, trading_symbol: str) -> dict[str, object]:
        raise NotImplementedError

    def get_historical_candles(
        self,
        *,
        exchange: str,
        segment: str,
        groww_symbol: str,
        start_time: str,
        end_time: str,
        candle_interval: str,
    ) -> dict[str, object]:
        raise NotImplementedError


class GrowwHistoricalClient:
    def __init__(self, sdk: GrowwHistoricalSDK):
        self.sdk = sdk

    def download(self, *, symbol: str, start: date, end: date) -> HistoricalDownload:
        instrument = self.sdk.get_instrument_by_exchange_and_trading_symbol(exchange=self.sdk.EXCHANGE_NSE, trading_symbol=symbol)
        if (instrument.get("exchange"), instrument.get("segment"), instrument.get("trading_symbol")) != ("NSE", "CASH", symbol):
            raise ValueError("Groww instrument must resolve to the requested NSE CASH symbol")
        provider_symbol = str(instrument["groww_symbol"])
        if provider_symbol != f"NSE-{symbol}":
            raise ValueError("Groww instrument returned an unexpected Groww symbol")
        payloads: list[dict[str, Any]] = []
        cursor = start
        while cursor <= end:
            chunk_end = min(end, cursor + timedelta(days=179))
            payload = self.sdk.get_historical_candles(
                exchange=self.sdk.EXCHANGE_NSE,
                segment=self.sdk.SEGMENT_CASH,
                groww_symbol=provider_symbol,
                start_time=f"{cursor.isoformat()} 00:00:00",
                end_time=f"{chunk_end.isoformat()} 23:59:59",
                candle_interval=self.sdk.CANDLE_INTERVAL_DAY,
            )
            payloads.append(payload)
            cursor = chunk_end + timedelta(days=1)
        checksum = _checksum(payloads)
        retrieved_at = datetime.now(timezone.utc)
        candles = [item for payload in payloads for item in payload.get("candles", [])]
        bars = tuple(CanonicalDailyBar(
            provider="groww", provider_symbol=provider_symbol, symbol=symbol, market="IN", currency="INR",
            trading_date=date.fromisoformat(str(item[0])[:10]), source_timezone="Asia/Kolkata",
            open=Decimal(str(item[1])), high=Decimal(str(item[2])), low=Decimal(str(item[3])),
            close=Decimal(str(item[4])), volume=int(item[5]), adjustment_mode=AdjustmentMode.PROVIDER_UNSPECIFIED,
            retrieved_at=retrieved_at, source_checksum=checksum,
        ) for item in candles)
        query = {"exchange": "NSE", "segment": "CASH", "groww_symbol": provider_symbol, "interval": "1 day", "start": start.isoformat(), "end": end.isoformat()}
        return HistoricalDownload(bars, len(payloads), query, checksum)
```

- [ ] **Step 4: Run focused provider tests**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_historical_clients -v
```

Expected: all provider tests pass; test output and exceptions contain no supplied secret values.

- [ ] **Step 5: Commit Task 2**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/api_clients.py market_sentinel/config.py market_sentinel/historical_clients.py tests/test_historical_clients.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add broker historical data clients'
```

### Task 3: Immutable Dataset Store And Manifest Lineage

**Files:**
- Create: `market_sentinel/dataset_store.py`
- Create: `tests/test_dataset_store.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `HistoricalDownload`, `CanonicalDailyBar`, `DatasetManifest`, and validated lane metadata.
- Produces: `DatasetStore.write(...)`, `DatasetStore.load(...)`, and `StoredDataset` for feature generation.

- [ ] **Step 1: Write failing immutability and isolation tests**

```python
# tests/test_dataset_store.py
import tempfile
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from market_sentinel.dataset_store import DatasetStore
from market_sentinel.historical_data import AdjustmentMode, CanonicalDailyBar


def one_bar(symbol: str, market: str, currency: str, checksum: str) -> CanonicalDailyBar:
    return CanonicalDailyBar("alpaca" if market == "US" else "groww", symbol, symbol, market, currency,
        date(2026, 7, 16), "America/New_York" if market == "US" else "Asia/Kolkata",
        Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 1000,
        AdjustmentMode.ALL if market == "US" else AdjustmentMode.PROVIDER_UNSPECIFIED,
        datetime(2026, 7, 17, tzinfo=timezone.utc), checksum)


class DatasetStoreTest(unittest.TestCase):
    def test_write_is_content_addressed_and_existing_artifact_is_not_mutated(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DatasetStore(Path(directory))
            first = store.write((one_bar("SPY", "US", "USD", "a" * 64),), requested_start=date(2026, 7, 1), requested_end=date(2026, 7, 16), interval="1Day", page_count=1, feed="iex")
            second = store.write((one_bar("SPY", "US", "USD", "a" * 64),), requested_start=date(2026, 7, 1), requested_end=date(2026, 7, 16), interval="1Day", page_count=1, feed="iex")
            self.assertEqual(first.manifest.dataset_id, second.manifest.dataset_id)
            self.assertEqual(first.bars_path.read_bytes(), second.bars_path.read_bytes())

    def test_market_paths_and_checksums_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DatasetStore(Path(directory))
            spy = store.write((one_bar("SPY", "US", "USD", "a" * 64),), requested_start=date(2026, 7, 1), requested_end=date(2026, 7, 16), interval="1Day", page_count=1, feed="iex")
            nifty = store.write((one_bar("NIFTYBEES", "IN", "INR", "b" * 64),), requested_start=date(2026, 7, 1), requested_end=date(2026, 7, 16), interval="1Day", page_count=1, feed=None)
            self.assertNotEqual(spy.manifest.dataset_id, nifty.manifest.dataset_id)
            self.assertIn("US", str(spy.bars_path))
            self.assertIn("IN", str(nifty.bars_path))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the store tests and confirm the missing module failure**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_dataset_store -v
```

Expected: FAIL with `ModuleNotFoundError` for `market_sentinel.dataset_store`.

- [ ] **Step 3: Implement content-addressed JSONL storage**

Implement `StoredDataset` and `DatasetStore` so `dataset_id` is SHA-256 over the canonical bar JSONL bytes, paths are `root/<market>/<symbol>/<dataset_id>/`, writes use exclusive creation, and `load` recomputes both the bar checksum and manifest identity before returning. Use this exact public surface:

```python
@dataclass(frozen=True)
class StoredDataset:
    manifest: DatasetManifest
    manifest_path: Path
    bars_path: Path


class DatasetStore:
    def __init__(self, root: Path):
        self.root = root

    def write(
        self,
        bars: tuple[CanonicalDailyBar, ...],
        *,
        requested_start: date,
        requested_end: date,
        interval: str,
        page_count: int,
        feed: str | None,
        reconciliation_record_id: str | None = None,
    ) -> StoredDataset:
        if not bars:
            raise ValueError("cannot persist an empty dataset")
        lines = b"".join(
            json.dumps(item.to_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            for item in bars
        )
        dataset_id = hashlib.sha256(lines).hexdigest()
        directory = self.root / bars[0].market / bars[0].symbol / dataset_id
        directory.mkdir(parents=True, exist_ok=True)
        bars_path = directory / "bars.jsonl"
        if bars_path.exists() and bars_path.read_bytes() != lines:
            raise RuntimeError("content-addressed dataset collision")
        if not bars_path.exists():
            bars_path.write_bytes(lines)
        manifest = DatasetManifest(
            dataset_id=dataset_id, provider=bars[0].provider, provider_symbol=bars[0].provider_symbol,
            symbol=bars[0].symbol, market=bars[0].market, currency=bars[0].currency, interval=interval,
            adjustment_mode=bars[0].adjustment_mode, requested_start=requested_start,
            requested_end=requested_end, first_trading_date=bars[0].trading_date,
            last_trading_date=bars[-1].trading_date, retrieved_at=bars[0].retrieved_at,
            response_page_count=page_count, requested_feed=feed, source_checksum=bars[0].source_checksum,
            row_count=len(bars), reconciliation_record_id=reconciliation_record_id,
        )
        manifest_path = directory / "manifest.json"
        payload = asdict(manifest)
        payload = {key: value.value if isinstance(value, AdjustmentMode) else value.isoformat() if isinstance(value, (date, datetime)) else value for key, value in payload.items()}
        encoded = json.dumps(payload, indent=2, sort_keys=True)
        if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != encoded:
            raise RuntimeError("immutable dataset manifest differs")
        if not manifest_path.exists():
            manifest_path.write_text(encoded, encoding="utf-8")
        return StoredDataset(manifest, manifest_path, bars_path)

    def load(self, market: str, symbol: str, dataset_id: str) -> tuple[DatasetManifest, tuple[CanonicalDailyBar, ...]]:
        directory = self.root / market / symbol / dataset_id
        lines = (directory / "bars.jsonl").read_bytes()
        if hashlib.sha256(lines).hexdigest() != dataset_id:
            raise ValueError("dataset checksum mismatch")
        payload = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if payload["dataset_id"] != dataset_id or payload["market"] != market or payload["symbol"] != symbol:
            raise ValueError("dataset manifest identity mismatch")
        return _manifest_from_payload(payload), tuple(_bar_from_payload(json.loads(line)) for line in lines.splitlines())


def _manifest_from_payload(payload: dict[str, object]) -> DatasetManifest:
    return DatasetManifest(
        dataset_id=str(payload["dataset_id"]), provider=str(payload["provider"]),
        provider_symbol=str(payload["provider_symbol"]), symbol=str(payload["symbol"]),
        market=str(payload["market"]), currency=str(payload["currency"]), interval=str(payload["interval"]),
        adjustment_mode=AdjustmentMode(str(payload["adjustment_mode"])),
        requested_start=date.fromisoformat(str(payload["requested_start"])),
        requested_end=date.fromisoformat(str(payload["requested_end"])),
        first_trading_date=date.fromisoformat(str(payload["first_trading_date"])),
        last_trading_date=date.fromisoformat(str(payload["last_trading_date"])),
        retrieved_at=datetime.fromisoformat(str(payload["retrieved_at"])),
        response_page_count=int(payload["response_page_count"]),
        requested_feed=None if payload["requested_feed"] is None else str(payload["requested_feed"]),
        source_checksum=str(payload["source_checksum"]), row_count=int(payload["row_count"]),
        reconciliation_record_id=None if payload["reconciliation_record_id"] is None else str(payload["reconciliation_record_id"]),
    )


def _bar_from_payload(payload: dict[str, object]) -> CanonicalDailyBar:
    return CanonicalDailyBar(
        provider=str(payload["provider"]), provider_symbol=str(payload["provider_symbol"]),
        symbol=str(payload["symbol"]), market=str(payload["market"]), currency=str(payload["currency"]),
        trading_date=date.fromisoformat(str(payload["trading_date"])), source_timezone=str(payload["source_timezone"]),
        open=Decimal(str(payload["open"])), high=Decimal(str(payload["high"])),
        low=Decimal(str(payload["low"])), close=Decimal(str(payload["close"])), volume=int(payload["volume"]),
        adjustment_mode=AdjustmentMode(str(payload["adjustment_mode"])),
        retrieved_at=datetime.fromisoformat(str(payload["retrieved_at"])), source_checksum=str(payload["source_checksum"]),
    )
```

Add these exact runtime paths to `.gitignore`:

```gitignore
data/datasets/
data/models/
data/trials/
data/paper/
```

- [ ] **Step 4: Run store tests and checksum-tampering test**

Add one more test that changes one byte in `bars.jsonl` and asserts `load` raises `ValueError("dataset checksum mismatch")`, then run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_dataset_store -v
```

Expected: all dataset-store tests pass.

- [ ] **Step 5: Commit Task 3**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add .gitignore market_sentinel/dataset_store.py tests/test_dataset_store.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: persist immutable market datasets'
```

### Task 4: Point-In-Time Features And Deterministic Candidates

**Files:**
- Create: `market_sentinel/ml_features.py`
- Create: `tests/test_ml_features.py`
- Modify: `market_sentinel/strategy.py`

**Interfaces:**
- Consumes: validated `tuple[CanonicalDailyBar, ...]`.
- Produces: `FEATURE_SCHEMA_VERSION`, `FEATURE_ORDER`, `FeatureRow`, `CandidateRule`, `build_feature_rows(...)`, and `is_market_candidate(...)`.

- [ ] **Step 1: Write failing formula, warmup, and timing tests**

```python
# tests/test_ml_features.py
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from market_sentinel.historical_data import AdjustmentMode, CanonicalDailyBar
from market_sentinel.ml_features import CandidateRule, build_feature_rows, is_market_candidate


def bars(count: int) -> tuple[CanonicalDailyBar, ...]:
    start = date(2026, 1, 1)
    return tuple(CanonicalDailyBar(
        "alpaca", "SPY", "SPY", "US", "USD", start + timedelta(days=index), "America/New_York",
        Decimal(100 + index), Decimal(102 + index), Decimal(99 + index), Decimal(101 + index), 1000 + index,
        AdjustmentMode.ALL, datetime(2026, 7, 17, tzinfo=timezone.utc), "a" * 64,
    ) for index in range(count))


class MLFeaturesTest(unittest.TestCase):
    def test_requires_61_bars_and_uses_only_data_through_feature_date(self):
        self.assertEqual(build_feature_rows(bars(60)), ())
        next_session = date(2026, 3, 10)
        rows = build_feature_rows(bars(62), next_session=next_session)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].feature_as_of, bars(62)[60].trading_date)
        self.assertEqual(rows[0].entry_eligible_at, bars(62)[61].trading_date)
        self.assertEqual(rows[1].entry_eligible_at, next_session)
        changed_future = list(bars(62))
        changed_future[61] = CanonicalDailyBar(**{**changed_future[61].__dict__, "close": Decimal("9999")})
        self.assertEqual(rows[0].values, build_feature_rows(tuple(changed_future), next_session=next_session)[0].values)

    def test_exact_returns_and_candidate_rule(self):
        row = build_feature_rows(bars(62))[0]
        self.assertEqual(row.values["return_5"], (Decimal("161") / Decimal("156")) - Decimal("1"))
        self.assertTrue(is_market_candidate(row, CandidateRule(Decimal("1000"), Decimal("1"))))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the feature tests and confirm the missing module failure**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_features -v
```

Expected: FAIL because `market_sentinel.ml_features` does not exist.

- [ ] **Step 3: Implement the frozen feature schema and candidate rule**

Use the following exact feature names and public types:

```python
FEATURE_SCHEMA_VERSION = "daily-meta-v1"
FEATURE_ORDER = (
    "return_5", "return_20", "return_60", "volatility_20",
    "close_vs_ma_20", "close_vs_ma_60", "volume_vs_average_20", "drawdown_60",
)


@dataclass(frozen=True)
class FeatureRow:
    symbol: str
    market: str
    currency: str
    feature_as_of: date
    entry_eligible_at: date
    feature_schema: str
    last_close: Decimal
    current_volume: Decimal
    average_volume_20: Decimal
    values: dict[str, Decimal]


@dataclass(frozen=True)
class CandidateRule:
    minimum_average_volume: Decimal
    maximum_volatility_20: Decimal


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def build_feature_rows(
    bars: tuple[CanonicalDailyBar, ...],
    *,
    next_session: date | None = None,
) -> tuple[FeatureRow, ...]:
    rows: list[FeatureRow] = []
    stop = len(bars) if next_session is not None else max(60, len(bars) - 1)
    for index in range(60, stop):
        closes = [item.close for item in bars[: index + 1]]
        volumes = [Decimal(item.volume) for item in bars[: index + 1]]
        daily_returns = [(closes[position] / closes[position - 1]) - Decimal("1") for position in range(index - 19, index + 1)]
        mean_return = _mean(daily_returns)
        variance = sum((value - mean_return) ** 2 for value in daily_returns) / Decimal(len(daily_returns) - 1)
        values = {
            "return_5": (closes[-1] / closes[-6]) - Decimal("1"),
            "return_20": (closes[-1] / closes[-21]) - Decimal("1"),
            "return_60": (closes[-1] / closes[-61]) - Decimal("1"),
            "volatility_20": Decimal(str(float(variance) ** 0.5)),
            "close_vs_ma_20": (closes[-1] / _mean(closes[-20:])) - Decimal("1"),
            "close_vs_ma_60": (closes[-1] / _mean(closes[-60:])) - Decimal("1"),
            "volume_vs_average_20": volumes[-1] / _mean(volumes[-20:]),
            "drawdown_60": (closes[-1] / max(closes[-60:])) - Decimal("1"),
        }
        entry_eligible_at = bars[index + 1].trading_date if index + 1 < len(bars) else next_session
        if entry_eligible_at is None:
            raise ValueError("latest feature row requires its next exchange session")
        rows.append(FeatureRow(
            bars[index].symbol, bars[index].market, bars[index].currency, bars[index].trading_date, entry_eligible_at,
            FEATURE_SCHEMA_VERSION, closes[-1], volumes[-1], _mean(volumes[-20:]), values,
        ))
    return tuple(rows)


def is_market_candidate(row: FeatureRow, rule: CandidateRule) -> bool:
    values = row.values
    return (
        values["return_20"] > 0
        and values["close_vs_ma_60"] > 0
        and row.current_volume > 0
        and row.average_volume_20 >= rule.minimum_average_volume
        and values["volatility_20"] < rule.maximum_volatility_20
    )
```

Update `StrategyAgent.generate(self, feature_row: FeatureRow, candidate_passed: bool, prediction: Prediction) -> list[OrderIntent]`. Return no intent unless both deterministic candidacy and `prediction.passed` are true, and use `feature_row.last_close` as the limit price. Preserve the existing quantity, 2 percent stop, 3 percent target, market/symbol from `feature_row`, and ETF classification; the model must not supply any of those fields.

- [ ] **Step 4: Run feature and strategy tests**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_features tests.test_agents -v
```

Expected: all tests pass, including a strategy test proving `candidate_passed=False` suppresses an otherwise passing ML prediction.

- [ ] **Step 5: Commit Task 4**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/ml_features.py market_sentinel/strategy.py tests/test_ml_features.py tests/test_agents.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add point in time market candidates'
```

### Task 5: Effective-Dated Costs And Conservative Meta-Labels

**Files:**
- Create: `market_sentinel/ml_labels.py`
- Create: `tests/test_ml_labels.py`

**Interfaces:**
- Consumes: `FeatureRow`, future bars beginning at `entry_eligible_at`, and a market-specific `CostProfile`.
- Produces: `CostSchedule`, `CostProfile`, `CostBreakdown`, `MetaLabelRow`, `select_cost_schedule(...)`, and `label_candidate(...)`.

- [ ] **Step 1: Write failing protected-fill and cost tests**

```python
# tests/test_ml_labels.py
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from market_sentinel.historical_data import AdjustmentMode, CanonicalDailyBar
from market_sentinel.ml_features import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, FeatureRow
from market_sentinel.ml_labels import CostProfile, CostSchedule, label_candidate


class MLLabelsTest(unittest.TestCase):
    def setUp(self):
        self.costs = CostProfile("US", "USD", "us-cost-v1", (
            CostSchedule(date(2020, 1, 1), Decimal("0"), Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("1.00"), "test schedule"),
        ))

    def feature_row(self) -> FeatureRow:
        return FeatureRow(
            "SPY", "US", "USD", date(2026, 7, 15), date(2026, 7, 16), FEATURE_SCHEMA_VERSION,
            Decimal("100"), Decimal("10000"), Decimal("9000"), {name: Decimal("0.1") for name in FEATURE_ORDER},
        )

    def canonical_bar(self, offset: int, open_price: str, high: str, low: str, close: str) -> CanonicalDailyBar:
        return CanonicalDailyBar(
            "alpaca", "SPY", "SPY", "US", "USD", date(2026, 7, 16) + timedelta(days=offset),
            "America/New_York", Decimal(open_price), Decimal(high), Decimal(low), Decimal(close), 10000,
            AdjustmentMode.ALL, datetime(2026, 7, 17, tzinfo=timezone.utc), "a" * 64,
        )

    def future_bars(self, *, open_price: str, high: str, low: str) -> tuple[CanonicalDailyBar, ...]:
        first = self.canonical_bar(0, open_price, high, low, open_price)
        rest = tuple(self.canonical_bar(index, open_price, open_price, open_price, open_price) for index in range(1, 10))
        return (first, *rest)

    def gap_bars(self, *, second_open: str) -> tuple[CanonicalDailyBar, ...]:
        entry = self.canonical_bar(0, "100", "101", "99", "100")
        gap = self.canonical_bar(1, second_open, second_open, second_open, second_open)
        rest = tuple(self.canonical_bar(index, second_open, second_open, second_open, second_open) for index in range(2, 10))
        return (entry, gap, *rest)

    def flat_future_bars(self, count: int) -> tuple[CanonicalDailyBar, ...]:
        return tuple(self.canonical_bar(index, "100", "101", "99", "100") for index in range(count))

    def test_same_bar_stop_and_target_uses_stop_first(self):
        result = label_candidate(self.feature_row(), self.future_bars(open_price="100", high="104", low="97"), self.costs)
        self.assertEqual(result.exit_reason, "stop")
        self.assertEqual(result.exit_price_before_costs, Decimal("98.00"))

    def test_gap_through_stop_exits_at_worse_open_and_target_caps_improvement(self):
        stopped = label_candidate(self.feature_row(), self.gap_bars(second_open="95"), self.costs)
        targeted = label_candidate(self.feature_row(), self.gap_bars(second_open="105"), self.costs)
        self.assertEqual(stopped.exit_price_before_costs, Decimal("95"))
        self.assertEqual(targeted.exit_price_before_costs, Decimal("103.00"))

    def test_each_cost_component_is_deducted_and_break_even_is_label_zero(self):
        result = label_candidate(self.feature_row(), self.flat_future_bars(10), self.costs)
        self.assertEqual(result.total_cost, sum(result.costs.to_values(), Decimal("0")))
        self.assertEqual(result.net_pnl, result.gross_pnl - result.total_cost)
        self.assertEqual(result.label, int(result.net_pnl > 0))
    def test_timing_boundary_is_explicit(self):
        future = self.flat_future_bars(10)
        result = label_candidate(self.feature_row(), future, self.costs)
        self.assertEqual(result.entry_date, self.feature_row().entry_eligible_at)
        self.assertEqual(result.label_end_at, future[9].trading_date)
```

- [ ] **Step 2: Run label tests and confirm the missing module failure**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_labels -v
```

Expected: FAIL because `market_sentinel.ml_labels` does not exist.

- [ ] **Step 3: Implement costs and deterministic fill ordering**

Use these exact contracts and order of operations:

```python
@dataclass(frozen=True)
class CostSchedule:
    effective_from: date
    commission_bps: Decimal
    regulatory_bps: Decimal
    tax_bps: Decimal
    spread_bps: Decimal
    slippage_bps: Decimal
    flat_fee: Decimal
    source_notes: str


@dataclass(frozen=True)
class CostProfile:
    market: str
    currency: str
    version: str
    schedules: tuple[CostSchedule, ...]


@dataclass(frozen=True)
class CostBreakdown:
    commission: Decimal
    regulatory: Decimal
    tax: Decimal
    spread: Decimal
    slippage: Decimal
    flat: Decimal

    def to_values(self) -> tuple[Decimal, ...]:
        return (self.commission, self.regulatory, self.tax, self.spread, self.slippage, self.flat)


@dataclass(frozen=True)
class MetaLabelRow:
    feature_row: FeatureRow
    label: int
    entry_date: date
    entry_price_before_costs: Decimal
    exit_date: date
    exit_price_before_costs: Decimal
    label_end_at: date
    holding_sessions: int
    exit_reason: str
    gross_pnl: Decimal
    costs: CostBreakdown
    total_cost: Decimal
    net_pnl: Decimal
    cost_profile_version: str


def select_cost_schedule(profile: CostProfile, trade_date: date) -> CostSchedule:
    effective_dates = [item.effective_from for item in profile.schedules]
    if len(effective_dates) != len(set(effective_dates)):
        raise ValueError("cost schedules cannot share an effective date")
    for item in profile.schedules:
        if not item.source_notes.strip() or min(item.commission_bps, item.regulatory_bps, item.tax_bps, item.spread_bps, item.slippage_bps, item.flat_fee) < 0:
            raise ValueError("cost schedules require source notes and non-negative values")
    eligible = [item for item in profile.schedules if item.effective_from <= trade_date]
    if not eligible:
        raise ValueError(f"no {profile.market} cost schedule effective on {trade_date.isoformat()}")
    return max(eligible, key=lambda item: item.effective_from)


def label_candidate(row: FeatureRow, future_bars: tuple[CanonicalDailyBar, ...], profile: CostProfile) -> MetaLabelRow:
    if (row.market, row.currency) != (profile.market, profile.currency):
        raise ValueError("cost profile market or currency mismatch")
    if len(future_bars) < 10 or future_bars[0].trading_date != row.entry_eligible_at:
        raise ValueError("future bars must begin at entry_eligible_at")
    schedule = select_cost_schedule(profile, future_bars[0].trading_date)
    entry = future_bars[0].open
    stop = entry * Decimal("0.98")
    target = entry * Decimal("1.03")
    exit_bar = future_bars[9]
    exit_price = exit_bar.close
    exit_reason = "maximum-hold"
    holding = 10
    for offset, item in enumerate(future_bars[:10], start=1):
        if item.open < stop:
            exit_bar, exit_price, exit_reason, holding = item, item.open, "stop", offset
            break
        if item.open >= target:
            exit_bar, exit_price, exit_reason, holding = item, target, "target", offset
            break
        if item.low <= stop:
            exit_bar, exit_price, exit_reason, holding = item, stop, "stop", offset
            break
        if item.high >= target:
            exit_bar, exit_price, exit_reason, holding = item, target, "target", offset
            break
    notional = entry + exit_price
    bps = Decimal("10000")
    costs = CostBreakdown(
        notional * schedule.commission_bps / bps,
        notional * schedule.regulatory_bps / bps,
        notional * schedule.tax_bps / bps,
        notional * schedule.spread_bps / bps,
        notional * schedule.slippage_bps / bps,
        schedule.flat_fee,
    )
    total_cost = sum(costs.to_values(), Decimal("0"))
    gross_pnl = exit_price - entry
    net_pnl = gross_pnl - total_cost
    return MetaLabelRow(row, int(net_pnl > 0), future_bars[0].trading_date, entry, exit_bar.trading_date,
        exit_price, exit_bar.trading_date, holding, exit_reason, gross_pnl, costs, total_cost, net_pnl, profile.version)
```

Entry spread/slippage and maximum-hold exit slippage are represented in `CostBreakdown`; they must never improve price. Near-dataset-end candidates with fewer than 10 future sessions remain unlabeled and cannot enter a fold.

- [ ] **Step 4: Run all label scenarios**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_labels -v
```

Expected: all cost, gap, same-bar, target, stop, 10-session exit, and timing tests pass.

- [ ] **Step 5: Commit Task 5**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/ml_labels.py tests/test_ml_labels.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add cost aware protected trade labels'
```

### Task 6: Purged Expanding Walk-Forward Folds

**Files:**
- Create: `market_sentinel/ml_validation.py`
- Create: `tests/test_ml_validation.py`

**Interfaces:**
- Consumes: chronological `tuple[MetaLabelRow, ...]` plus the complete exchange-session date sequence covering those rows.
- Produces: `WalkForwardConfig`, `FoldDefinition`, `build_walk_forward_folds(...)`, and `assert_oos_eligibility(...)`.

- [ ] **Step 1: Write failing fold-boundary tests**

```python
# tests/test_ml_validation.py
import unittest
from dataclasses import dataclass, replace
from datetime import date, timedelta

from market_sentinel.ml_validation import WalkForwardConfig, build_walk_forward_folds


@dataclass(frozen=True)
class StubFeature:
    feature_as_of: date


@dataclass(frozen=True)
class StubRow:
    feature_row: StubFeature
    label_end_at: date
    label: int


class MLValidationTest(unittest.TestCase):
    def make_rows(self, count: int) -> tuple[tuple[StubRow, ...], tuple[date, ...]]:
        sessions = tuple(date(2024, 1, 1) + timedelta(days=index) for index in range((count * 2) + 20))
        rows = tuple(StubRow(StubFeature(sessions[index * 2]), sessions[(index * 2) + 5], index % 2) for index in range(count))
        return rows, sessions

    def test_three_expanding_folds_have_two_ten_session_gaps(self):
        rows, sessions = self.make_rows(360)
        positions = {session: index for index, session in enumerate(sessions)}
        folds = build_walk_forward_folds(rows, sessions, WalkForwardConfig())
        self.assertGreaterEqual(len(folds), 3)
        for fold in folds:
            fit_end = rows[max(fold.fit_indices)].feature_row.feature_as_of
            calibration_start = rows[min(fold.calibration_indices)].feature_row.feature_as_of
            calibration_end = rows[max(fold.calibration_indices)].feature_row.feature_as_of
            test_start = rows[min(fold.test_indices)].feature_row.feature_as_of
            self.assertGreater(positions[calibration_start] - positions[fit_end], 10)
            self.assertGreater(positions[test_start] - positions[calibration_end], 10)
            self.assertGreaterEqual(len(fold.calibration_indices), 40)
            self.assertGreaterEqual(len(fold.test_indices), 30)

    def test_each_candidate_appears_in_only_one_test_fold(self):
        rows, sessions = self.make_rows(360)
        folds = build_walk_forward_folds(rows, sessions, WalkForwardConfig())
        test_indices = [index for fold in folds for index in fold.test_indices]
        self.assertEqual(len(test_indices), len(set(test_indices)))

    def test_label_horizon_may_not_cross_a_slice_boundary(self):
        original, sessions = self.make_rows(360)
        rows = list(original)
        rows[100] = replace(rows[100], label_end_at=rows[140].feature_row.feature_as_of)
        folds = build_walk_forward_folds(tuple(rows), sessions, WalkForwardConfig())
        for fold in folds:
            calibration_start = rows[min(fold.calibration_indices)].feature_row.feature_as_of
            self.assertTrue(all(rows[index].label_end_at < calibration_start for index in fold.fit_indices))
```

- [ ] **Step 2: Run fold tests and confirm the missing module failure**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_validation -v
```

Expected: FAIL because `market_sentinel.ml_validation` does not exist.

- [ ] **Step 3: Implement chronological fold construction**

```python
@dataclass(frozen=True)
class WalkForwardConfig:
    test_folds: int = 3
    gap_sessions: int = 10
    calibration_fraction: Decimal = Decimal("0.20")
    min_calibration_rows: int = 40
    min_test_rows: int = 30
    min_total_oos: int = 150
    min_positive: int = 30
    min_negative: int = 30


@dataclass(frozen=True)
class FoldDefinition:
    fold_id: str
    fit_indices: tuple[int, ...]
    calibration_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


def _both_classes(rows: tuple[MetaLabelRow, ...], indices: tuple[int, ...]) -> bool:
    return {rows[index].label for index in indices} == {0, 1}


def build_walk_forward_folds(
    rows: tuple[MetaLabelRow, ...],
    sessions: tuple[date, ...],
    config: WalkForwardConfig,
) -> tuple[FoldDefinition, ...]:
    if config.test_folds < 3:
        raise ValueError("at least three test folds are required")
    if tuple(sorted(rows, key=lambda item: item.feature_row.feature_as_of)) != rows:
        raise ValueError("walk-forward rows must be chronological")
    if tuple(sorted(set(sessions))) != sessions:
        raise ValueError("exchange sessions must be unique and chronological")
    positions = {session: index for index, session in enumerate(sessions)}
    if any(item.feature_row.feature_as_of not in positions for item in rows):
        raise ValueError("every candidate date must be an exchange session")
    test_size = max(config.min_test_rows, len(rows) // (config.test_folds + 3))
    first_test = len(rows) - (test_size * config.test_folds)
    folds: list[FoldDefinition] = []
    for fold_number in range(config.test_folds):
        test_start = first_test + (fold_number * test_size)
        test_stop = len(rows) if fold_number == config.test_folds - 1 else test_start + test_size
        test_start_date = rows[test_start].feature_row.feature_as_of
        calibration_latest_position = positions[test_start_date] - config.gap_sessions - 1
        if calibration_latest_position < 0:
            raise ValueError(f"fold-{fold_number + 1} has no calibration history before its gap")
        calibration_latest_date = sessions[calibration_latest_position]
        pretest_indices = tuple(index for index in range(test_start) if rows[index].feature_row.feature_as_of <= calibration_latest_date)
        calibration_size = max(config.min_calibration_rows, math.ceil(len(pretest_indices) * float(config.calibration_fraction)))
        calibration_indices = pretest_indices[-calibration_size:]
        if not calibration_indices:
            raise ValueError(f"fold-{fold_number + 1} has no calibration rows")
        calibration_start_date = rows[calibration_indices[0]].feature_row.feature_as_of
        fit_latest_position = positions[calibration_start_date] - config.gap_sessions - 1
        if fit_latest_position < 0:
            raise ValueError(f"fold-{fold_number + 1} has no fit history before its gap")
        fit_latest_date = sessions[fit_latest_position]
        fit_indices = tuple(index for index in range(calibration_indices[0]) if rows[index].feature_row.feature_as_of <= fit_latest_date and rows[index].label_end_at < calibration_start_date)
        calibration_indices = tuple(index for index in calibration_indices if rows[index].label_end_at < test_start_date)
        test_indices = tuple(range(test_start, test_stop))
        if not fit_indices or len(calibration_indices) < config.min_calibration_rows or len(test_indices) < config.min_test_rows:
            raise ValueError(f"fold-{fold_number + 1} does not meet row minimums")
        if not _both_classes(rows, fit_indices) or not _both_classes(rows, calibration_indices) or not _both_classes(rows, test_indices):
            raise ValueError(f"fold-{fold_number + 1} must contain both classes in every slice")
        folds.append(FoldDefinition(f"fold-{fold_number + 1}", fit_indices, calibration_indices, test_indices))
    return tuple(folds)


def assert_oos_eligibility(rows: tuple[MetaLabelRow, ...], folds: tuple[FoldDefinition, ...], config: WalkForwardConfig) -> None:
    indices = [index for fold in folds for index in fold.test_indices]
    if len(indices) != len(set(indices)):
        raise ValueError("test candidates must be predicted exactly once")
    labels = [rows[index].label for index in indices]
    if len(labels) < config.min_total_oos or labels.count(1) < config.min_positive or labels.count(0) < config.min_negative:
        raise ValueError("out-of-sample row or class minimum not met")
```

- [ ] **Step 4: Verify fold construction and minimum failures**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_validation -v
```

Expected: all fold tests pass, including explicit failures for fewer than 150 OOS rows, fewer than 30 members of either class, and fewer than three folds.

- [ ] **Step 5: Commit Task 6**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/ml_validation.py tests/test_ml_validation.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: add purged walk forward folds'
```

### Task 7: Fold-Local Logistic Training, Calibration, And JSON Artifacts

**Files:**
- Replace: `market_sentinel/model_training.py`
- Create: `tests/test_market_model_training.py`
- Remove obsolete ML assertions from: `tests/test_ml_training_and_scheduling.py`

**Interfaces:**
- Consumes: `MetaLabelRow`, `FoldDefinition`, `FEATURE_ORDER`, one `C`, and one threshold.
- Produces: `MarketModelArtifact`, `fit_fold_model(...)`, `predict_probability(...)`, `to_payload()`, and `from_payload(...)`.

- [ ] **Step 1: Write failing fit-locality, calibration, and serialization tests**

```python
# tests/test_market_model_training.py
import json
import unittest
from decimal import Decimal

from market_sentinel.model_training import MarketModelArtifact, fit_fold_model, predict_probability


class MarketModelTrainingTest(unittest.TestCase):
    def test_scaler_uses_fit_rows_only(self):
        fit_rows, calibration_rows = self.rows(fit_value=1, calibration_value=1000)
        artifact = fit_fold_model(fit_rows, calibration_rows, c_value=Decimal("1.0"), threshold=Decimal("0.60"), metadata=self.metadata())
        self.assertTrue(all(abs(value - 1.0) < 0.01 for value in artifact.scaler_mean))

    def test_probability_and_threshold_round_trip_through_plain_json(self):
        fit_rows, calibration_rows = self.rows(fit_value=1, calibration_value=2)
        artifact = fit_fold_model(fit_rows, calibration_rows, c_value=Decimal("0.1"), threshold=Decimal("0.65"), metadata=self.metadata())
        loaded = MarketModelArtifact.from_payload(json.loads(json.dumps(artifact.to_payload())))
        probability = predict_probability(loaded, calibration_rows[0].feature_row)
        self.assertGreaterEqual(probability, Decimal("0"))
        self.assertLessEqual(probability, Decimal("1"))
        self.assertEqual(loaded.threshold, Decimal("0.65"))

    def test_unknown_hyperparameter_or_threshold_is_rejected(self):
        fit_rows, calibration_rows = self.rows(fit_value=1, calibration_value=2)
        with self.assertRaises(ValueError):
            fit_fold_model(fit_rows, calibration_rows, c_value=Decimal("2.0"), threshold=Decimal("0.50"), metadata=self.metadata())
```

The helper `rows` must create both labels in fit and calibration. `metadata` must provide market, symbol, dataset checksum, schema versions, fold ranges, library version, and code commit.

- [ ] **Step 2: Run training tests and confirm old public surface fails**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_market_model_training -v
```

Expected: FAIL because `MarketModelArtifact` and `fit_fold_model` do not exist.

- [ ] **Step 3: Implement reproducible fitting and JSON-safe inference**

Define the artifact with these exact fields:

```python
@dataclass(frozen=True)
class MarketModelArtifact:
    version: str
    market: str
    symbol: str
    currency: str
    model_type: str
    sklearn_version: str
    feature_schema: str
    feature_order: tuple[str, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    fit_feature_deciles: dict[str, tuple[float, ...]]
    coefficients: tuple[float, ...]
    intercept: float
    calibrator_coefficient: float
    calibrator_intercept: float
    threshold: Decimal
    c_value: Decimal
    dataset_id: str
    dataset_checksum: str
    label_version: str
    cost_profile_version: str
    fit_range: tuple[str, str]
    calibration_range: tuple[str, str]
    test_ranges: tuple[tuple[str, str], ...]
    fold_metrics: tuple[dict[str, object], ...]
    aggregate_metrics: dict[str, object]
    promoted_for_paper: bool
    failure_reasons: tuple[str, ...]
    behavior_checksum: str
    created_at: str
    code_commit: str
    parent_champion_version: str | None
```

Fit with `StandardScaler()` and `LogisticRegression(C=float(c_value), solver="lbfgs", random_state=17, max_iter=1000)`. Call `scaler.fit_transform` only on fit rows. Fit a second `LogisticRegression(C=1_000_000.0, solver="lbfgs", random_state=17, max_iter=1000)` on the one-column fit-model decision scores of calibration rows. Persist only numeric parameters and metadata. Reconstruct inference without sklearn deserialization:

```python
def predict_probability(artifact: MarketModelArtifact, row: FeatureRow) -> Decimal:
    if (row.market, row.symbol, row.currency, row.feature_schema) != (artifact.market, artifact.symbol, artifact.currency, artifact.feature_schema):
        raise ValueError("feature row is incompatible with model artifact")
    raw_values = [float(row.values[name]) for name in artifact.feature_order]
    scaled = [(value - mean) / scale for value, mean, scale in zip(raw_values, artifact.scaler_mean, artifact.scaler_scale, strict=True)]
    decision = artifact.intercept + sum(coefficient * value for coefficient, value in zip(artifact.coefficients, scaled, strict=True))
    calibrated_logit = artifact.calibrator_intercept + (artifact.calibrator_coefficient * decision)
    probability = 1.0 / (1.0 + math.exp(-max(-709.0, min(709.0, calibrated_logit))))
    return Decimal(str(probability))
```

`behavior_checksum` is SHA-256 over canonical JSON containing feature schema/order, scaler values, coefficients/intercept, calibrator values, threshold, label/cost versions, and the 2 percent / 3 percent / 10-session protection defaults. `to_payload` must stringify Decimal fields, convert tuples to JSON arrays, and include every artifact field. `from_payload` must reject missing keys, non-finite values, a feature order other than `FEATURE_ORDER`, any `model_type` other than `sklearn-logistic-meta-v1`, or a recomputed behavior checksum mismatch.

- [ ] **Step 4: Run training and surviving scheduler tests**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_market_model_training tests.test_ml_training_and_scheduling -v
```

Expected: logistic tests and the unrelated scheduled-order tests pass; no test trains or loads a pickle/joblib artifact.

- [ ] **Step 5: Commit Task 7**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/model_training.py tests/test_market_model_training.py tests/test_ml_training_and_scheduling.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: train calibrated market meta labelers'
```

### Task 8: Chronological Replay, Promotion Gates, And Trial Ledger

**Files:**
- Create: `market_sentinel/ml_evaluation.py`
- Create: `market_sentinel/trial_ledger.py`
- Create: `tests/test_ml_evaluation.py`
- Create: `tests/test_trial_ledger_and_model_store.py`

**Interfaces:**
- Consumes: calibration rows/probabilities, fold rows, one-time OOS probabilities, frozen thresholds, and candidate trade outcomes.
- Produces: `CalibrationChoice`, `select_calibration_configuration(...)`, `ReplayMetrics`, `FoldMetrics`, `ValidationReport`, `evaluate_validation(...)`, `TrialRecord`, and `TrialLedger.append(...)`.

- [ ] **Step 1: Write failing promotion and append-only ledger tests**

```python
# tests/test_ml_evaluation.py
import inspect
import unittest
from decimal import Decimal

from market_sentinel.ml_evaluation import evaluate_validation, select_calibration_configuration


class MLEvaluationTest(unittest.TestCase):
    def test_configuration_selection_has_no_test_fold_input(self):
        rows = self.calibration_rows()
        probabilities = self.calibration_probabilities_by_c(rows)
        selected = select_calibration_configuration(rows, probabilities)
        self.assertIn(selected.c_value, {Decimal("0.1"), Decimal("1.0"), Decimal("10.0")})
        self.assertIn(selected.threshold, {Decimal("0.55"), Decimal("0.60"), Decimal("0.65")})
        self.assertNotIn("test", inspect.signature(select_calibration_configuration).parameters)

    def test_failed_mandatory_fold_cannot_be_averaged_away(self):
        folds = self.passing_folds()
        folds[1] = self.with_filtered_expectancy(folds[1], Decimal("-0.01"))
        report = evaluate_validation(folds, attempted_configurations=3)
        self.assertFalse(report.promoted_for_paper)
        self.assertIn("fold-2 filtered expectancy is not positive", report.failure_reasons)

    def test_all_promotion_gates_are_independent(self):
        report = evaluate_validation(self.passing_folds(), attempted_configurations=3)
        self.assertTrue(report.promoted_for_paper)
        self.assertEqual(report.attempted_configurations, 3)
        self.assertGreaterEqual(report.acceptance_coverage, Decimal("0.10"))
        self.assertLessEqual(report.acceptance_coverage, Decimal("0.80"))
```

```python
# tests/test_trial_ledger_and_model_store.py
import tempfile
import unittest
from pathlib import Path

from market_sentinel.trial_ledger import TrialLedger


class TrialLedgerTest(unittest.TestCase):
    def test_trial_ids_are_immutable_and_failed_trials_remain_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = TrialLedger(Path(directory) / "trials.jsonl")
            ledger.append(self.record("trial-1", promoted=False))
            with self.assertRaisesRegex(ValueError, "trial id already exists"):
                ledger.append(self.record("trial-1", promoted=True))
            self.assertEqual([item.trial_id for item in ledger.read_all()], ["trial-1"])
```

- [ ] **Step 2: Run evaluation and ledger tests and confirm missing modules**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_evaluation tests.test_trial_ledger_and_model_store -v
```

Expected: FAIL because evaluation and ledger modules do not exist.

- [ ] **Step 3: Implement replay metrics, mandatory gates, and atomic append**

Use an open-position gate in `replay_fold`: iterate chronologically, skip accepted signals while `feature_as_of <= open_trade.label_end_at`, and count only the completed protected outcomes as executable trades. Define:

```python
@dataclass(frozen=True)
class CalibrationChoice:
    c_value: Decimal
    threshold: Decimal
    expectancy: Decimal
    maximum_drawdown: Decimal
    brier_score: Decimal
    acceptance_coverage: Decimal


@dataclass(frozen=True)
class ReplayMetrics:
    completed_trades: int
    gross_return: Decimal
    net_return: Decimal
    total_costs: Decimal
    win_rate: Decimal | None
    expectancy: Decimal | None
    maximum_drawdown: Decimal


@dataclass(frozen=True)
class FoldMetrics:
    fold_id: str
    candidate_count: int
    positive_count: int
    negative_count: int
    accuracy: Decimal
    precision: Decimal | None
    recall: Decimal | None
    brier_score: Decimal
    training_prevalence: Decimal
    prevalence_brier_score: Decimal
    acceptance_coverage: Decimal
    rejected_candidates: int
    calibration_buckets: tuple[dict[str, object], ...]
    filtered: ReplayMetrics
    baseline: ReplayMetrics


@dataclass(frozen=True)
class ValidationReport:
    fold_metrics: tuple[FoldMetrics, ...]
    aggregate_metrics: dict[str, object]
    acceptance_coverage: Decimal
    attempted_configurations: int
    promoted_for_paper: bool
    failure_reasons: tuple[str, ...]


def select_calibration_configuration(
    rows: tuple[MetaLabelRow, ...],
    probabilities_by_c: dict[Decimal, tuple[Decimal, ...]],
) -> CalibrationChoice:
    allowed_c = (Decimal("0.1"), Decimal("1.0"), Decimal("10.0"))
    allowed_thresholds = (Decimal("0.55"), Decimal("0.60"), Decimal("0.65"))
    if set(probabilities_by_c) != set(allowed_c):
        raise ValueError("calibration must compare exactly the predeclared C values")
    choices: list[CalibrationChoice] = []
    for c_value in allowed_c:
        probabilities = probabilities_by_c[c_value]
        if len(probabilities) != len(rows):
            raise ValueError("calibration probability count mismatch")
        brier = sum((probability - Decimal(rows[index].label)) ** 2 for index, probability in enumerate(probabilities)) / Decimal(len(rows))
        for threshold in allowed_thresholds:
            accepted = tuple(probability >= threshold for probability in probabilities)
            coverage = Decimal(sum(accepted)) / Decimal(len(accepted))
            replay = replay_fold(rows, accepted)
            if Decimal("0.10") <= coverage <= Decimal("0.80") and replay.expectancy is not None:
                choices.append(CalibrationChoice(c_value, threshold, replay.expectancy, replay.maximum_drawdown, brier, coverage))
    if not choices:
        raise ValueError("no calibration configuration meets coverage and completed-trade requirements")
    return max(choices, key=lambda item: (item.expectancy, -item.maximum_drawdown, -item.brier_score, -item.c_value, item.threshold))
```

`evaluate_validation` must add a distinct failure reason for each failed rule: fewer than three folds, row/class minimum, undefined or non-positive filtered expectancy in any fold, aggregate filtered expectancy not above baseline, worse filtered drawdown in any fold, Brier not below the constant predictor formed from that fold's fit-slice `training_prevalence`, coverage below 0.10, or coverage above 0.80. Classification metrics use every OOS candidate exactly once; replay metrics use the position-state gate.

Implement the ledger as one canonical JSON object per line and flush plus `os.fsync` after append:

```python
class TrialLedger:
    def __init__(self, path: Path):
        self.path = path

    def append(self, record: TrialRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if record.trial_id in {item.trial_id for item in self.read_all()}:
            raise ValueError("trial id already exists")
        line = json.dumps(record.to_payload(), sort_keys=True, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def read_all(self) -> tuple[TrialRecord, ...]:
        if not self.path.exists():
            return ()
        return tuple(TrialRecord.from_payload(json.loads(line)) for line in self.path.read_text(encoding="utf-8").splitlines())
```

Use this exact ledger contract so selected and rejected calibration attempts remain visible:

```python
@dataclass(frozen=True)
class TrialRecord:
    trial_id: str
    stage: str
    market: str
    symbol: str
    dataset_id: str
    dataset_checksum: str
    dataset_range: tuple[str, str]
    feature_schema: str
    label_version: str
    cost_profile_version: str
    fold_definitions: tuple[dict[str, object], ...]
    c_value: Decimal
    threshold_candidates: tuple[Decimal, ...]
    selected_threshold: Decimal | None
    fold_metrics: tuple[dict[str, object], ...]
    aggregate_metrics: dict[str, object]
    promoted_for_paper: bool
    failure_reasons: tuple[str, ...]
    code_commit: str
    created_at: str
```

Set `stage` to `calibration-selection` for all nine predeclared attempts and `walk-forward-validation` for the frozen selected configuration. Calibration-selection records have calibration metrics and an empty `fold_metrics` tuple; only the selected configuration receives one-time test-fold metrics.

- [ ] **Step 4: Run evaluation and ledger tests**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_evaluation tests.test_trial_ledger_and_model_store -v
```

Expected: all replay, metric, gate, attempted-configuration, and immutable-ledger tests pass.

- [ ] **Step 5: Commit Task 8**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/ml_evaluation.py market_sentinel/trial_ledger.py tests/test_ml_evaluation.py tests/test_trial_ledger_and_model_store.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: audit walk forward promotion evidence'
```

### Task 9: Market-Specific Model Store, Runtime Drift, And Authority Boundary

**Files:**
- Replace: `market_sentinel/model_store.py`
- Replace: `market_sentinel/prediction.py`
- Create: `tests/test_ml_runtime_and_drift.py`
- Modify: `tests/test_trial_ledger_and_model_store.py`

**Interfaces:**
- Consumes: `MarketModelArtifact`, runtime `FeatureRow`, recent scored feature rows, expected dataset/schema identifiers.
- Produces: `ModelStore.save(...)`, `activate_for_paper(...)`, `load_active(...)`, `DriftState`, `MarketMLPredictionAgent.score(...)`, and sanitized blocked reasons.

- [ ] **Step 1: Write failing lane-isolation and drift tests**

```python
# tests/test_ml_runtime_and_drift.py
import inspect
import tempfile
import unittest
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from market_sentinel.model_store import ModelStore
from market_sentinel.prediction import MarketMLPredictionAgent


class MLRuntimeTest(unittest.TestCase):
    def test_active_pointers_are_market_and_symbol_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            store.save(self.artifact("US", "SPY", "spy-v1"))
            store.save(self.artifact("IN", "NIFTYBEES", "nifty-v1"))
            store.activate_for_paper("US", "SPY", "spy-v1")
            store.activate_for_paper("IN", "NIFTYBEES", "nifty-v1")
            self.assertEqual(store.load_active("US", "SPY", expected_schema="daily-meta-v1", expected_dataset_checksum="a" * 64).version, "spy-v1")
            self.assertEqual(store.load_active("IN", "NIFTYBEES", expected_schema="daily-meta-v1", expected_dataset_checksum="b" * 64).version, "nifty-v1")

    def test_eight_sigma_outlier_and_psi_above_point_two_five_block(self):
        agent = MarketMLPredictionAgent(self.artifact("US", "SPY", "spy-v1"))
        outlier = self.row(value=Decimal("9"))
        self.assertFalse(agent.score(outlier, history=(), expected_feature_as_of=outlier.feature_as_of).passed)
        shifted_history = tuple(self.row(value=Decimal("3")) for _ in range(60))
        current = self.row(value=Decimal("3"))
        prediction = agent.score(current, history=shifted_history, expected_feature_as_of=current.feature_as_of)
        self.assertFalse(prediction.passed)
        self.assertIn("material population drift", prediction.reasons)

    def test_stale_feature_date_blocks_candidate(self):
        agent = MarketMLPredictionAgent(self.artifact("US", "SPY", "spy-v1"))
        row = self.row(value=Decimal("0"))
        prediction = agent.score(row, history=(), expected_feature_as_of=row.feature_as_of + timedelta(days=1))
        self.assertEqual(prediction.reasons, ("stale or unexpected feature date",))

    def test_prediction_module_has_no_broker_or_execution_authority(self):
        source = inspect.getsource(__import__("market_sentinel.prediction", fromlist=["*"]))
        self.assertNotIn("market_sentinel.brokers", source)
        self.assertNotIn("ExecutionAgent", source)
        self.assertNotIn("place_order", source)
```

- [ ] **Step 2: Run runtime tests and confirm new interfaces fail**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_ml_runtime_and_drift tests.test_trial_ledger_and_model_store -v
```

Expected: FAIL because the old model store has one pointer and prediction is rule-based.

- [ ] **Step 3: Implement compatibility, outlier, PSI, and fail-closed scoring**

Store artifacts at `root/<market>/<symbol>/<version>.json` and pointers at `root/<market>/<symbol>/active-paper.txt`. Store the SHA-256 of each canonical artifact beside it as `<version>.sha256`. `activate_for_paper` must reject `promoted_for_paper=False`. `load_active(market, symbol, *, expected_schema, expected_dataset_checksum)` must reject market, symbol, feature schema, dataset checksum, sklearn major/minor version, and artifact checksum mismatches.

Use this prediction contract:

```python
@dataclass(frozen=True)
class Prediction:
    score: Decimal
    passed: bool
    model_version: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class DriftState:
    scored_candidates: int
    feature_psi: dict[str, Decimal]
    status: str


class MarketMLPredictionAgent:
    def __init__(self, artifact: MarketModelArtifact):
        self.artifact = artifact

    def score(
        self,
        row: FeatureRow,
        *,
        history: tuple[FeatureRow, ...],
        expected_feature_as_of: date,
    ) -> Prediction:
        try:
            if not self.artifact.promoted_for_paper:
                return Prediction(Decimal("0"), False, self.artifact.version, ("model is not promoted for paper",))
            if row.feature_as_of != expected_feature_as_of:
                return Prediction(Decimal("0"), False, self.artifact.version, ("stale or unexpected feature date",))
            if (row.market, row.symbol, row.currency, row.feature_schema) != (
                self.artifact.market, self.artifact.symbol, self.artifact.currency, self.artifact.feature_schema,
            ):
                return Prediction(Decimal("0"), False, self.artifact.version, ("feature row is incompatible with model",))
            for index, name in enumerate(self.artifact.feature_order):
                value = float(row.values[name])
                mean = self.artifact.scaler_mean[index]
                scale = self.artifact.scaler_scale[index]
                if not math.isfinite(value):
                    return Prediction(Decimal("0"), False, self.artifact.version, (f"non-finite feature: {name}",))
                if scale > 0 and abs(value - mean) > (8.0 * scale):
                    return Prediction(Decimal("0"), False, self.artifact.version, (f"hard outlier: {name}",))
            drift = population_drift(self.artifact, history)
            if drift.status == "blocked":
                return Prediction(Decimal("0"), False, self.artifact.version, ("material population drift",))
            probability = predict_probability(self.artifact, row)
            if probability < 0 or probability > 1:
                return Prediction(Decimal("0"), False, self.artifact.version, ("probability outside [0, 1]",))
            return Prediction(probability, probability >= self.artifact.threshold, self.artifact.version,
                () if probability >= self.artifact.threshold else ("below frozen threshold",))
        except (KeyError, ValueError, ArithmeticError, OverflowError) as exc:
            return Prediction(Decimal("0"), False, self.artifact.version, (f"model inference blocked: {type(exc).__name__}",))
```

`population_drift` returns `insufficient-history` before 60 rows. At 60 rows, calculate PSI against artifact decile proportions using epsilon `1e-6`; if any feature exceeds `Decimal("0.25")`, return `blocked`. Do not reduce the threshold or start retraining.

- [ ] **Step 4: Run model-store, drift, and authority tests**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_trial_ledger_and_model_store tests.test_ml_runtime_and_drift -v
```

Expected: all isolated-pointer, checksum, compatibility, missing-model, stale-feature, outlier, PSI, and source-boundary tests pass.

- [ ] **Step 5: Commit Task 9**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/model_store.py market_sentinel/prediction.py tests/test_trial_ledger_and_model_store.py tests/test_ml_runtime_and_drift.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: enforce market model runtime gates'
```

### Task 10: Research CLI Orchestration And Synthetic-Model Removal

**Files:**
- Modify: `market_sentinel/cli.py`
- Modify: `tests/test_operations.py`
- Modify: `tests/test_ml_training_and_scheduling.py`

**Interfaces:**
- Consumes: provider clients, dataset store, feature/label builders, folds, training, evaluation, ledger, and model store.
- Produces: `download-data`, `build-dataset`, `train-market-model`, `validate-market-model`, `promote-to-paper`, and `paper-status` commands.

- [ ] **Step 1: Write failing CLI isolation tests**

```python
# append to tests/test_operations.py
def test_train_market_model_requires_real_dataset_and_never_uses_synthetic_rows(self):
    with tempfile.TemporaryDirectory() as directory:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["train-market-model", "--market", "US", "--symbol", "SPY", "--dataset-id", "missing", "--data-root", directory])
    self.assertNotEqual(exit_code, 0)
    self.assertIn("dataset", output.getvalue().lower())
    self.assertNotIn("accuracy gate", output.getvalue().lower())


def test_historical_commands_do_not_import_or_construct_live_brokers(self):
    source = inspect.getsource(__import__("market_sentinel.cli", fromlist=["*"]))
    research_source = source[source.index("def _download_data"):source.index("def _submit_order")]
    self.assertNotIn("GrowwBrokerAdapter", research_source)
    self.assertNotIn("AlpacaBrokerAdapter", research_source)
    self.assertNotIn("ExecutionAgent", research_source)


def test_failed_validation_cannot_activate_paper_pointer(self):
    result = self.run_cli_with_failed_report(["promote-to-paper", "--market", "US", "--symbol", "SPY", "--version", "failed-v1"])
    self.assertEqual(result.exit_code, 1)
    self.assertFalse(result.active_pointer.exists())


def test_only_one_challenger_per_lane_per_calendar_month(self):
    records = (self.validation_trial("US", "SPY", created_at="2026-07-01T00:00:00+00:00"),)
    with self.assertRaisesRegex(RuntimeError, "challenger already created for 2026-07"):
        _assert_challenger_month_available(records, "US", "SPY", datetime(2026, 7, 20, tzinfo=timezone.utc))
```

- [ ] **Step 2: Run operations tests and confirm new commands are absent**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_operations -v
```

Expected: FAIL because `train-market-model` and `promote-to-paper` are invalid choices.

- [ ] **Step 3: Replace synthetic training with explicit research commands**

Delete `_training_dataset`, `_train_model`, `MODEL_PROMOTION_THRESHOLD`, and the old `train-model` parser. Add fixed lane choices and dispatch:

```python
LANES = {
    ("US", "SPY"): {"provider": "alpaca", "currency": "USD", "adjustment": "all"},
    ("IN", "NIFTYBEES"): {"provider": "groww", "currency": "INR", "adjustment": "provider-unspecified"},
}


def _lane(market: str, symbol: str) -> dict[str, str]:
    try:
        return LANES[(market, symbol)]
    except KeyError as exc:
        raise ValueError("only US/SPY and IN/NIFTYBEES are supported") from exc


def _add_lane_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--market", choices=["US", "IN"], required=True)
    parser.add_argument("--symbol", choices=["SPY", "NIFTYBEES"], required=True)


def _assert_challenger_month_available(
    records: tuple[TrialRecord, ...],
    market: str,
    symbol: str,
    as_of: datetime,
) -> None:
    month = as_of.strftime("%Y-%m")
    if any(
        record.stage == "walk-forward-validation"
        and record.market == market
        and record.symbol == symbol
        and record.created_at[:7] == month
        for record in records
    ):
        raise RuntimeError(f"challenger already created for {month}")


download_parser = subcommands.add_parser("download-data")
_add_lane_arguments(download_parser)
download_parser.add_argument("--start", required=True)
download_parser.add_argument("--end", required=True)
download_parser.add_argument("--data-root", default="data/datasets")

build_parser = subcommands.add_parser("build-dataset")
_add_lane_arguments(build_parser)
build_parser.add_argument("--dataset-id", required=True)
build_parser.add_argument("--cost-profile", required=True)
build_parser.add_argument("--corporate-action-record")
build_parser.add_argument("--data-root", default="data/datasets")

train_parser = subcommands.add_parser("train-market-model")
_add_lane_arguments(train_parser)
train_parser.add_argument("--dataset-id", required=True)
train_parser.add_argument("--data-root", default="data/datasets")
train_parser.add_argument("--model-root", default="data/models")
train_parser.add_argument("--trial-root", default="data/trials")

validate_parser = subcommands.add_parser("validate-market-model")
_add_lane_arguments(validate_parser)
validate_parser.add_argument("--version", required=True)
validate_parser.add_argument("--model-root", default="data/models")

promote_parser = subcommands.add_parser("promote-to-paper")
_add_lane_arguments(promote_parser)
promote_parser.add_argument("--version", required=True)
promote_parser.add_argument("--model-root", default="data/models")

paper_status_parser = subcommands.add_parser("paper-status")
_add_lane_arguments(paper_status_parser)
paper_status_parser.add_argument("--paper-root", default="data/paper")
```

Make `_download_data`, `_build_dataset`, `_train_market_model`, and `_validate_market_model` accept dependencies as keyword-only arguments in tests. They may construct only historical clients, not broker adapters. `_build_dataset` accepts an optional reviewed corporate-action JSON record containing `record_id`, `source_url`, and reconciled exchange dates; it passes those dates to canonical validation and persists only `record_id`. An unexplained provider-unspecified discontinuity remains blocked when that record is absent or does not cover the date. For each walk-forward fold, fit the three `C` values on the fit slice, fit each sigmoid calibrator on the calibration slice, evaluate the three thresholds on calibration only, and append all nine calibration-selection records. Freeze the single selected `C` and threshold before scoring that fold's test rows exactly once. Before creating a challenger, call `_assert_challenger_month_available`; save the result with the current active paper model as `parent_champion_version` without overwriting or activating that champion. A failed challenger leaves the pointer unchanged. `promote-to-paper` calls `ModelStore.activate_for_paper` only for a passing artifact, resets that lane's paper clock, and never changes live mode or broker readiness.

- [ ] **Step 4: Run CLI and old synthetic-regression tests**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_operations tests.test_ml_training_and_scheduling -v
```

Expected: all tests pass; `rg "_training_dataset|MODEL_PROMOTION_THRESHOLD|train-linear-model" market_sentinel tests` returns no matches.

- [ ] **Step 5: Commit Task 10**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/cli.py tests/test_operations.py tests/test_ml_training_and_scheduling.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: orchestrate real data model research'
```

### Task 11: Independent Paper Lanes And 60-Session Clocks

**Files:**
- Create: `market_sentinel/paper_validation.py`
- Create: `tests/test_paper_validation.py`
- Modify: `market_sentinel/ruflo.py`
- Modify: `tests/test_research_agents.py`

**Interfaces:**
- Consumes: active paper artifacts, candidate predictions, `ExecutionAgent`, `AlpacaBrokerAdapter`, and `MockBrokerAdapter` through injected factories.
- Produces: `PaperLaneState`, `PaperValidationStore.activate(...)`, `PaperValidationStore.observe_completed_session(...)`, `PaperCoordinator.submit_candidate(...)`, and sanitized status payloads.

- [ ] **Step 1: Write failing execution-target and session-clock tests**

```python
# tests/test_paper_validation.py
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from market_sentinel.historical_data import expected_sessions
from market_sentinel.paper_validation import PaperCoordinator, PaperValidationStore


class PaperValidationTest(unittest.TestCase):
    def test_spy_accepts_only_alpaca_paper_endpoint(self):
        coordinator = self.coordinator(alpaca_endpoint="https://paper-api.alpaca.markets")
        coordinator.submit_candidate(self.spy_candidate(), self.account(), [], now=self.now())
        self.assertEqual(coordinator.recording_broker.urls, ["https://paper-api.alpaca.markets/v2/orders"])
        with self.assertRaisesRegex(ValueError, "Alpaca paper endpoint required"):
            self.coordinator(alpaca_endpoint="https://api.alpaca.markets")

    def test_niftybees_uses_local_simulator_and_never_groww(self):
        coordinator = self.coordinator()
        coordinator.submit_candidate(self.nifty_candidate(), self.account(), [], now=self.now())
        self.assertEqual(coordinator.local_simulator.fills, 1)
        self.assertEqual(coordinator.groww_calls, 0)

    def test_lane_clocks_are_independent_cannot_backfill_and_restart_on_behavior_change(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PaperValidationStore(Path(directory))
            start = date(2026, 7, 17)
            store.activate("US", "SPY", "spy-v1", "behavior-a", start)
            sessions = expected_sessions("US", start + timedelta(days=1), date(2026, 12, 31))[:60]
            for session in sessions:
                store.observe_completed_session("US", "SPY", session)
            self.assertEqual(store.load("US", "SPY").sessions_observed, 60)
            self.assertEqual(store.load("IN", "NIFTYBEES"), None)
            store.activate("US", "SPY", "spy-v2", "behavior-b", sessions[-1] + timedelta(days=1))
            self.assertEqual(store.load("US", "SPY").sessions_observed, 0)

    def test_metadata_only_replacement_keeps_session_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PaperValidationStore(Path(directory))
            start = date(2026, 7, 17)
            store.activate("US", "SPY", "spy-v1", "behavior-a", start)
            store.observe_completed_session("US", "SPY", expected_sessions("US", start + timedelta(days=1), date(2026, 7, 31))[0])
            store.activate("US", "SPY", "spy-v1-metadata", "behavior-a", start)
            self.assertEqual(store.load("US", "SPY").sessions_observed, 1)

    def test_calibration_drift_waits_for_sixty_resolved_paper_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PaperValidationStore(Path(directory))
            store.activate("US", "SPY", "spy-v1", "behavior-a", date(2026, 7, 17))
            for index in range(59):
                store.record_resolved_prediction("US", "SPY", Decimal("0.60"), index % 2)
            self.assertEqual(store.load("US", "SPY").calibration_status, "insufficient-history")
            store.record_resolved_prediction("US", "SPY", Decimal("0.60"), 1)
            self.assertEqual(store.load("US", "SPY").calibration_status, "reported")
```

- [ ] **Step 2: Run paper tests and confirm the module is absent**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_paper_validation tests.test_research_agents -v
```

Expected: FAIL because `market_sentinel.paper_validation` does not exist.

- [ ] **Step 3: Implement paper-only routing and state**

```python
@dataclass(frozen=True)
class PaperLaneState:
    market: str
    symbol: str
    model_version: str
    behavior_checksum: str
    activated_on: date
    last_completed_session: date | None
    sessions_observed: int
    completed_outcomes: int
    prediction_coverage: Decimal
    realized_costs: Decimal
    maximum_drawdown: Decimal
    data_failures: int
    execution_rejects: int
    drift_status: str
    calibration_brier: Decimal | None
    calibration_status: str
    status: str


class PaperCoordinator:
    def __init__(self, *, settings: Settings, alpaca_paper_factory: Callable[[], BrokerAdapter], local_simulator: BrokerAdapter):
        if settings.mode != RuntimeMode.PAPER or settings.alpaca_live_trading_enabled or settings.alpaca_paper_trading_endpoint != "https://paper-api.alpaca.markets":
            raise ValueError("Alpaca paper endpoint required")
        self.settings = settings
        self.alpaca_paper_factory = alpaca_paper_factory
        self.local_simulator = local_simulator

    def broker_for(self, market: str, symbol: str) -> BrokerAdapter:
        if (market, symbol) == ("US", "SPY"):
            return self.alpaca_paper_factory()
        if (market, symbol) == ("IN", "NIFTYBEES"):
            return self.local_simulator
        raise ValueError("unsupported paper lane")

    def submit_candidate(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
        positions: list[Position],
        *,
        now: datetime,
    ) -> Decision:
        broker = self.broker_for(intent.market, intent.symbol)
        return ExecutionAgent(self.settings, broker).submit(intent, account, positions, now=now)
```

`PaperValidationStore.activate(market, symbol, model_version, behavior_checksum, activated_on)` creates state at zero sessions. A different behavior checksum resets the lane; a version change with the same behavior checksum updates metadata without resetting evidence. `observe_completed_session` increments once only when the supplied date is an expected exchange session after `activated_on` and after `last_completed_session`; it rejects dates before activation, historical bulk insertion, duplicate dates, and skipped unexplained sessions. `record_resolved_prediction(market, symbol, probability, label)` appends a sanitized outcome, validates probability in `[0, 1]` and label in `{0, 1}`, and reports Brier score plus calibration buckets only after 60 resolved outcomes. Before then, calibration status is `insufficient-history`; reporting never changes the frozen threshold. Lane `status` is `observing` through session 59 and `human-review-eligible` at session 60. That state must not modify runtime mode or broker readiness.

Update RUFLO output to read these states and report them. Add a source test proving `ruflo.py` contains no `activate_for_paper`, `place_order`, threshold mutation, or live-mode mutation.

- [ ] **Step 4: Run paper-lane and RUFLO tests**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_paper_validation tests.test_research_agents -v
```

Expected: all paper target, independent clock, non-backfill, model-replacement, and RUFLO authority tests pass.

- [ ] **Step 5: Commit Task 11**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/paper_validation.py market_sentinel/ruflo.py tests/test_paper_validation.py tests/test_research_agents.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: enforce independent paper validation lanes'
```

### Task 12: Separate Dashboard Evidence, Documentation, And Secret Safety

**Files:**
- Modify: `market_sentinel/cli.py`
- Modify: `tests/test_operations.py`
- Modify: `apps/control-center/app/page.tsx`
- Modify: `apps/control-center/public/status.json`
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**
- Consumes: per-lane model, dataset, validation, paper, and drift status.
- Produces: one sanitized `lanes` object for SPY and NIFTYBEES and a read-only dashboard.

- [ ] **Step 1: Write failing dashboard-contract tests**

```python
# append to tests/test_operations.py
def test_dashboard_exports_two_non_aggregated_sanitized_lanes(self):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "status.json"
        _export_dashboard(path, model_dir=Path(directory) / "models", data_root=Path(directory) / "datasets", paper_root=Path(directory) / "paper")
        payload = json.loads(path.read_text(encoding="utf-8"))
    self.assertEqual(set(payload["lanes"]), {"US:SPY", "IN:NIFTYBEES"})
    self.assertNotIn("ready_to_trade", json.dumps(payload).lower())
    self.assertNotIn("api_key", json.dumps(payload).lower())
    self.assertNotIn("secret", json.dumps(payload).lower())
    self.assertFalse(payload["lanes"]["US:SPY"]["paper"]["complete"])
    self.assertFalse(payload["lanes"]["IN:NIFTYBEES"]["paper"]["complete"])


def test_dashboard_has_no_order_submission_or_manual_readiness_control(self):
    source = Path("apps/control-center/app/page.tsx").read_text(encoding="utf-8").lower()
    self.assertNotIn("submit-order", source)
    self.assertNotIn("ready_to_trade", source)
    self.assertNotIn("place order", source)
```

- [ ] **Step 2: Run operations tests and confirm the old singular schema fails**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_operations -v
```

Expected: FAIL because the exported dashboard has singular `model` state and fabricated synthetic promotion data.

- [ ] **Step 3: Implement the read-only lane schema and update docs**

Export exactly this top-level shape from `_export_dashboard`:

```python
data = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "scope": "historical-validation-and-paper-only",
    "lanes": {
        "US:SPY": _lane_dashboard_status("US", "SPY", "Alpaca", "Alpaca paper", model_dir, data_root, paper_root),
        "IN:NIFTYBEES": _lane_dashboard_status("IN", "NIFTYBEES", "Groww", "local simulator", model_dir, data_root, paper_root),
    },
    "disclaimer": "Historical and paper results do not guarantee future performance. Real-money activation is outside this workflow.",
}
```

Each lane must contain `mode`, `execution_target`, `data` source/range/freshness/checksum, `model` version/schema/threshold, `validation` fold and aggregate metrics, modeled costs, drawdown, expectancy, coverage, `paper` sessions/60 and completion, `drift`, `data_quality`, and `blocked_reasons`. Missing files render blocked reasons; they do not crash export or synthesize successful metrics.

Render two sibling lane sections in `page.tsx`, each with compact tables for validation and paper evidence. Do not add buttons, forms, editable inputs, direct broker links, order controls, credential values, profit claims, or a combined readiness result.

Replace `apps/control-center/public/status.json` with a generated blocked example: no active models, zero paper sessions, no accuracy value, and explicit `data-not-downloaded` / `model-not-validated` reasons for both lanes.

Document these commands in `README.md` using environment-provided credentials and no literal values: `download-data`, `build-dataset`, `train-market-model`, `validate-market-model`, `promote-to-paper`, `paper-status`, and `export-dashboard`. State that the build does not guarantee outcomes and stops at paper evidence. Add historical endpoint variables to `.env.example` but do not add real values; retain the existing local secret-entry instructions.

- [ ] **Step 4: Run Python tests and build the dashboard**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_operations -v
npm --prefix apps/control-center run build
```

Expected: operations tests pass and Next.js exits with code 0. Visually inspect desktop and 390px mobile widths; lane sections remain readable, no text overlaps, and there is no order or readiness control.

- [ ] **Step 5: Commit Task 12**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add market_sentinel/cli.py tests/test_operations.py apps/control-center/app/page.tsx apps/control-center/public/status.json README.md .env.example
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'feat: show isolated paper model evidence'
```

### Task 13: End-To-End Safety Regression And Verification

**Files:**
- Modify: `tests/test_operations.py`
- Modify: `tests/test_brokers_execution_and_alerts.py`
- Modify: `tests/test_research_agents.py`

**Interfaces:**
- Consumes: the complete historical, ML, paper, CLI, and dashboard system.
- Produces: executable acceptance evidence without any real-money broker submission.

- [ ] **Step 1: Add the end-to-end paper-only regression**

```python
def test_dual_lane_research_to_paper_never_calls_live_order_endpoint(self):
    harness = DualLaneHarness.with_realistic_daily_fixtures(
        spy_sessions=420,
        niftybees_sessions=420,
        oos_candidates_per_lane=180,
    )
    spy = harness.run_lane("US", "SPY")
    nifty = harness.run_lane("IN", "NIFTYBEES")
    self.assertEqual(spy.execution_target, "alpaca-paper")
    self.assertEqual(nifty.execution_target, "local-simulator")
    self.assertNotEqual(spy.dataset_id, nifty.dataset_id)
    self.assertNotEqual(spy.model_version, nifty.model_version)
    self.assertEqual(harness.live_endpoint_calls, [])
    self.assertEqual(harness.groww_order_calls, [])
    self.assertNotIn("I_CONFIRM_REAL_MONEY_ORDER", harness.invocations)
```

Build `DualLaneHarness` entirely from fake historical HTTP responses, deterministic bar fixtures, temporary directories, an Alpaca paper recording adapter, and `MockBrokerAdapter`. It must not read process credentials or use network access.

- [ ] **Step 2: Run the new end-to-end regression**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_operations.OperationsTest.test_dual_lane_research_to_paper_never_calls_live_order_endpoint -v
```

Expected: PASS with zero live Alpaca endpoint calls and zero Groww order calls.

- [ ] **Step 3: Run static safety scans**

Run:

```powershell
rg -n "api[_-]?key|secret[_-]?key|access[_-]?token|Authorization" data apps/control-center/public/status.json
rg -n "pickle|joblib\.load|api\.alpaca\.markets/v2/orders|historical/candle/range" market_sentinel tests
rg -n "_training_dataset|MODEL_PROMOTION_THRESHOLD|accuracy gate|never losing|guaranteed profit" market_sentinel apps README.md
```

Expected: the first command finds no runtime artifacts or dashboard credentials; the second finds only explicit rejection/safety assertions and no model deserialization or research call to a live order endpoint; the third finds no synthetic promotion or performance claims.

- [ ] **Step 4: Run the complete verification suite**

Run:

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
npm --prefix apps/control-center run build
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' diff --check
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' status --short
```

Expected: all Python tests pass, dashboard build exits 0, `git diff --check` prints nothing, and status lists only the intended test changes from this task.

- [ ] **Step 5: Commit final verification coverage**

```powershell
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' add tests/test_operations.py tests/test_brokers_execution_and_alerts.py tests/test_research_agents.py
& 'C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' commit -m 'test: verify dual market paper safety'
```

## Final Acceptance Checklist

- [ ] Synthetic rows cannot train or activate a model.
- [ ] SPY and NIFTYBEES download, normalize, store, train, validate, and report independently.
- [ ] Features, scaling, calibration, thresholds, and test predictions respect point-in-time boundaries.
- [ ] Cost-aware labels use the approved conservative fill rules.
- [ ] All walk-forward minimums and mandatory promotion gates are executable tests.
- [ ] Failed trials remain in the immutable ledger and failed models cannot become paper-active.
- [ ] Runtime incompatibility, stale data, inference failure, eight-sigma outliers, and PSI above `0.25` block entries.
- [ ] SPY paper execution can reach only `https://paper-api.alpaca.markets`.
- [ ] NIFTYBEES paper execution can reach only the local simulator and never a Groww order operation.
- [ ] Paper clocks are independent, begin at activation, require 60 completed sessions, and cannot be backfilled.
- [ ] Dashboard and CLI expose sanitized per-lane evidence without a manual trading-readiness or order control.
- [ ] RUFLO and ML have no discretionary broker, promotion, threshold, sizing, or runtime authority.
- [ ] The full Python suite and dashboard build pass without submitting a real-money order.
