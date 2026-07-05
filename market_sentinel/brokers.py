from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol

from market_sentinel.api_clients import HttpClient, UrllibHttpClient
from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.models import Fill, OrderIntent, Side


class BrokerReject(RuntimeError):
    pass


class BrokerAdapter(Protocol):
    name: str

    def place_order(self, order_intent: OrderIntent) -> Fill:
        ...


class GrowwClient(Protocol):
    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class MockBrokerAdapter:
    name = "mock"

    def place_order(self, order_intent: OrderIntent) -> Fill:
        return Fill(
            symbol=order_intent.symbol,
            side=order_intent.side,
            quantity=order_intent.quantity,
            price=order_intent.limit_price,
            commission=Decimal("0"),
            timestamp=datetime.now(timezone.utc),
        )


class GrowwBrokerAdapter:
    name = "groww"

    def __init__(self, settings: Settings, *, groww_client: GrowwClient | None = None):
        self.settings = settings
        self.groww_client = groww_client

    def place_order(self, order_intent: OrderIntent) -> Fill:
        if not self._live_gate_open():
            if self.settings.mode == RuntimeMode.PAPER and not self.settings.groww_real_api_enabled:
                return MockBrokerAdapter().place_order(order_intent)
            raise BrokerReject("Groww live order blocked by adapter gate")
        if not self.settings.groww_real_api_enabled:
            return MockBrokerAdapter().place_order(order_intent)
        if self.groww_client is None:
            raise BrokerReject("Groww real API enabled but no SDK client is configured")

        payload = {
            "symbol": order_intent.symbol,
            "quantity": str(order_intent.quantity),
            "price": str(order_intent.limit_price),
            "side": order_intent.side.value,
            "stop_loss": str(order_intent.stop_loss),
            "take_profit": str(order_intent.take_profit),
            "algo_id": self.settings.groww_algo_id,
        }
        result = self.groww_client.place_order(payload)
        return Fill(
            symbol=order_intent.symbol,
            side=order_intent.side,
            quantity=order_intent.quantity,
            price=Decimal(str(result.get("average_price", order_intent.limit_price))),
            commission=Decimal("0"),
            timestamp=datetime.now(timezone.utc),
        )

    def _live_gate_open(self) -> bool:
        return bool(
            self.settings.mode == RuntimeMode.LIVE_SMALL
            and self.settings.india_live_trading_enabled
            and self.settings.india_algo_compliance_verified
            and self.settings.groww_algo_id
            and self.settings.groww_access_token
        )


class AlpacaBrokerAdapter:
    name = "alpaca"
    PAPER_URL = "https://paper-api.alpaca.markets/v2/orders"
    LIVE_URL = "https://api.alpaca.markets/v2/orders"

    def __init__(self, settings: Settings, *, http_client: HttpClient | None = None):
        self.settings = settings
        self.http_client = http_client or UrllibHttpClient()

    def place_order(self, order_intent: OrderIntent) -> Fill:
        if self.settings.mode == RuntimeMode.PAPER:
            if self.settings.alpaca_real_api_enabled:
                return self._post_order(self.PAPER_URL, order_intent)
            return MockBrokerAdapter().place_order(order_intent)
        if not (
            self.settings.mode == RuntimeMode.LIVE_SMALL
            and self.settings.alpaca_live_trading_enabled
            and self.settings.alpaca_account_id
            and self.settings.alpaca_real_api_enabled
        ):
            raise BrokerReject("Alpaca live order blocked by adapter gate")
        return self._post_order(self.LIVE_URL, order_intent)

    def _post_order(self, url: str, order_intent: OrderIntent) -> Fill:
        if not self.settings.alpaca_key_id or not self.settings.alpaca_secret_key:
            raise BrokerReject("Alpaca API credentials are missing")
        payload = {
            "symbol": order_intent.symbol,
            "qty": str(order_intent.quantity),
            "side": "buy" if order_intent.side == Side.BUY else "sell",
            "type": "limit",
            "time_in_force": "day",
            "limit_price": str(order_intent.limit_price),
            "order_class": "bracket",
            "take_profit": {"limit_price": str(order_intent.take_profit)},
            "stop_loss": {"stop_price": str(order_intent.stop_loss)},
        }
        response = self.http_client.post_json(
            url,
            headers={
                "APCA-API-KEY-ID": self.settings.alpaca_key_id,
                "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
            },
            payload=payload,
        )
        if response.status_code >= 400:
            raise BrokerReject(f"Alpaca order rejected with HTTP {response.status_code}")
        price = response.payload.get("filled_avg_price") or order_intent.limit_price
        return Fill(
            symbol=order_intent.symbol,
            side=order_intent.side,
            quantity=order_intent.quantity,
            price=Decimal(str(price)),
            commission=Decimal("0"),
            timestamp=datetime.now(timezone.utc),
        )
