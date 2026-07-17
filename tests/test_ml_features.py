import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from market_sentinel.historical_data import AdjustmentMode, CanonicalDailyBar
from market_sentinel.ml_features import (
    CandidateRule,
    build_feature_rows,
    is_market_candidate,
)


def bars(count: int) -> tuple[CanonicalDailyBar, ...]:
    start = date(2026, 1, 1)
    return tuple(
        CanonicalDailyBar(
            "alpaca",
            "SPY",
            "SPY",
            "US",
            "USD",
            start + timedelta(days=index),
            "America/New_York",
            Decimal(100 + index),
            Decimal(102 + index),
            Decimal(99 + index),
            Decimal(101 + index),
            1000 + index,
            AdjustmentMode.ALL,
            datetime(2026, 7, 17, tzinfo=timezone.utc),
            "a" * 64,
        )
        for index in range(count)
    )


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
        changed_future[61] = CanonicalDailyBar(
            **{**changed_future[61].__dict__, "close": Decimal("9999")}
        )
        changed_rows = build_feature_rows(
            tuple(changed_future),
            next_session=next_session,
        )
        self.assertEqual(rows[0].values, changed_rows[0].values)

    def test_exact_returns_and_candidate_rule(self):
        row = build_feature_rows(bars(62))[0]
        self.assertEqual(
            row.values["return_5"],
            (Decimal("161") / Decimal("156")) - Decimal("1"),
        )
        self.assertTrue(
            is_market_candidate(
                row,
                CandidateRule(Decimal("1000"), Decimal("1")),
            )
        )


if __name__ == "__main__":
    unittest.main()
