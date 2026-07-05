import unittest
from datetime import datetime, timezone
from decimal import Decimal

from market_sentinel.compliance import ComplianceGuard
from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.models import AccountSnapshot, InstrumentType, OrderIntent, Position, Side
from market_sentinel.risk import RiskAgent


def protected_intent(symbol="SPY", market="US", instrument_type=InstrumentType.ETF):
    return OrderIntent(
        symbol=symbol,
        market=market,
        instrument_type=instrument_type,
        side=Side.BUY,
        quantity=Decimal("1"),
        limit_price=Decimal("500"),
        stop_loss=Decimal("490"),
        take_profit=Decimal("515"),
        strategy_id="momentum-long",
    )


class RiskAndComplianceTest(unittest.TestCase):
    def test_risk_blocks_unprotected_intent(self):
        intent = protected_intent()
        unprotected = OrderIntent(
            symbol=intent.symbol,
            market=intent.market,
            instrument_type=intent.instrument_type,
            side=intent.side,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            stop_loss=None,
            take_profit=intent.take_profit,
            strategy_id=intent.strategy_id,
        )

        decision = RiskAgent(Settings()).evaluate(
            unprotected,
            AccountSnapshot("paper-local", Decimal("100000"), Decimal("100000")),
            [],
        )

        self.assertFalse(decision.allowed)
        self.assertIn("missing stop-loss or take-profit", decision.reasons)

    def test_risk_blocks_total_position_cap(self):
        positions = [
            Position(f"S{i}", "US", Decimal("1"), Decimal("10"))
            for i in range(6)
        ]

        decision = RiskAgent(Settings()).evaluate(
            protected_intent("AAPL"),
            AccountSnapshot("paper-local", Decimal("100000"), Decimal("100000")),
            positions,
        )

        self.assertFalse(decision.allowed)
        self.assertIn("total position cap reached", decision.reasons)

    def test_compliance_blocks_india_live_without_algo_id(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            groww_algo_id=None,
        )

        decision = ComplianceGuard(settings).evaluate(
            protected_intent("NIFTYBEES", "IN"),
            broker="groww",
            now=datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
        )

        self.assertFalse(decision.allowed)
        self.assertIn("Groww algo id is missing", decision.reasons)

    def test_compliance_allows_alpaca_paper_with_allowlisted_account(self):
        settings = Settings(mode=RuntimeMode.PAPER, account_id="paper-local")

        decision = ComplianceGuard(settings).evaluate(
            protected_intent(),
            broker="alpaca",
            now=datetime(2026, 7, 6, 14, 0, tzinfo=timezone.utc),
        )

        self.assertTrue(decision.allowed)


if __name__ == "__main__":
    unittest.main()
