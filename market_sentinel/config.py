from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
import ipaddress
import os
from urllib.parse import urlparse


class RuntimeMode(StrEnum):
    DISABLED = "disabled"
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE_SMALL = "live-small"
    EMERGENCY = "emergency"


class PrimaryBroker(StrEnum):
    ANY = "any"
    ALPACA = "alpaca"
    GROWW = "groww"
    DHAN = "dhan"


@dataclass(frozen=True)
class Settings:
    mode: RuntimeMode = RuntimeMode.DISABLED
    primary_broker: PrimaryBroker = PrimaryBroker.ANY
    account_id: str = "paper-local"
    account_allowlist: frozenset[str] = field(default_factory=lambda: frozenset({"paper-local"}))
    cash_etf_risk_per_trade: Decimal = Decimal("0.0025")
    derivative_risk_per_trade: Decimal = Decimal("0.0010")
    daily_loss_stop: Decimal = Decimal("0.01")
    weekly_drawdown_stop: Decimal = Decimal("0.03")
    monthly_drawdown_stop: Decimal = Decimal("0.06")
    max_positions_per_market: int = 3
    max_positions_total: int = 6
    india_live_trading_enabled: bool = False
    india_algo_compliance_verified: bool = False
    groww_algo_id: str | None = None
    groww_api_key: str | None = None
    groww_secret_key: str | None = None
    groww_access_token: str | None = None
    groww_real_api_enabled: bool = False
    groww_api_subscription_active: bool = False
    groww_protected_order_client: bool = False
    groww_static_outbound_ip: str | None = None
    groww_static_ip_allowlisted: bool = False
    dhan_client_id: str | None = None
    dhan_access_token: str | None = None
    dhan_real_api_enabled: bool = False
    dhan_static_outbound_ip: str | None = None
    dhan_static_ip_allowlisted: bool = False
    dhan_protected_order_client: bool = False
    dhan_security_id_map: dict[str, str] = field(default_factory=dict)
    alpaca_paper_trading_enabled: bool = True
    alpaca_live_trading_enabled: bool = False
    alpaca_account_id: str | None = None
    alpaca_key_id: str | None = None
    alpaca_secret_key: str | None = None
    alpaca_real_api_enabled: bool = False
    alpaca_paper_trading_endpoint: str = "https://paper-api.alpaca.markets"
    alpaca_trading_endpoint: str = "https://api.alpaca.markets"
    twilio_alerts_enabled: bool = False
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from: str | None = None
    twilio_messaging_service_sid: str | None = None
    twilio_status_callback_url: str | None = None
    twilio_to: str | None = None


def _parse_mode(value: str | None) -> RuntimeMode:
    if value in {mode.value for mode in RuntimeMode}:
        return RuntimeMode(value)
    return RuntimeMode.DISABLED


