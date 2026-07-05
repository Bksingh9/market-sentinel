from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from market_sentinel.models import OrderIntent


class ScheduledOrderStatus(StrEnum):
    PENDING = "pending"
    ELIGIBLE = "eligible"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"


@dataclass
class ScheduledOrderIntent:
    id: str
    intent: OrderIntent
    eligible_at: datetime
    expires_at: datetime
    reason: str
    model_version: str | None = None
    status: ScheduledOrderStatus = ScheduledOrderStatus.PENDING
    block_reason: str | None = None


class ScheduledOrderBook:
    def __init__(self):
        self._items: dict[str, ScheduledOrderIntent] = {}

    def add(self, scheduled: ScheduledOrderIntent) -> None:
        self._items[scheduled.id] = scheduled

    def get(self, scheduled_id: str) -> ScheduledOrderIntent:
        return self._items[scheduled_id]

    def due_intents(self, now: datetime) -> list[ScheduledOrderIntent]:
        due: list[ScheduledOrderIntent] = []
        for scheduled in self._items.values():
            if scheduled.status != ScheduledOrderStatus.PENDING:
                continue
            if now > scheduled.expires_at:
                scheduled.status = ScheduledOrderStatus.EXPIRED
                continue
            if now >= scheduled.eligible_at:
                scheduled.status = ScheduledOrderStatus.ELIGIBLE
                due.append(scheduled)
        return due

    def mark_blocked(self, scheduled_id: str, reason: str) -> None:
        scheduled = self.get(scheduled_id)
        scheduled.status = ScheduledOrderStatus.BLOCKED
        scheduled.block_reason = reason
