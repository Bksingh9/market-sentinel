import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.historical_data import expected_sessions
from market_sentinel.models import (
    AccountSnapshot,
    Fill,
    InstrumentType,
    OrderIntent,
    Side,
)
from market_sentinel.paper_validation import PaperCoordinator, PaperValidationStore


class RecordingPaperBroker:
    name = "alpaca"

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.urls: list[str] = []

    def place_order(self, intent: OrderIntent) -> Fill:
        self.urls.append(f"{self.endpoint}/v2/orders")
        return Fill(
            intent.symbol,
            intent.side,
            intent.quantity,
            intent.limit_price,
            Decimal("0"),
            datetime.now(timezone.utc),
        )


class RecordingLocalSimulator:
    name = "mock"

    def __init__(self):
        self.fills = 0

    def place_order(self, intent: OrderIntent) -> Fill:
        self.fills += 1
        return Fill(
            intent.symbol,
            intent.side,
            intent.quantity,
            intent.limit_price,
            Decimal("0"),
            datetime.now(timezone.utc),
        )


class PaperValidationTest(unittest.TestCase):
    def test_spy_accepts_only_alpaca_paper_endpoint(self):
        coordinator = self.coordinator(
            alpaca_endpoint="https://paper-api.alpaca.markets"
        )
        coordinator.submit_candidate(
            self.candidate("US", "SPY"),
            self.account(),
            [],
            now=self.now(),
        )
        self.assertEqual(
            coordinator.recording_broker.urls,
            ["https://paper-api.alpaca.markets/v2/orders"],
        )
        with self.assertRaisesRegex(ValueError, "Alpaca paper endpoint required"):
            self.coordinator(alpaca_endpoint="https://api.alpaca.markets")

    def test_niftybees_uses_local_simulator_and_never_groww(self):
        coordinator = self.coordinator()
        coordinator.submit_candidate(
            self.candidate("IN", "NIFTYBEES"),
            self.account(),
            [],
            now=self.now(),
        )
        self.assertEqual(coordinator.local_simulator.fills, 1)
        self.assertEqual(coordinator.groww_calls, 0)

    def test_lane_clocks_are_independent_and_restart_on_behavior_change(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PaperValidationStore(Path(directory))
            start = date(2026, 7, 17)
            store.activate("US", "SPY", "spy-v1", "behavior-a", start)
            sessions = expected_sessions(
                "US",
                start + timedelta(days=1),
                date(2026, 12, 31),
            )[:60]
            for session in sessions:
                store.observe_completed_session("US", "SPY", session)
            self.assertEqual(store.load("US", "SPY").sessions_observed, 60)
            self.assertIsNone(store.load("IN", "NIFTYBEES"))
            store.activate(
                "US",
                "SPY",
                "spy-v2",
                "behavior-b",
                sessions[-1] + timedelta(days=1),
            )
            self.assertEqual(store.load("US", "SPY").sessions_observed, 0)

    def test_metadata_only_replacement_keeps_session_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PaperValidationStore(Path(directory))
            start = date(2026, 7, 17)
            store.activate("US", "SPY", "spy-v1", "behavior-a", start)
            session = expected_sessions(
                "US",
                start + timedelta(days=1),
                date(2026, 7, 31),
            )[0]
            store.observe_completed_session("US", "SPY", session)
            store.activate(
                "US",
                "SPY",
                "spy-v1-metadata",
                "behavior-a",
                start,
            )
            self.assertEqual(store.load("US", "SPY").sessions_observed, 1)

    def test_calibration_drift_waits_for_sixty_resolved_paper_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PaperValidationStore(Path(directory))
            store.activate(
                "US",
                "SPY",
                "spy-v1",
                "behavior-a",
                date(2026, 7, 17),
            )
            for index in range(59):
                store.record_resolved_prediction(
                    "US",
                    "SPY",
                    Decimal("0.60"),
                    index % 2,
                )
            self.assertEqual(
                store.load("US", "SPY").calibration_status,
                "insufficient-history",
            )
            store.record_resolved_prediction(
                "US",
                "SPY",
                Decimal("0.60"),
                1,
            )
            self.assertEqual(
                store.load("US", "SPY").calibration_status,
                "reported",
            )

    def coordinator(
        self,
        alpaca_endpoint: str = "https://paper-api.alpaca.markets",
    ) -> PaperCoordinator:
        settings = Settings(
            mode=RuntimeMode.PAPER,
            alpaca_paper_trading_endpoint=alpaca_endpoint,
        )
        recording = RecordingPaperBroker(alpaca_endpoint)
        local = RecordingLocalSimulator()
        coordinator = PaperCoordinator(
            settings=settings,
            alpaca_paper_factory=lambda: recording,
            local_simulator=local,
        )
        coordinator.recording_broker = recording
        coordinator.groww_calls = 0
        return coordinator

    @staticmethod
    def candidate(market: str, symbol: str) -> OrderIntent:
        return OrderIntent(
            symbol=symbol,
            market=market,
            instrument_type=InstrumentType.ETF,
            side=Side.BUY,
            quantity=Decimal("1"),
            limit_price=Decimal("100"),
            stop_loss=Decimal("98"),
            take_profit=Decimal("103"),
            strategy_id="paper-validation",
        )

    @staticmethod
    def account() -> AccountSnapshot:
        return AccountSnapshot("paper-local", Decimal("100000"), Decimal("100000"))

    @staticmethod
    def now() -> datetime:
        return datetime(2026, 7, 17, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
