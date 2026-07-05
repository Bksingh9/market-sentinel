from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
import os


class RuntimeMode(StrEnum):
    DISABLED = "disabled"
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE_SMALL = "live-small"
    EMERGENCY = "emergency"


@dataclass(frozen=True)
class Settings:
    mode: RuntimeMode = RuntimeMode.DISABLED
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
    groww_access_token: str | None = None
    groww_real_api_enabled: bool = False
    alpaca_paper_trading_enabled: bool = True
    alpaca_live_trading_enabled: bool = False
    alpaca_account_id: str | None = None
    alpaca_key_id: str | None = None
    alpaca_secret_key: str | None = None
    alpaca_real_api_enabled: bool = False
    twilio_alerts_enabled: bool = False
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from: str | None = None
    twilio_to: str | None = None


def _parse_mode(value: str | None) -> RuntimeMode:
    if value in {mode.value for mode in RuntimeMode}:
        return RuntimeMode(value)
    return RuntimeMode.DISABLED


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_allowlist(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset({"paper-local"})
    entries = {item.strip() for item in value.split(",") if item.strip()}
    return frozenset(entries or {"paper-local"})


def load_settings(env: dict[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env
    return Settings(
        mode=_parse_mode(source.get("MARKET_SENTINEL_MODE")),
        account_id=source.get("MARKET_SENTINEL_ACCOUNT_ID", "paper-local"),
        account_allowlist=_parse_allowlist(source.get("MARKET_SENTINEL_ACCOUNT_ALLOWLIST")),
        india_live_trading_enabled=_parse_bool(source.get("INDIA_LIVE_TRADING_ENABLED")),
        india_algo_compliance_verified=_parse_bool(source.get("INDIA_ALGO_COMPLIANCE_VERIFIED")),
        groww_algo_id=source.get("GROWW_ALGO_ID") or None,
        groww_access_token=source.get("GROWW_ACCESS_TOKEN") or None,
        groww_real_api_enabled=_parse_bool(source.get("GROWW_REAL_API_ENABLED")),
        alpaca_paper_trading_enabled=_parse_bool(source.get("ALPACA_PAPER_TRADING_ENABLED"), default=True),
        alpaca_live_trading_enabled=_parse_bool(source.get("ALPACA_LIVE_TRADING_ENABLED")),
        alpaca_account_id=source.get("ALPACA_ACCOUNT_ID") or None,
        alpaca_key_id=source.get("ALPACA_KEY_ID") or None,
        alpaca_secret_key=source.get("ALPACA_SECRET_KEY") or None,
        alpaca_real_api_enabled=_parse_bool(source.get("ALPACA_REAL_API_ENABLED")),
        twilio_alerts_enabled=_parse_bool(source.get("TWILIO_ALERTS_ENABLED")),
        twilio_account_sid=source.get("TWILIO_ACCOUNT_SID") or None,
        twilio_auth_token=source.get("TWILIO_AUTH_TOKEN") or None,
        twilio_from=source.get("TWILIO_FROM") or None,
        twilio_to=source.get("TWILIO_TO") or None,
    )
