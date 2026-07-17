from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from market_sentinel.historical_data import CanonicalDailyBar


FEATURE_SCHEMA_VERSION = "daily-meta-v1"
FEATURE_ORDER = (
    "return_5",
    "return_20",
    "return_60",
    "volatility_20",
    "close_vs_ma_20",
    "close_vs_ma_60",
    "volume_vs_average_20",
    "drawdown_60",
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
        daily_returns = [
            (closes[position] / closes[position - 1]) - Decimal("1")
            for position in range(index - 19, index + 1)
        ]
        mean_return = _mean(daily_returns)
        variance = sum(
            (value - mean_return) ** 2 for value in daily_returns
        ) / Decimal(len(daily_returns) - 1)
        values = {
            "return_5": (closes[-1] / closes[-6]) - Decimal("1"),
            "return_20": (closes[-1] / closes[-21]) - Decimal("1"),
            "return_60": (closes[-1] / closes[-61]) - Decimal("1"),
            "volatility_20": variance.sqrt(),
            "close_vs_ma_20": (closes[-1] / _mean(closes[-20:]))
            - Decimal("1"),
            "close_vs_ma_60": (closes[-1] / _mean(closes[-60:]))
            - Decimal("1"),
            "volume_vs_average_20": volumes[-1] / _mean(volumes[-20:]),
            "drawdown_60": (closes[-1] / max(closes[-60:]))
            - Decimal("1"),
        }
        entry_eligible_at = (
            bars[index + 1].trading_date
            if index + 1 < len(bars)
            else next_session
        )
        if entry_eligible_at is None:
            raise ValueError("latest feature row requires its next exchange session")
        rows.append(
            FeatureRow(
                bars[index].symbol,
                bars[index].market,
                bars[index].currency,
                bars[index].trading_date,
                entry_eligible_at,
                FEATURE_SCHEMA_VERSION,
                closes[-1],
                volumes[-1],
                _mean(volumes[-20:]),
                values,
            )
        )
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
