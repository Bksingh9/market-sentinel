import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from market_sentinel.model_store import ModelStore
from market_sentinel.model_training import TrainingExample, train_linear_model
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
    def test_training_produces_model_that_scores_positive_example(self):
        examples = [
            TrainingExample({"momentum": Decimal("0.04"), "average_volume": Decimal("1000")}, 1),
            TrainingExample({"momentum": Decimal("-0.03"), "average_volume": Decimal("900")}, 0),
            TrainingExample({"momentum": Decimal("0.02"), "average_volume": Decimal("1100")}, 1),
        ]

        model = train_linear_model(examples, epochs=12)

        self.assertEqual(model.training_rows, 3)
        self.assertIn("momentum", model.feature_names)
        self.assertGreater(model.predict_score({"momentum": Decimal("0.04"), "average_volume": Decimal("1000")}), Decimal("0.5"))

    def test_model_store_round_trips_active_model(self):
        model = train_linear_model([
            TrainingExample({"momentum": Decimal("0.04")}, 1),
            TrainingExample({"momentum": Decimal("-0.03")}, 0),
        ])

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ModelStore(Path(temp_dir))
            store.save(model)
            store.activate(model.version)
            loaded = store.load_active()

        self.assertEqual(loaded.version, model.version)
        self.assertEqual(loaded.feature_names, model.feature_names)

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
