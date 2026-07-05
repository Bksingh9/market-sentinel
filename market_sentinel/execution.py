from __future__ import annotations

from datetime import datetime

from market_sentinel.brokers import BrokerAdapter
from market_sentinel.compliance import ComplianceGuard
from market_sentinel.config import Settings
from market_sentinel.models import AccountSnapshot, Decision, OrderIntent, Position
from market_sentinel.risk import RiskAgent


class ExecutionAgent:
    def __init__(self, settings: Settings, broker: BrokerAdapter):
        self.settings = settings
        self.broker = broker

    def submit(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
        positions: list[Position],
        *,
        now: datetime,
    ) -> Decision:
        risk_decision = RiskAgent(self.settings).evaluate(intent, account, positions)
        if not risk_decision.allowed:
            return risk_decision

        compliance_decision = ComplianceGuard(self.settings).evaluate(
            intent,
            broker=self.broker.name,
            now=now,
        )
        if not compliance_decision.allowed:
            return compliance_decision

        self.broker.place_order(intent)
        return Decision.allow()
