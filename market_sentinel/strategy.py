from __future__ import annotations

from decimal import Decimal

from market_sentinel.models import InstrumentType, OrderIntent, Side
from market_sentinel.prediction import Prediction


class StrategyAgent:
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id

    def generate(
        self,
        symbol: str,
        market: str,
        features: dict[str, Decimal],
        prediction: Prediction,
    ) -> list[OrderIntent]:
        if not prediction.passed:
            return []
        if features.get("momentum", Decimal("0")) <= Decimal("0"):
            return []

        limit_price = features["last_close"]
        return [
            OrderIntent(
                symbol=symbol,
                market=market,
                instrument_type=InstrumentType.ETF if symbol in {"SPY", "NIFTYBEES"} else InstrumentType.EQUITY,
                side=Side.BUY,
                quantity=Decimal("1"),
                limit_price=limit_price,
                stop_loss=(limit_price * Decimal("0.98")).quantize(Decimal("0.01")),
                take_profit=(limit_price * Decimal("1.03")).quantize(Decimal("0.01")),
                strategy_id=self.strategy_id,
            )
        ]
