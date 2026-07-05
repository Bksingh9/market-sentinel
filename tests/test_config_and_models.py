import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from market_sentinel.config import RuntimeMode, load_settings
from market_sentinel.models import InstrumentType, OrderIntent, Side


class ConfigAndModelsTest(unittest.TestCase):
    def test_unknown_mode_fails_closed_to_disabled(self):
        with patch.dict(os.environ, {"MARKET_SENTINEL_MODE": "fast-live"}, clear=True):
            settings = load_settings()

        self.assertEqual(settings.mode, RuntimeMode.DISABLED)

    def test_risk_defaults_are_conservative(self):
        settings = load_settings({})

        self.assertEqual(settings.cash_etf_risk_per_trade, Decimal("0.0025"))
        self.assertEqual(settings.derivative_risk_per_trade, Decimal("0.0010"))
        self.assertEqual(settings.daily_loss_stop, Decimal("0.01"))
        self.assertEqual(settings.weekly_drawdown_stop, Decimal("0.03"))
        self.assertEqual(settings.monthly_drawdown_stop, Decimal("0.06"))
        self.assertEqual(settings.max_positions_per_market, 3)
        self.assertEqual(settings.max_positions_total, 6)

    def test_twilio_production_fields_load_from_environment(self):
        settings = load_settings(
            {
                "TWILIO_ALERTS_ENABLED": "true",
                "TWILIO_ACCOUNT_SID": "AC123",
                "TWILIO_AUTH_TOKEN": "token",
                "TWILIO_MESSAGING_SERVICE_SID": "MG123",
                "TWILIO_STATUS_CALLBACK_URL": "https://example.test/twilio/status",
                "TWILIO_TO": "+19999999999",
            }
        )

        self.assertTrue(settings.twilio_alerts_enabled)
        self.assertEqual(settings.twilio_messaging_service_sid, "MG123")
        self.assertEqual(settings.twilio_status_callback_url, "https://example.test/twilio/status")

    def test_order_intent_requires_protection(self):
        intent = OrderIntent(
            symbol="SPY",
            market="US",
            instrument_type=InstrumentType.ETF,
            side=Side.BUY,
            quantity=Decimal("1"),
            limit_price=Decimal("500"),
            stop_loss=None,
            take_profit=Decimal("510"),
            strategy_id="mean-reversion",
        )

        self.assertFalse(intent.has_protection())


if __name__ == "__main__":
    unittest.main()
