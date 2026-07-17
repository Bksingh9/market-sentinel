from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from market_sentinel.brokers import MockBrokerAdapter
from market_sentinel.config import PrimaryBroker, RuntimeMode, Settings
from market_sentinel.execution import ExecutionAgent
from market_sentinel.models import AccountSnapshot, InstrumentType, OrderIntent, Side


def _missing(required: dict[str, object]) -> list[str]:
    return [name for name, value in required.items() if not value]


def _check(*, enabled: bool, required: dict[str, object]) -> dict[str, object]:
    missing = _missing(required)
    return {
        "enabled": enabled,
        "ready": enabled and not missing,
        "missing": missing,
    }


def live_preflight_report(settings: Settings) -> dict[str, object]:
    account_allowlisted = settings.account_id in settings.account_allowlist
    mode_ready = settings.mode == RuntimeMode.LIVE_SMALL
    groww_credentials_present = bool(
        settings.groww_access_token or (settings.groww_api_key and settings.groww_secret_key)
    )
    alpaca = _check(
        enabled=mode_ready and settings.alpaca_live_trading_enabled and settings.alpaca_real_api_enabled,
        required={
            "MARKET_SENTINEL_MODE=live-small": mode_ready,
            "MARKET_SENTINEL_ACCOUNT_ALLOWLIST includes MARKET_SENTINEL_ACCOUNT_ID": account_allowlisted,
            "ALPACA_LIVE_TRADING_ENABLED": settings.alpaca_live_trading_enabled,
            "ALPACA_REAL_API_ENABLED": settings.alpaca_real_api_enabled,
            "ALPACA_TRADING_ENDPOINT=https://api.alpaca.markets": settings.alpaca_trading_endpoint
            == "https://api.alpaca.markets",
            "ALPACA_ACCOUNT_ID": settings.alpaca_account_id,
            "ALPACA_KEY_ID": settings.alpaca_key_id,
            "ALPACA_SECRET_KEY": settings.alpaca_secret_key,
        },
    )
    groww = _check(
        enabled=mode_ready and settings.india_live_trading_enabled and settings.groww_real_api_enabled,
        required={
            "MARKET_SENTINEL_MODE=live-small": mode_ready,
            "MARKET_SENTINEL_ACCOUNT_ALLOWLIST includes MARKET_SENTINEL_ACCOUNT_ID": account_allowlisted,
            "INDIA_LIVE_TRADING_ENABLED": settings.india_live_trading_enabled,
            "INDIA_ALGO_COMPLIANCE_VERIFIED": settings.india_algo_compliance_verified,
            "GROWW_REAL_API_ENABLED": settings.groww_real_api_enabled,
            "GROWW_API_SUBSCRIPTION_ACTIVE": settings.groww_api_subscription_active,
            "GROWW_PROTECTED_ORDER_CLIENT": settings.groww_protected_order_client,
            "GROWW_STATIC_OUTBOUND_IP": settings.groww_static_outbound_ip,
            "GROWW_STATIC_IP_ALLOWLISTED": settings.groww_static_ip_allowlisted,
            "GROWW_ACCESS_TOKEN or GROWW_API_KEY+GROWW_SECRET_KEY": groww_credentials_present,
            "GROWW_ALGO_ID": settings.groww_algo_id,
        },
    )
    dhan = _check(
        enabled=mode_ready and settings.india_live_trading_enabled and settings.dhan_real_api_enabled,
        required={
            "MARKET_SENTINEL_MODE=live-small": mode_ready,
            "MARKET_SENTINEL_ACCOUNT_ALLOWLIST includes MARKET_SENTINEL_ACCOUNT_ID": account_allowlisted,
            "INDIA_LIVE_TRADING_ENABLED": settings.india_live_trading_enabled,
            "INDIA_ALGO_COMPLIANCE_VERIFIED": settings.india_algo_compliance_verified,
            "DHAN_REAL_API_ENABLED": settings.dhan_real_api_enabled,
            "DHAN_CLIENT_ID": settings.dhan_client_id,
            "DHAN_ACCESS_TOKEN": settings.dhan_access_token,
            "DHAN_STATIC_OUTBOUND_IP": settings.dhan_static_outbound_ip,
            "DHAN_STATIC_IP_ALLOWLISTED": settings.dhan_static_ip_allowlisted,
            "DHAN_PROTECTED_ORDER_CLIENT": settings.dhan_protected_order_client,
            "DHAN_SECURITY_ID_MAP": bool(settings.dhan_security_id_map),
        },
    )
    twilio = _check(
        enabled=settings.twilio_alerts_enabled,
        required={
            "TWILIO_ALERTS_ENABLED": settings.twilio_alerts_enabled,
            "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": settings.twilio_auth_token,
            "TWILIO_TO": settings.twilio_to,
            "TWILIO_FROM or TWILIO_MESSAGING_SERVICE_SID": settings.twilio_from
            or settings.twilio_messaging_service_sid,
        },
    )
    alerts_ready = (not settings.twilio_alerts_enabled) or bool(twilio["ready"])
    broker_checks = {
        PrimaryBroker.ALPACA: alpaca,
        PrimaryBroker.GROWW: groww,
        PrimaryBroker.DHAN: dhan,
    }
    if settings.primary_broker == PrimaryBroker.ANY:
        broker_ready = bool(alpaca["ready"] or groww["ready"] or dhan["ready"])
    else:
        broker_ready = bool(broker_checks[settings.primary_broker]["ready"])
    return {
        "mode": settings.mode.value,
        "primary_broker": settings.primary_broker.value,
        "account_id": settings.account_id,
        "account_allowlisted": account_allowlisted,
        "ready_to_trade": bool(mode_ready and account_allowlisted and broker_ready and alerts_ready),
        "apis": {
            "alpaca": alpaca,
            "groww": groww,
            "dhan": dhan,
        },
        "alerts": {
            "twilio": twilio,
        },
        "ruflo": {
            "role": "supervised-coordinator",
            "can_place_orders": False,
            "order_boundary": "ExecutionAgent",
        },
    }


