import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from market_sentinel.alerts import TwilioAlertAdapter
from market_sentinel.api_clients import HttpResponse
from market_sentinel.brokers import (
    AlpacaBrokerAdapter,
    BrokerReject,
    DhanBrokerAdapter,
    GrowwBrokerAdapter,
    GrowwSDKClient,
    MockBrokerAdapter,
)
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


class FakeGrowwAPI:
    VALIDITY_DAY = "DAY"
    EXCHANGE_NSE = "NSE"
    SEGMENT_CASH = "CASH"
    PRODUCT_CNC = "CNC"
    PRODUCT_MIS = "MIS"
    ORDER_TYPE_MARKET = "MARKET"
    ORDER_TYPE_LIMIT = "LIMIT"
    TRANSACTION_TYPE_BUY = "BUY"
    TRANSACTION_TYPE_SELL = "SELL"
    generated_tokens = []
    instances = []

    def __init__(self, access_token):
        self.access_token = access_token
        self.orders = []
        self.__class__.instances.append(self)

    @classmethod
    def get_access_token(cls, *, api_key, secret):
        cls.generated_tokens.append((api_key, secret))
        return "generated-token"

    def place_order(self, **kwargs):
        self.orders.append(kwargs)
        return {"groww_order_id": "groww-1"}


