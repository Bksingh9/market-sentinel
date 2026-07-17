import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from market_sentinel.models import InstrumentType, OrderIntent, Side
from market_sentinel.scheduler import ScheduledOrderBook, ScheduledOrderIntent, ScheduledOrderStatus


def protected_intent():
    return OrderIntent(
        symbol="SPY",
        market="US",
        instrument_type=InstrumentType.ETF,
        side=Side.BUY,
        quantity=Decimal("1"),
        limit_price=Decimal("500"),
        stop_loss=Decimal("490"),
        take_profit=Decimal("515"),
        strategy_id="momentum-long",
    )


class MLTrainingAndSchedulingTest(unittest.TestCase):
    def test_scheduler_returns_only_eligible_unexpired_intents(self):
        now = datetime(2026, 7, 5, 10, 0, tzinfo=timezone.utc)
        book = ScheduledOrderBook()
        future = ScheduledOrderIntent(
            id="future",
            intent=protected_intent(),
            eligible_at=now + timedelta(minutes=5),
            expires_at=now + timedelta(minutes=30),
            reason="wait for open",
        )
        due = ScheduledOrderIntent(
            id="due",
            intent=protected_intent(),
            eligible_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(minutes=30),
            reason="scheduled model signal",
            model_version="model-1",
        )
        expired = ScheduledOrderIntent(
            id="expired",
            intent=protected_intent(),
            eligible_at=now - timedelta(minutes=30),
            expires_at=now - timedelta(minutes=1),
            reason="old signal",
        )

        book.add(future)
        book.add(due)
        book.add(expired)
        due_items = book.due_intents(now)

        self.assertEqual([item.id for item in due_items], ["due"])
        self.assertEqual(book.get("future").status, ScheduledOrderStatus.PENDING)
        self.assertEqual(book.get("due").status, ScheduledOrderStatus.ELIGIBLE)
        self.assertEqual(book.get("expired").status, ScheduledOrderStatus.EXPIRED)


if __name__ == "__main__":
    unittest.main()
