import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from market_sentinel.alerts import TwilioAlertAdapter
from market_sentinel.api_clients import HttpResponse
from market_sentinel.brokers import AlpacaBrokerAdapter, BrokerReject, GrowwBrokerAdapter, MockBrokerAdapter
from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.execution import ExecutionAgent
from market_sentinel.models import AccountSnapshot, InstrumentType, OrderIntent, Position, Side


class RecordingHttpClient:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or HttpResponse(200, {"id": "order-1", "filled_avg_price": "500"})

    def post_json(self, url, *, headers, payload, auth=None):
        self.calls.append(("json", url, headers, payload, auth))
        return self.response

    def post_form(self, url, *, data, auth=None):
        self.calls.append(("form", url, {}, data, auth))
        return HttpResponse(201, {"sid": "SM123", "status": "queued"})


class RecordingGrowwClient:
    def __init__(self):
        self.payloads = []

    def place_order(self, payload):
        self.payloads.append(payload)
        return {"order_id": "groww-1", "average_price": "102"}


def protected_intent(symbol="SPY", market="US"):
    return OrderIntent(
        symbol=symbol,
        market=market,
        instrument_type=InstrumentType.ETF,
        side=Side.BUY,
        quantity=Decimal("1"),
        limit_price=Decimal("500"),
        stop_loss=Decimal("490"),
        take_profit=Decimal("515"),
        strategy_id="momentum-long",
    )


class BrokersExecutionAndAlertsTest(unittest.TestCase):
    def test_alpaca_real_paper_api_uses_official_order_payload(self):
        http = RecordingHttpClient()
        settings = Settings(
            mode=RuntimeMode.PAPER,
            alpaca_real_api_enabled=True,
            alpaca_key_id="key",
            alpaca_secret_key="secret",
        )
        broker = AlpacaBrokerAdapter(settings, http_client=http)

        fill = broker.place_order(protected_intent())

        self.assertEqual(fill.symbol, "SPY")
        _, url, headers, payload, _ = http.calls[0]
        self.assertEqual(url, "https://paper-api.alpaca.markets/v2/orders")
        self.assertEqual(headers["APCA-API-KEY-ID"], "key")
        self.assertEqual(payload["order_class"], "bracket")
        self.assertEqual(payload["take_profit"]["limit_price"], "515")
        self.assertEqual(payload["stop_loss"]["stop_price"], "490")

    def test_groww_real_api_boundary_calls_sdk_client_only_when_enabled(self):
        client = RecordingGrowwClient()
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="paper-local",
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            groww_algo_id="algo-123",
            groww_real_api_enabled=True,
            groww_access_token="token",
        )
        broker = GrowwBrokerAdapter(settings, groww_client=client)

        fill = broker.place_order(protected_intent("NIFTYBEES", "IN"))

        self.assertEqual(fill.symbol, "NIFTYBEES")
        self.assertEqual(client.payloads[0]["algo_id"], "algo-123")
        self.assertEqual(client.payloads[0]["symbol"], "NIFTYBEES")

    def test_execution_agent_blocks_before_broker_call(self):
        class ExplodingBroker:
            name = "alpaca"

            def place_order(self, order_intent):
                raise AssertionError("broker should not be called")

        agent = ExecutionAgent(Settings(mode=RuntimeMode.DISABLED), ExplodingBroker())
        result = agent.submit(
            protected_intent(),
            AccountSnapshot("paper-local", Decimal("100000"), Decimal("100000")),
            [],
            now=datetime.now(timezone.utc),
        )

        self.assertFalse(result.allowed)
        self.assertIn("mode blocks new orders: disabled", result.reasons)

    def test_mock_broker_returns_fill(self):
        fill = MockBrokerAdapter().place_order(protected_intent())

        self.assertEqual(fill.symbol, "SPY")
        self.assertEqual(fill.price, Decimal("500"))

    def test_twilio_alert_adapter_posts_message_when_enabled(self):
        http = RecordingHttpClient()
        settings = Settings(
            twilio_alerts_enabled=True,
            twilio_account_sid="AC123",
            twilio_auth_token="auth",
            twilio_from="+10000000000",
            twilio_to="+19999999999",
        )
        adapter = TwilioAlertAdapter(settings, http_client=http)

        result = adapter.send("Risk gate blocked a scheduled order")

        self.assertEqual(result["status"], "queued")
        _, url, _, data, auth = http.calls[0]
        self.assertEqual(url, "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json")
        self.assertEqual(data["Body"], "Risk gate blocked a scheduled order")
        self.assertEqual(auth, ("AC123", "auth"))


if __name__ == "__main__":
    unittest.main()