class RUFLOAgent:
    def checklist_status(self) -> dict[str, object]:
        return {
            "can_place_orders": False,
            "role": "supervised-coordinator",
            "checks": [
                "dependency license review",
                "Groww permissions and India algo obligations",
                "Alpaca account and endpoint separation",
                "Twilio alert delivery and consent setup",
                "independent 60-session paper gates",
            ],
        }

    def paper_evidence(self, store: object) -> dict[str, object]:
        lanes: dict[str, object] = {}
        for market, symbol in (("US", "SPY"), ("IN", "NIFTYBEES")):
            state = store.load(market, symbol)
            lanes[f"{market}:{symbol}"] = (
                {
                    "status": "not-started",
                    "sessions_observed": 0,
                    "required_sessions": 60,
                }
                if state is None
                else {
                    "status": state.status,
                    "sessions_observed": state.sessions_observed,
                    "required_sessions": 60,
                    "calibration_status": state.calibration_status,
                    "drift_status": state.drift_status,
                }
            )
        return {"lanes": lanes, "can_place_orders": False}

    def trading_authority(self) -> dict[str, object]:
        return {
            "can_take_discretionary_calls": False,
            "can_book_profit_autonomously": False,
            "can_place_orders": False,
            "live_order_authority": "execution-agent-only-after-gates",
        }

    def supervised_run_once(self, settings: Settings) -> dict[str, object]:
        if settings.mode != RuntimeMode.PAPER:
            return {
                "mode": settings.mode.value,
                "decision": "blocked",
                "reasons": ["RUFLO supervised run is paper-only"],
                "live_order_submitted": False,
            }
        intent = OrderIntent(
            symbol="SPY",
            market="US",
            instrument_type=InstrumentType.ETF,
            side=Side.BUY,
            quantity=Decimal("1"),
            limit_price=Decimal("500"),
            stop_loss=Decimal("490"),
            take_profit=Decimal("515"),
            strategy_id="ruflo-supervised-paper",
        )
        broker = MockBrokerAdapter()
        decision = ExecutionAgent(settings, broker).submit(
            intent,
            AccountSnapshot(settings.account_id, Decimal("100000"), Decimal("100000")),
            [],
            now=datetime.now(timezone.utc),
        )
        return {
            "mode": settings.mode.value,
            "decision": "allowed" if decision.allowed else "blocked",
            "reasons": list(decision.reasons),
            "broker": broker.name,
            "symbol": intent.symbol,
            "live_order_submitted": False,
        }
