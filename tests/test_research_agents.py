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
