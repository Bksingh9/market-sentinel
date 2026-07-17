from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from market_sentinel.historical_data import CanonicalDailyBar
from market_sentinel.ml_features import FeatureRow


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
        return (
            self.commission,
            self.regulatory,
            self.tax,
            self.spread,
            self.slippage,
            self.flat,
        )


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
        values = (
            item.commission_bps,
            item.regulatory_bps,
            item.tax_bps,
            item.spread_bps,
            item.slippage_bps,
            item.flat_fee,
        )
        if not item.source_notes.strip() or min(values) < 0:
            raise ValueError(
                "cost schedules require source notes and non-negative values"
            )
    eligible = [
        item for item in profile.schedules if item.effective_from <= trade_date
    ]
    if not eligible:
        raise ValueError(
            f"no {profile.market} cost schedule effective on "
            f"{trade_date.isoformat()}"
        )
    return max(eligible, key=lambda item: item.effective_from)


def label_candidate(
    row: FeatureRow,
    future_bars: tuple[CanonicalDailyBar, ...],
    profile: CostProfile,
) -> MetaLabelRow:
    if (row.market, row.currency) != (profile.market, profile.currency):
        raise ValueError("cost profile market or currency mismatch")
    if (
        len(future_bars) < 10
        or future_bars[0].trading_date != row.entry_eligible_at
    ):
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
            exit_bar, exit_price, exit_reason, holding = (
                item,
                item.open,
                "stop",
                offset,
            )
            break
        if item.open >= target:
            exit_bar, exit_price, exit_reason, holding = (
                item,
                target,
                "target",
                offset,
            )
            break
        if item.low <= stop:
            exit_bar, exit_price, exit_reason, holding = (
                item,
                stop,
                "stop",
                offset,
            )
            break
        if item.high >= target:
            exit_bar, exit_price, exit_reason, holding = (
                item,
                target,
                "target",
                offset,
            )
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
    return MetaLabelRow(
        row,
        int(net_pnl > 0),
        future_bars[0].trading_date,
        entry,
        exit_bar.trading_date,
        exit_price,
        exit_bar.trading_date,
        holding,
        exit_reason,
        gross_pnl,
        costs,
        total_cost,
        net_pnl,
        profile.version,
    )
