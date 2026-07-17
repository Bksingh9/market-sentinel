from __future__ import annotations

from decimal import Decimal

from market_sentinel.ml_features import FeatureRow
from market_sentinel.models import InstrumentType, OrderIntent, Side
from market_sentinel.prediction import Prediction


class StrategyAgent:
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id

    def generate(
        self,
        feature_row: FeatureRow,
        candidate_passed: bool,
        prediction: Prediction,
    ) -> list[OrderIntent]:
        if not candidate_passed or not prediction.passed:
            return []

        limit_price = feature_row.last_close
        return [
            OrderIntent(
                symbol=feature_row.symbol,
                market=feature_row.market,
                instrument_type=InstrumentType.ETF,
                side=Side.BUY,
                quantity=Decimal("1"),
                limit_price=limit_price,
                stop_loss=(limit_price * Decimal("0.98")).quantize(Decimal("0.01")),
                take_profit=(limit_price * Decimal("1.03")).quantize(Decimal("0.01")),
                strategy_id=self.strategy_id,
            )
        ]
