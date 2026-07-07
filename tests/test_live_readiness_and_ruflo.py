import unittest
import io
import json
from contextlib import redirect_stdout
from decimal import Decimal
from unittest.mock import patch

from market_sentinel.config import PrimaryBroker, RuntimeMode, Settings
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

    def test_live_preflight_blocks_non_live_alpaca_endpoint(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="live-account",
            account_allowlist=frozenset({"live-account"}),
            alpaca_live_trading_enabled=True,
            alpaca_real_api_enabled=True,
            alpaca_account_id="live-account",
            alpaca_key_id="key",
            alpaca_secret_key="secret",
            alpaca_trading_endpoint="https://paper-api.alpaca.markets",
        )

        report = live_preflight_report(settings)

        self.assertFalse(report["ready_to_trade"])
        self.assertIn("ALPACA_TRADING_ENDPOINT=https://api.alpaca.markets", report["apis"]["alpaca"]["missing"])

    def test_live_preflight_requires_groww_subscription_and_protected_client(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="live-account",
            account_allowlist=frozenset({"live-account"}),
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            groww_real_api_enabled=True,
            groww_access_token="token",
            groww_algo_id="algo-123",
        )

        report = live_preflight_report(settings)

        self.assertFalse(report["ready_to_trade"])
        self.assertIn("GROWW_API_SUBSCRIPTION_ACTIVE", report["apis"]["groww"]["missing"])
        self.assertIn("GROWW_PROTECTED_ORDER_CLIENT", report["apis"]["groww"]["missing"])
        self.assertIn("GROWW_STATIC_OUTBOUND_IP", report["apis"]["groww"]["missing"])
        self.assertIn("GROWW_STATIC_IP_ALLOWLISTED", report["apis"]["groww"]["missing"])

    def test_live_preflight_accepts_groww_api_key_and_secret_as_credentials(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            primary_broker=PrimaryBroker.GROWW,
            account_id="live-account",
            account_allowlist=frozenset({"live-account"}),
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            groww_real_api_enabled=True,
            groww_api_subscription_active=True,
            groww_protected_order_client=True,
            groww_static_outbound_ip="8.8.8.8",
            groww_static_ip_allowlisted=True,
            groww_api_key="api-key",
            groww_secret_key="secret-key",
            groww_algo_id="algo-123",
        )

        report = live_preflight_report(settings)

        self.assertTrue(report["apis"]["groww"]["ready"])
        self.assertTrue(report["ready_to_trade"])
        self.assertNotIn("api-key", str(report))
        self.assertNotIn("secret-key", str(report))

    def test_live_preflight_groww_primary_ignores_ready_dhan(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            primary_broker=PrimaryBroker.GROWW,
            account_id="live-account",
            account_allowlist=frozenset({"live-account"}),
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            dhan_real_api_enabled=True,
            dhan_client_id="client-1",
            dhan_access_token="token",
            dhan_static_outbound_ip="8.8.8.8",
            dhan_static_ip_allowlisted=True,
            dhan_protected_order_client=True,
            dhan_security_id_map={"IDEA": "14366"},
        )

        report = live_preflight_report(settings)

        self.assertTrue(report["apis"]["dhan"]["ready"])
        self.assertFalse(report["apis"]["groww"]["ready"])
        self.assertFalse(report["ready_to_trade"])
        self.assertEqual(report["primary_broker"], "groww")

    def test_live_preflight_allows_dhan_when_all_gates_are_present(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="live-account",
            account_allowlist=frozenset({"live-account"}),
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            dhan_real_api_enabled=True,
            dhan_client_id="client-1",
            dhan_access_token="token",
            dhan_static_outbound_ip="8.8.8.8",
            dhan_static_ip_allowlisted=True,
            dhan_protected_order_client=True,
            dhan_security_id_map={"IDEA": "14366"},
        )

        report = live_preflight_report(settings)

        self.assertTrue(report["apis"]["dhan"]["ready"])
        self.assertTrue(report["ready_to_trade"])
        self.assertNotIn("token", str(report))

    def test_live_preflight_blocks_dhan_without_static_ip(self):
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="live-account",
            account_allowlist=frozenset({"live-account"}),
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            dhan_real_api_enabled=True,
            dhan_client_id="client-1",
            dhan_access_token="token",
            dhan_protected_order_client=True,
            dhan_security_id_map={"IDEA": "14366"},
        )

        report = live_preflight_report(settings)

        self.assertFalse(report["ready_to_trade"])
        self.assertIn("DHAN_STATIC_OUTBOUND_IP", report["apis"]["dhan"]["missing"])
        self.assertIn("DHAN_STATIC_IP_ALLOWLISTED", report["apis"]["dhan"]["missing"])

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
