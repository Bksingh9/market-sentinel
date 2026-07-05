import unittest
import io
import json
from contextlib import redirect_stdout
from decimal import Decimal
from unittest.mock import patch

from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.cli import main
from market_sentinel.ruflo import RUFLOAgent, live_preflight_report


class LiveReadinessAndRUFLOTest(unittest.TestCase):
    def test_live_preflight_masks_secrets_and_blocks_missing_credentials(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            alpaca_live_trading_enabled=True,
            alpaca_real_api_enabled=True,
            alpaca_key_id="key-secret",
            alpaca_secret_key=None,
            alpaca_account_id="live-account",
            account_id="live-account",
            account_allowlist=frozenset({"live-account"}),
        )

        report = live_preflight_report(settings)

        self.assertFalse(report["ready_to_trade"])
        self.assertIn("ALPACA_SECRET_KEY", report["apis"]["alpaca"]["missing"])
        self.assertNotIn("key-secret", str(report))
        self.assertNotIn("secret", report["apis"]["alpaca"])

    def test_live_preflight_allows_alpaca_only_when_all_gates_are_present(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="live-account",
            account_allowlist=frozenset({"live-account"}),
            alpaca_live_trading_enabled=True,
            alpaca_real_api_enabled=True,
            alpaca_account_id="live-account",
            alpaca_key_id="key",
            alpaca_secret_key="secret",
            twilio_alerts_enabled=True,
            twilio_account_sid="AC123",
            twilio_auth_token="auth",
            twilio_to="+19999999999",
            twilio_messaging_service_sid="MG123",
        )

        report = live_preflight_report(settings)

        self.assertTrue(report["apis"]["alpaca"]["ready"])
        self.assertTrue(report["alerts"]["twilio"]["ready"])
        self.assertTrue(report["ready_to_trade"])

    def test_ruflo_supervised_paper_run_executes_only_in_paper_mode(self):
        agent = RUFLOAgent()
        settings = Settings(mode=RuntimeMode.PAPER)

        result = agent.supervised_run_once(settings)

        self.assertEqual(result["mode"], "paper")
        self.assertEqual(result["decision"], "allowed")
        self.assertEqual(result["broker"], "mock")
        self.assertFalse(result["live_order_submitted"])

    def test_ruflo_has_no_discretionary_profit_booking_authority(self):
        agent = RUFLOAgent()

        authority = agent.trading_authority()

        self.assertFalse(authority["can_take_discretionary_calls"])
        self.assertFalse(authority["can_book_profit_autonomously"])
        self.assertEqual(authority["live_order_authority"], "execution-agent-only-after-gates")

    def test_live_preflight_cli_reports_sanitized_missing_live_api_state(self):
        with patch.dict(
            "os.environ",
            {
                "MARKET_SENTINEL_MODE": "live-small",
                "MARKET_SENTINEL_ACCOUNT_ID": "live-account",
                "MARKET_SENTINEL_ACCOUNT_ALLOWLIST": "live-account",
                "ALPACA_LIVE_TRADING_ENABLED": "true",
                "ALPACA_REAL_API_ENABLED": "true",
                "ALPACA_KEY_ID": "key-secret",
            },
            clear=True,
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["live-preflight"])
        data = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertFalse(data["ready_to_trade"])
        self.assertIn("ALPACA_SECRET_KEY", data["apis"]["alpaca"]["missing"])
        self.assertNotIn("key-secret", output.getvalue())

    def test_ruflo_run_once_cli_is_paper_only(self):
        with patch.dict("os.environ", {"MARKET_SENTINEL_MODE": "paper"}, clear=True):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["ruflo-run-once"])
        data = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["decision"], "allowed")
        self.assertFalse(data["live_order_submitted"])


if __name__ == "__main__":
    unittest.main()
