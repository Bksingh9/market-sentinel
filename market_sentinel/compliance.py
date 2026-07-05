from __future__ import annotations

from datetime import datetime

from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.models import Decision, OrderIntent


class ComplianceGuard:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(self, intent: OrderIntent, *, broker: str, now: datetime) -> Decision:
        reasons: list[str] = []
        if self.settings.mode in {RuntimeMode.DISABLED, RuntimeMode.EMERGENCY}:
            reasons.append(f"mode blocks new orders: {self.settings.mode.value}")
        if self.settings.mode == RuntimeMode.BACKTEST:
            reasons.append("backtest mode cannot submit broker orders")
        if self.settings.account_id not in self.settings.account_allowlist:
            reasons.append("account is not allowlisted")
        if not intent.has_protection():
            reasons.append("missing stop-loss or take-profit")
        if broker == "groww" and self.settings.mode == RuntimeMode.LIVE_SMALL:
            if intent.market != "IN":
                reasons.append("Groww live-small is limited to India market")
            if not self.settings.india_live_trading_enabled:
                reasons.append("India live trading flag is disabled")
            if not self.settings.india_algo_compliance_verified:
                reasons.append("India algo compliance is not verified")
            if not self.settings.groww_algo_id:
                reasons.append("Groww algo id is missing")
        if broker == "alpaca" and self.settings.mode == RuntimeMode.LIVE_SMALL:
            if intent.market != "US":
                reasons.append("Alpaca live-small is limited to US market")
            if not self.settings.alpaca_live_trading_enabled:
                reasons.append("Alpaca live trading flag is disabled")
            if not self.settings.alpaca_account_id:
                reasons.append("Alpaca account id is missing")
        if now.tzinfo is None:
            reasons.append("timestamp must be timezone-aware")
        if reasons:
            return Decision.block(*reasons)
        return Decision.allow()
