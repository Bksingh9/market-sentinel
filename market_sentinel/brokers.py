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


def _groww_credentials_present(settings: Settings) -> bool:
    return bool(settings.groww_access_token or (settings.groww_api_key and settings.groww_secret_key))


class GrowwSDKClient:
    def __init__(self, access_token: str, *, sdk_factory: Any | None = None):
        groww_api = self._load_sdk(sdk_factory)
        self.groww = groww_api(access_token)

    @classmethod
    def from_settings(cls, settings: Settings, *, sdk_factory: Any | None = None) -> "GrowwSDKClient":
        groww_api = cls._load_sdk(sdk_factory)
        if settings.groww_access_token:
            access_token = settings.groww_access_token
        elif settings.groww_api_key and settings.groww_secret_key:
            access_token = groww_api.get_access_token(
                api_key=settings.groww_api_key,
                secret=settings.groww_secret_key,
            )
        else:
            raise BrokerReject("Groww API credentials are missing")
        return cls(access_token, sdk_factory=groww_api)

    @staticmethod
    def _load_sdk(sdk_factory: Any | None) -> Any:
        if sdk_factory is not None:
            return sdk_factory
        try:
            from growwapi import GrowwAPI
        except ImportError as exc:
            raise BrokerReject("Groww real API enabled but growwapi is not installed") from exc
        return GrowwAPI

    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        quantity = Decimal(str(payload["quantity"]))
        if quantity != quantity.to_integral_value():
            raise BrokerReject("Groww cash quantity must be a whole share count")
        transaction_type = (
            self.groww.TRANSACTION_TYPE_BUY
            if payload["side"] == Side.BUY.value
            else self.groww.TRANSACTION_TYPE_SELL
        )
        product = getattr(self.groww, "PRODUCT_CNC", self.groww.PRODUCT_MIS)
        return self.groww.place_order(
            trading_symbol=payload["symbol"],
            quantity=int(quantity),
            validity=self.groww.VALIDITY_DAY,
            exchange=self.groww.EXCHANGE_NSE,
            segment=self.groww.SEGMENT_CASH,
            product=product,
            order_type=self.groww.ORDER_TYPE_LIMIT,
            transaction_type=transaction_type,
            price=float(payload["price"]),
            order_reference_id=payload["algo_id"][:20],
        )


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
            and _groww_credentials_present(self.settings)
            and self.settings.groww_api_subscription_active
            and self.settings.groww_protected_order_client
            and self.settings.groww_static_outbound_ip
            and self.settings.groww_static_ip_allowlisted
        )


class DhanBrokerAdapter:
    name = "dhan"
    ORDERS_URL = "https://api.dhan.co/v2/orders"

    def __init__(self, settings: Settings, *, http_client: HttpClient | None = None):
        self.settings = settings
        self.http_client = http_client or UrllibHttpClient()

    def place_order(self, order_intent: OrderIntent) -> Fill:
        if not self._live_gate_open():
            raise BrokerReject("Dhan live order blocked by adapter gate")
        if order_intent.side not in {Side.BUY, Side.SELL}:
            raise BrokerReject("Dhan cash orders support buy and sell sides only")
        return self._post_order(order_intent)

    def _live_gate_open(self) -> bool:
        return bool(
            self.settings.mode == RuntimeMode.LIVE_SMALL
            and self.settings.india_live_trading_enabled
            and self.settings.india_algo_compliance_verified
            and self.settings.dhan_real_api_enabled
            and self.settings.dhan_client_id
            and self.settings.dhan_access_token
            and self.settings.dhan_static_outbound_ip
            and self.settings.dhan_static_ip_allowlisted
            and self.settings.dhan_protected_order_client
        )

    def _post_order(self, order_intent: OrderIntent) -> Fill:
        security_id = self._security_id(order_intent.symbol)
        bo_profit, bo_stop = self._bracket_offsets(order_intent)
        quantity = self._whole_quantity(order_intent.quantity)
        payload = {
            "dhanClientId": self.settings.dhan_client_id,
            "correlationId": order_intent.strategy_id[:30],
            "transactionType": "BUY" if order_intent.side == Side.BUY else "SELL",
            "exchangeSegment": "NSE_EQ",
            "productType": "BO",
            "orderType": "LIMIT",
            "validity": "DAY",
            "securityId": security_id,
            "quantity": quantity,
            "disclosedQuantity": "",
            "price": str(order_intent.limit_price),
            "triggerPrice": "",
            "afterMarketOrder": False,
            "amoTime": "",
            "boProfitValue": str(bo_profit),
            "boStopLossValue": str(bo_stop),
        }
        response = self.http_client.post_json(
            self.ORDERS_URL,
            headers={"access-token": self.settings.dhan_access_token or ""},
            payload=payload,
        )
        if response.status_code >= 400:
            raise BrokerReject(f"Dhan order rejected with HTTP {response.status_code}")
        return Fill(
            symbol=order_intent.symbol,
            side=order_intent.side,
            quantity=order_intent.quantity,
            price=order_intent.limit_price,
            commission=Decimal("0"),
            timestamp=datetime.now(timezone.utc),
        )

    def _security_id(self, symbol: str) -> str:
        if symbol.isdigit():
            return symbol
        security_id = self.settings.dhan_security_id_map.get(symbol.upper())
        if not security_id:
            raise BrokerReject(f"Dhan security id mapping is missing for {symbol}")
        return security_id

    def _whole_quantity(self, quantity: Decimal) -> int:
        if quantity != quantity.to_integral_value():
            raise BrokerReject("Dhan cash quantity must be a whole share count")
        return int(quantity)

    def _bracket_offsets(self, order_intent: OrderIntent) -> tuple[Decimal, Decimal]:
        if not order_intent.has_protection():
            raise BrokerReject("Dhan protected order requires stop-loss and take-profit")
        if order_intent.side == Side.BUY:
            profit = (order_intent.take_profit or Decimal("0")) - order_intent.limit_price
            stop = order_intent.limit_price - (order_intent.stop_loss or Decimal("0"))
        else:
            profit = order_intent.limit_price - (order_intent.take_profit or Decimal("0"))
            stop = (order_intent.stop_loss or Decimal("0")) - order_intent.limit_price
        if profit <= 0 or stop <= 0:
            raise BrokerReject("Dhan bracket offsets must be positive")
        return profit, stop


class AlpacaBrokerAdapter:
    name = "alpaca"

    def __init__(self, settings: Settings, *, http_client: HttpClient | None = None):
        self.settings = settings
        self.http_client = http_client or UrllibHttpClient()

    def place_order(self, order_intent: OrderIntent) -> Fill:
        if self.settings.mode == RuntimeMode.PAPER:
            if self.settings.alpaca_real_api_enabled:
                return self._post_order(self._orders_url(self.settings.alpaca_paper_trading_endpoint), order_intent)
            return MockBrokerAdapter().place_order(order_intent)
        if not (
            self.settings.mode == RuntimeMode.LIVE_SMALL
            and self.settings.alpaca_live_trading_enabled
            and self.settings.alpaca_account_id
            and self.settings.alpaca_real_api_enabled
        ):
            raise BrokerReject("Alpaca live order blocked by adapter gate")
        return self._post_order(self._orders_url(self.settings.alpaca_trading_endpoint), order_intent)

    def _orders_url(self, endpoint: str) -> str:
        return f"{endpoint.rstrip('/')}/v2/orders"

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