def _parse_primary_broker(value: str | None) -> PrimaryBroker:
    if value in {broker.value for broker in PrimaryBroker}:
        return PrimaryBroker(value)
    return PrimaryBroker.ANY


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_allowlist(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset({"paper-local"})
    entries = {item.strip() for item in value.split(",") if item.strip()}
    return frozenset(entries or {"paper-local"})


def _parse_endpoint(value: str | None, *, default: str, allowed_hosts: frozenset[str]) -> str:
    endpoint = (value or default).strip().rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or parsed.netloc not in allowed_hosts or parsed.path:
        return default
    return endpoint


def _parse_public_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if parsed.version != 4 or parsed.is_private or parsed.is_loopback or parsed.is_multicast:
        return None
    return str(parsed)


def _parse_symbol_map(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    mapping: dict[str, str] = {}
    for entry in value.split(","):
        if ":" not in entry:
            continue
        symbol, security_id = entry.split(":", 1)
        symbol = symbol.strip().upper()
        security_id = security_id.strip()
        if symbol and security_id.isdigit():
            mapping[symbol] = security_id
    return mapping


def load_settings(env: dict[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env
    return Settings(
        mode=_parse_mode(source.get("MARKET_SENTINEL_MODE")),
        primary_broker=_parse_primary_broker(source.get("MARKET_SENTINEL_PRIMARY_BROKER")),
        account_id=source.get("MARKET_SENTINEL_ACCOUNT_ID", "paper-local"),
        account_allowlist=_parse_allowlist(source.get("MARKET_SENTINEL_ACCOUNT_ALLOWLIST")),
        india_live_trading_enabled=_parse_bool(source.get("INDIA_LIVE_TRADING_ENABLED")),
        india_algo_compliance_verified=_parse_bool(source.get("INDIA_ALGO_COMPLIANCE_VERIFIED")),
        groww_algo_id=source.get("GROWW_ALGO_ID") or None,
        groww_api_key=source.get("GROWW_API_KEY") or None,
        groww_secret_key=source.get("GROWW_SECRET_KEY") or None,
        groww_access_token=source.get("GROWW_ACCESS_TOKEN") or None,
        groww_real_api_enabled=_parse_bool(source.get("GROWW_REAL_API_ENABLED")),
        groww_api_subscription_active=_parse_bool(source.get("GROWW_API_SUBSCRIPTION_ACTIVE")),
        groww_protected_order_client=_parse_bool(source.get("GROWW_PROTECTED_ORDER_CLIENT")),
        groww_static_outbound_ip=_parse_public_ip(source.get("GROWW_STATIC_OUTBOUND_IP")),
        groww_static_ip_allowlisted=_parse_bool(source.get("GROWW_STATIC_IP_ALLOWLISTED")),
        dhan_client_id=source.get("DHAN_CLIENT_ID") or None,
        dhan_access_token=source.get("DHAN_ACCESS_TOKEN") or None,
        dhan_real_api_enabled=_parse_bool(source.get("DHAN_REAL_API_ENABLED")),
        dhan_static_outbound_ip=_parse_public_ip(source.get("DHAN_STATIC_OUTBOUND_IP")),
        dhan_static_ip_allowlisted=_parse_bool(source.get("DHAN_STATIC_IP_ALLOWLISTED")),
        dhan_protected_order_client=_parse_bool(source.get("DHAN_PROTECTED_ORDER_CLIENT")),
        dhan_security_id_map=_parse_symbol_map(source.get("DHAN_SECURITY_ID_MAP")),
        alpaca_paper_trading_enabled=_parse_bool(source.get("ALPACA_PAPER_TRADING_ENABLED"), default=True),
        alpaca_live_trading_enabled=_parse_bool(source.get("ALPACA_LIVE_TRADING_ENABLED")),
        alpaca_account_id=source.get("ALPACA_ACCOUNT_ID") or None,
        alpaca_key_id=source.get("ALPACA_KEY_ID") or None,
        alpaca_secret_key=source.get("ALPACA_SECRET_KEY") or None,
        alpaca_real_api_enabled=_parse_bool(source.get("ALPACA_REAL_API_ENABLED")),
        alpaca_paper_trading_endpoint=_parse_endpoint(
            source.get("ALPACA_PAPER_TRADING_ENDPOINT"),
            default="https://paper-api.alpaca.markets",
            allowed_hosts=frozenset({"paper-api.alpaca.markets"}),
        ),
        alpaca_trading_endpoint=_parse_endpoint(
            source.get("ALPACA_TRADING_ENDPOINT"),
            default="https://api.alpaca.markets",
            allowed_hosts=frozenset({"api.alpaca.markets"}),
        ),
        twilio_alerts_enabled=_parse_bool(source.get("TWILIO_ALERTS_ENABLED")),
        twilio_account_sid=source.get("TWILIO_ACCOUNT_SID") or None,
        twilio_auth_token=source.get("TWILIO_AUTH_TOKEN") or None,
        twilio_from=source.get("TWILIO_FROM") or None,
        twilio_messaging_service_sid=source.get("TWILIO_MESSAGING_SERVICE_SID") or None,
        twilio_status_callback_url=source.get("TWILIO_STATUS_CALLBACK_URL") or None,
        twilio_to=source.get("TWILIO_TO") or None,
    )
