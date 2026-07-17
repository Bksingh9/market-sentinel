import tempfile
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from market_sentinel.dataset_store import DatasetStore
from market_sentinel.historical_data import AdjustmentMode, CanonicalDailyBar


def one_bar(
    symbol: str,
    market: str,
    currency: str,
    checksum: str,
) -> CanonicalDailyBar:
    return CanonicalDailyBar(
        "alpaca" if market == "US" else "groww",
        symbol,
        symbol,
        market,
        currency,
        date(2026, 7, 16),
        "America/New_York" if market == "US" else "Asia/Kolkata",
        Decimal("100"),
        Decimal("102"),
        Decimal("99"),
        Decimal("101"),
        1000,
        AdjustmentMode.ALL
        if market == "US"
        else AdjustmentMode.PROVIDER_UNSPECIFIED,
        datetime(2026, 7, 17, tzinfo=timezone.utc),
        checksum,
    )


class DatasetStoreTest(unittest.TestCase):
    def test_write_is_content_addressed_and_existing_artifact_is_not_mutated(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DatasetStore(Path(directory))
            first = store.write(
                (one_bar("SPY", "US", "USD", "a" * 64),),
                requested_start=date(2026, 7, 1),
                requested_end=date(2026, 7, 16),
                interval="1Day",
                page_count=1,
                feed="iex",
            )
            second = store.write(
                (one_bar("SPY", "US", "USD", "a" * 64),),
                requested_start=date(2026, 7, 1),
                requested_end=date(2026, 7, 16),
                interval="1Day",
                page_count=1,
                feed="iex",
            )
            self.assertEqual(first.manifest.dataset_id, second.manifest.dataset_id)
            self.assertEqual(first.bars_path.read_bytes(), second.bars_path.read_bytes())

    def test_market_paths_and_checksums_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DatasetStore(Path(directory))
            spy = store.write(
                (one_bar("SPY", "US", "USD", "a" * 64),),
                requested_start=date(2026, 7, 1),
                requested_end=date(2026, 7, 16),
                interval="1Day",
                page_count=1,
                feed="iex",
            )
            nifty = store.write(
                (one_bar("NIFTYBEES", "IN", "INR", "b" * 64),),
                requested_start=date(2026, 7, 1),
                requested_end=date(2026, 7, 16),
                interval="1Day",
                page_count=1,
                feed=None,
            )
            self.assertNotEqual(spy.manifest.dataset_id, nifty.manifest.dataset_id)
            self.assertIn("US", str(spy.bars_path))
            self.assertIn("IN", str(nifty.bars_path))

    def test_load_rejects_tampered_bar_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DatasetStore(Path(directory))
            stored = store.write(
                (one_bar("SPY", "US", "USD", "a" * 64),),
                requested_start=date(2026, 7, 1),
                requested_end=date(2026, 7, 16),
                interval="1Day",
                page_count=1,
                feed="iex",
            )
            encoded = stored.bars_path.read_bytes()
            stored.bars_path.write_bytes(encoded.replace(b'"volume":1000', b'"volume":1001'))
            with self.assertRaisesRegex(ValueError, "dataset checksum mismatch"):
                store.load("US", "SPY", stored.manifest.dataset_id)


if __name__ == "__main__":
    unittest.main()
