import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from market_sentinel.historical_data import AdjustmentMode, CanonicalDailyBar
from market_sentinel.ml_features import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, FeatureRow
from market_sentinel.ml_labels import CostProfile, CostSchedule, label_candidate


class MLLabelsTest(unittest.TestCase):
    def setUp(self):
        self.costs = CostProfile(
            "US",
            "USD",
            "us-cost-v1",
            (
                CostSchedule(
                    date(2020, 1, 1),
                    Decimal("0"),
                    Decimal("1"),
                    Decimal("2"),
                    Decimal("3"),
                    Decimal("4"),
                    Decimal("1.00"),
                    "test schedule",
                ),
            ),
        )

    def feature_row(self) -> FeatureRow:
        return FeatureRow(
            "SPY",
            "US",
            "USD",
            date(2026, 7, 15),
            date(2026, 7, 16),
            FEATURE_SCHEMA_VERSION,
            Decimal("100"),
            Decimal("10000"),
            Decimal("9000"),
            {name: Decimal("0.1") for name in FEATURE_ORDER},
        )

    def canonical_bar(
        self,
        offset: int,
        open_price: str,
        high: str,
        low: str,
        close: str,
    ) -> CanonicalDailyBar:
        return CanonicalDailyBar(
            "alpaca",
            "SPY",
            "SPY",
            "US",
            "USD",
            date(2026, 7, 16) + timedelta(days=offset),
            "America/New_York",
            Decimal(open_price),
            Decimal(high),
            Decimal(low),
            Decimal(close),
            10000,
            AdjustmentMode.ALL,
            datetime(2026, 7, 17, tzinfo=timezone.utc),
            "a" * 64,
        )

    def future_bars(
        self,
        *,
        open_price: str,
        high: str,
        low: str,
    ) -> tuple[CanonicalDailyBar, ...]:
        first = self.canonical_bar(0, open_price, high, low, open_price)
        rest = tuple(
            self.canonical_bar(index, open_price, open_price, open_price, open_price)
            for index in range(1, 10)
        )
        return (first, *rest)

    def gap_bars(self, *, second_open: str) -> tuple[CanonicalDailyBar, ...]:
        entry = self.canonical_bar(0, "100", "101", "99", "100")
        gap = self.canonical_bar(
            1,
            second_open,
            second_open,
            second_open,
            second_open,
        )
        rest = tuple(
            self.canonical_bar(
                index,
                second_open,
                second_open,
                second_open,
                second_open,
            )
            for index in range(2, 10)
        )
        return (entry, gap, *rest)

    def flat_future_bars(self, count: int) -> tuple[CanonicalDailyBar, ...]:
        return tuple(
            self.canonical_bar(index, "100", "101", "99", "100")
            for index in range(count)
        )

    def test_same_bar_stop_and_target_uses_stop_first(self):
        result = label_candidate(
            self.feature_row(),
            self.future_bars(open_price="100", high="104", low="97"),
            self.costs,
        )
        self.assertEqual(result.exit_reason, "stop")
        self.assertEqual(result.exit_price_before_costs, Decimal("98.00"))

    def test_gap_through_stop_exits_at_worse_open_and_target_caps_improvement(self):
        stopped = label_candidate(
            self.feature_row(),
            self.gap_bars(second_open="95"),
            self.costs,
        )
        targeted = label_candidate(
            self.feature_row(),
            self.gap_bars(second_open="105"),
            self.costs,
        )
        self.assertEqual(stopped.exit_price_before_costs, Decimal("95"))
        self.assertEqual(targeted.exit_price_before_costs, Decimal("103.00"))

    def test_each_cost_component_is_deducted_and_break_even_is_label_zero(self):
        result = label_candidate(
            self.feature_row(),
            self.flat_future_bars(10),
            self.costs,
        )
        self.assertEqual(
            result.total_cost,
            sum(result.costs.to_values(), Decimal("0")),
        )
        self.assertEqual(result.net_pnl, result.gross_pnl - result.total_cost)
        self.assertEqual(result.label, int(result.net_pnl > 0))

    def test_timing_boundary_is_explicit(self):
        future = self.flat_future_bars(10)
        result = label_candidate(self.feature_row(), future, self.costs)
        self.assertEqual(result.entry_date, self.feature_row().entry_eligible_at)
        self.assertEqual(result.label_end_at, future[9].trading_date)

    def test_fewer_than_ten_future_sessions_cannot_be_labeled(self):
        with self.assertRaisesRegex(ValueError, "must begin at entry_eligible_at"):
            label_candidate(
                self.feature_row(),
                self.flat_future_bars(9),
                self.costs,
            )


if __name__ == "__main__":
    unittest.main()
