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
    schedule = mcal.get_calendar(calendar_name).schedule(
        start_date=start,
        end_date=end,
    )
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
            if (
                opening_gap >= Decimal("0.35")
                and item.trading_date not in reconciled_discontinuity_dates
            ):
                raise ValueError(
                    "unreconciled distribution discontinuity on "
                    f"{item.trading_date.isoformat()}"
                )
        dates.append(item.trading_date)
        previous = item
    if dates != sorted(set(dates)):
        raise ValueError("trading dates must be unique and strictly increasing")
    expected = expected_sessions(expected_market, dates[0], dates[-1])
    actual_dates = set(dates)
    missing = [day for day in expected if day not in actual_dates]
    if missing:
        rendered = ", ".join(day.isoformat() for day in missing)
        raise ValueError(f"missing exchange sessions: {rendered}")
    return bars
