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


def bar(day: date, *, high: str = "102") -> CanonicalDailyBar:
    return CanonicalDailyBar(
        provider="alpaca",
        provider_symbol="SPY",
        symbol="SPY",
        market="US",
        currency="USD",
        trading_date=day,
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

    def test_nse_calendar_excludes_weekend(self):
        sessions = expected_sessions("IN", date(2026, 7, 17), date(2026, 7, 20))
        self.assertEqual(sessions, (date(2026, 7, 17), date(2026, 7, 20)))

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
        first = replace(
            bar(date(2026, 7, 15)),
            provider="groww",
            provider_symbol="NSE-NIFTYBEES",
            symbol="NIFTYBEES",
            market="IN",
            currency="INR",
            source_timezone="Asia/Kolkata",
            adjustment_mode=AdjustmentMode.PROVIDER_UNSPECIFIED,
        )
        second = replace(
            first,
            trading_date=date(2026, 7, 16),
            open=Decimal("50"),
            high=Decimal("51"),
            low=Decimal("49"),
            close=Decimal("50"),
        )
        with self.assertRaisesRegex(ValueError, "unreconciled distribution discontinuity"):
            validate_daily_bars(
                (first, second),
                expected_symbol="NIFTYBEES",
                expected_market="IN",
                expected_currency="INR",
                expected_adjustment=AdjustmentMode.PROVIDER_UNSPECIFIED,
                last_completed_session=date(2026, 7, 16),
            )


if __name__ == "__main__":
    unittest.main()