def protected_intent(symbol="SPY", market="US", instrument_type=InstrumentType.ETF):
    return OrderIntent(
        symbol=symbol,
        market=market,
        instrument_type=instrument_type,
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

    def test_alpaca_live_api_uses_configured_live_endpoint(self):
        http = RecordingHttpClient()
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            alpaca_live_trading_enabled=True,
            alpaca_real_api_enabled=True,
            alpaca_account_id="live-account",
            alpaca_key_id="key",
            alpaca_secret_key="secret",
            alpaca_trading_endpoint="https://api.alpaca.markets",
        )
        broker = AlpacaBrokerAdapter(settings, http_client=http)

        broker.place_order(protected_intent())

        _, url, _, _, _ = http.calls[0]
        self.assertEqual(url, "https://api.alpaca.markets/v2/orders")

    def test_groww_real_api_boundary_calls_sdk_client_only_when_enabled(self):
        client = RecordingGrowwClient()
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="paper-local",
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            groww_algo_id="algo-123",
            groww_real_api_enabled=True,
            groww_api_subscription_active=True,
            groww_protected_order_client=True,
            groww_static_outbound_ip="8.8.8.8",
            groww_static_ip_allowlisted=True,
            groww_access_token="token",
        )
        broker = GrowwBrokerAdapter(settings, groww_client=client)

        fill = broker.place_order(protected_intent("NIFTYBEES", "IN"))

        self.assertEqual(fill.symbol, "NIFTYBEES")
        self.assertEqual(client.payloads[0]["algo_id"], "algo-123")
        self.assertEqual(client.payloads[0]["symbol"], "NIFTYBEES")

    def test_groww_live_blocks_without_protected_order_client(self):
        client = RecordingGrowwClient()
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="paper-local",
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            groww_algo_id="algo-123",
            groww_real_api_enabled=True,
            groww_api_subscription_active=True,
            groww_access_token="token",
        )
        broker = GrowwBrokerAdapter(settings, groww_client=client)

        with self.assertRaises(BrokerReject):
            broker.place_order(protected_intent("NIFTYBEES", "IN"))
        self.assertEqual(client.payloads, [])

    def test_groww_sdk_client_generates_access_token_from_key_secret(self):
        FakeGrowwAPI.generated_tokens = []
        FakeGrowwAPI.instances = []
        settings = Settings(groww_api_key="api-key", groww_secret_key="secret-key")

        client = GrowwSDKClient.from_settings(settings, sdk_factory=FakeGrowwAPI)
        result = client.place_order(
            {"symbol": "IDEA", "quantity": "1", "side": "buy", "price": "10.5", "algo_id": "algo-123"}
        )

        self.assertEqual(result["groww_order_id"], "groww-1")
        self.assertEqual(FakeGrowwAPI.generated_tokens, [("api-key", "secret-key")])
        self.assertEqual(FakeGrowwAPI.instances[0].access_token, "generated-token")
        self.assertEqual(FakeGrowwAPI.instances[0].orders[0]["trading_symbol"], "IDEA")
        self.assertEqual(FakeGrowwAPI.instances[0].orders[0]["transaction_type"], "BUY")
        self.assertEqual(FakeGrowwAPI.instances[0].orders[0]["product"], "CNC")
        self.assertEqual(FakeGrowwAPI.instances[0].orders[0]["order_type"], "LIMIT")
        self.assertEqual(FakeGrowwAPI.instances[0].orders[0]["price"], 10.5)
        self.assertEqual(FakeGrowwAPI.instances[0].orders[0]["order_reference_id"], "algo-123")

    def test_groww_live_gate_accepts_key_secret_without_printing_them(self):
        client = RecordingGrowwClient()
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="paper-local",
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            groww_algo_id="algo-123",
            groww_real_api_enabled=True,
            groww_api_subscription_active=True,
            groww_protected_order_client=True,
            groww_static_outbound_ip="8.8.8.8",
            groww_static_ip_allowlisted=True,
            groww_api_key="api-key",
            groww_secret_key="secret-key",
        )
        broker = GrowwBrokerAdapter(settings, groww_client=client)

        broker.place_order(protected_intent("NIFTYBEES", "IN"))

        self.assertEqual(client.payloads[0]["symbol"], "NIFTYBEES")

    def test_groww_live_blocks_without_static_ip_allowlist(self):
        client = RecordingGrowwClient()
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="paper-local",
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            groww_algo_id="algo-123",
            groww_real_api_enabled=True,
            groww_api_subscription_active=True,
            groww_protected_order_client=True,
            groww_access_token="token",
        )
        broker = GrowwBrokerAdapter(settings, groww_client=client)

        with self.assertRaises(BrokerReject):
            broker.place_order(protected_intent("NIFTYBEES", "IN"))
        self.assertEqual(client.payloads, [])

    def test_dhan_live_api_uses_official_order_payload(self):
        http = RecordingHttpClient(HttpResponse(200, {"orderId": "order-1", "orderStatus": "PENDING"}))
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="paper-local",
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
        broker = DhanBrokerAdapter(settings, http_client=http)

        fill = broker.place_order(protected_intent("IDEA", "IN", InstrumentType.EQUITY))

        self.assertEqual(fill.symbol, "IDEA")
        _, url, headers, payload, _ = http.calls[0]
        self.assertEqual(url, "https://api.dhan.co/v2/orders")
        self.assertEqual(headers["access-token"], "token")
        self.assertEqual(payload["dhanClientId"], "client-1")
        self.assertEqual(payload["securityId"], "14366")
        self.assertEqual(payload["productType"], "BO")
        self.assertEqual(payload["orderType"], "LIMIT")
        self.assertEqual(payload["boProfitValue"], "15")
        self.assertEqual(payload["boStopLossValue"], "10")

    def test_dhan_live_blocks_without_static_ip_allowlist(self):
        http = RecordingHttpClient()
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="paper-local",
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            dhan_real_api_enabled=True,
            dhan_client_id="client-1",
            dhan_access_token="token",
            dhan_protected_order_client=True,
            dhan_security_id_map={"IDEA": "14366"},
        )
        broker = DhanBrokerAdapter(settings, http_client=http)

        with self.assertRaises(BrokerReject):
            broker.place_order(protected_intent("IDEA", "IN", InstrumentType.EQUITY))
        self.assertEqual(http.calls, [])

    def test_dhan_live_blocks_without_security_id_mapping(self):
        http = RecordingHttpClient()
        settings = Settings(
            mode=RuntimeMode.LIVE_SMALL,
            account_id="paper-local",
            india_live_trading_enabled=True,
            india_algo_compliance_verified=True,
            dhan_real_api_enabled=True,
            dhan_client_id="client-1",
            dhan_access_token="token",
            dhan_static_outbound_ip="8.8.8.8",
            dhan_static_ip_allowlisted=True,
            dhan_protected_order_client=True,
        )
        broker = DhanBrokerAdapter(settings, http_client=http)

        with self.assertRaises(BrokerReject):
            broker.place_order(protected_intent("IDEA", "IN", InstrumentType.EQUITY))
        self.assertEqual(http.calls, [])

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
        self.assertEqual(data["From"], "+10000000000")
        self.assertEqual(data["To"], "+19999999999")
        self.assertEqual(auth, ("AC123", "auth"))

    def test_twilio_alert_adapter_supports_messaging_service_and_status_callback(self):
        http = RecordingHttpClient()
        settings = Settings(
            twilio_alerts_enabled=True,
            twilio_account_sid="AC123",
            twilio_auth_token="auth",
            twilio_messaging_service_sid="MG123",
            twilio_status_callback_url="https://example.test/twilio/status",
            twilio_to="+19999999999",
        )
        adapter = TwilioAlertAdapter(settings, http_client=http)

        adapter.send("Execution alert")

        _, _, _, data, _ = http.calls[0]
        self.assertNotIn("From", data)
        self.assertEqual(data["MessagingServiceSid"], "MG123")
        self.assertEqual(data["StatusCallback"], "https://example.test/twilio/status")


if __name__ == "__main__":
    unittest.main()
