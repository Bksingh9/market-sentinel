from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from market_sentinel.models import Decision, Quote


class MarketDataAgent:
    def __init__(self, max_age_seconds: int = 10):
        self.max_age_seconds = max_age_seconds

    def validate_quote(self, quote: Quote, *, now: datetime) -> Decision:
        reasons: list[str] = []
        if not quote.symbol or not quote.market:
            reasons.append("quote identity is missing")
        if quote.bid <= Decimal("0") or quote.ask <= Decimal("0") or quote.last <= Decimal("0"):
            reasons.append("quote price is non-positive")
        if quote.bid > quote.ask:
            reasons.append("quote bid exceeds ask")
        if (now - quote.timestamp).total_seconds() > self.max_age_seconds:
            reasons.append("quote is stale")
        if reasons:
            return Decision.block(*reasons)
        return Decision.allow()
