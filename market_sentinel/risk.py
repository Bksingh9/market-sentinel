from __future__ import annotations

from market_sentinel.config import Settings
from market_sentinel.models import AccountSnapshot, Decision, InstrumentType, OrderIntent, Position, Side


DERIVATIVE_TYPES = {
    InstrumentType.OPTION,
    InstrumentType.FUTURE,
    InstrumentType.COMMODITY,
    InstrumentType.CRYPTO,
}


class RiskAgent:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
        positions: list[Position],
    ) -> Decision:
        reasons: list[str] = []
        if not intent.has_protection():
            reasons.append("missing stop-loss or take-profit")
        if intent.side == Side.SHORT:
            reasons.append("unsupported shorting")
        if intent.instrument_type == InstrumentType.OPTION and intent.side == Side.SELL:
            reasons.append("naked options are not supported")
        if len(positions) >= self.settings.max_positions_total:
            reasons.append("total position cap reached")
        market_positions = [position for position in positions if position.market == intent.market]
        if len(market_positions) >= self.settings.max_positions_per_market:
            reasons.append("market position cap reached")
        if account.daily_pnl <= -(account.equity * self.settings.daily_loss_stop):
            reasons.append("daily loss stop reached")

        risk_fraction = (
            self.settings.derivative_risk_per_trade
            if intent.instrument_type in DERIVATIVE_TYPES
            else self.settings.cash_etf_risk_per_trade
        )
        max_loss = account.equity * risk_fraction
        if intent.stop_loss is not None:
            estimated_loss = abs(intent.limit_price - intent.stop_loss) * intent.quantity
            if estimated_loss > max_loss:
                reasons.append("per-trade risk budget exceeded")

        if reasons:
            return Decision.block(*reasons)
        return Decision.allow()
