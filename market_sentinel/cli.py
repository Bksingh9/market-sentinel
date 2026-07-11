from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from market_sentinel.analysis import AnalysisAgent
from market_sentinel.brokers import AlpacaBrokerAdapter, GrowwBrokerAdapter, GrowwSDKClient
from market_sentinel.config import load_settings
from market_sentinel.execution import ExecutionAgent
from market_sentinel.model_store import ModelStore
from market_sentinel.model_training import TrainingExample, train_linear_model
from market_sentinel.models import AccountSnapshot, InstrumentType, OrderIntent, Side
from market_sentinel.ruflo import RUFLOAgent, live_preflight_report


MODEL_PROMOTION_THRESHOLD = Decimal("0.9000")
REAL_ORDER_CONFIRMATION = "I_CONFIRM_REAL_MONEY_ORDER"


def _status() -> dict[str, object]:
    settings = load_settings()
    deployment = _deployment_status()
    return {
        "mode": settings.mode.value,
        "primary_broker": settings.primary_broker.value,
        "account_id": settings.account_id,
        "live_small_blocked_by_default": settings.mode.value != "live-small",
        "apis": {
            "alpaca_real_api_enabled": settings.alpaca_real_api_enabled,
            "alpaca_credentials_present": bool(settings.alpaca_key_id and settings.alpaca_secret_key),
            "groww_real_api_enabled": settings.groww_real_api_enabled,
            "groww_credentials_present": bool(
                settings.groww_algo_id
                and (
                    settings.groww_access_token
                    or (settings.groww_api_key and settings.groww_secret_key)
                )
            ),
            "groww_static_ip_configured": bool(
                settings.groww_static_outbound_ip and settings.groww_static_ip_allowlisted
            ),
            "dhan_real_api_enabled": settings.dhan_real_api_enabled,
            "dhan_credentials_present": bool(settings.dhan_client_id and settings.dhan_access_token),
            "dhan_static_ip_configured": bool(
                settings.dhan_static_outbound_ip and settings.dhan_static_ip_allowlisted
            ),
            "dhan_security_map_present": bool(settings.dhan_security_id_map),
            "twilio_alerts_enabled": settings.twilio_alerts_enabled,
            "twilio_credentials_present": bool(settings.twilio_account_sid and settings.twilio_auth_token),
            "twilio_sender_configured": bool(settings.twilio_messaging_service_sid or settings.twilio_from),
            "twilio_messaging_service_configured": bool(settings.twilio_messaging_service_sid),
            "twilio_status_callback_configured": bool(settings.twilio_status_callback_url),
        },
        "live_preflight": live_preflight_report(settings),
        "ruflo": RUFLOAgent().checklist_status(),
        "deployment": deployment,
    }


def _deployment_status() -> dict[str, object]:
    return {
        "public_control_center": "read-only",
        "private_execution": "local-supervised",
        "selected_tunnel": "cloudflare/cloudflared",
        "tunnel_license": "Apache-2.0",
        "tunnel_access_policy": "Cloudflare Access or equivalent identity gate required",
        "live_order_endpoint_public": False,
        "broker_secrets_public": False,
        "operator_confirmation_required": REAL_ORDER_CONFIRMATION,
        "public_dashboard_url": None,
    }


def _training_dataset() -> tuple[list[TrainingExample], list[TrainingExample]]:
    train: list[TrainingExample] = []
    validation: list[TrainingExample] = []
    for index in range(1, 21):
        momentum = (Decimal(index) / Decimal("10")).quantize(Decimal("0.0001"))
        volume = (Decimal("1") + (Decimal(index % 5) / Decimal("10"))).quantize(Decimal("0.0001"))
        positive = TrainingExample({"momentum": momentum, "average_volume": volume}, 1)
        negative = TrainingExample({"momentum": -momentum, "average_volume": volume}, 0)
        if index % 4 == 0:
            validation.extend([positive, negative])
        else:
            train.extend([positive, negative])
    return train, validation


def _train_model(model_dir: Path) -> str:
    train, validation = _training_dataset()
    model = train_linear_model(
        train,
        validation_examples=validation,
        epochs=20,
        promotion_threshold=MODEL_PROMOTION_THRESHOLD,
    )
    store = ModelStore(model_dir)
    store.save(model)
    if not model.promoted:
        raise RuntimeError(
            f"model accuracy {model.accuracy} is below promotion threshold {model.promotion_threshold}"
        )
    store.activate(model.version)
    return model.version


def _model_status(model_dir: Path) -> dict[str, object]:
    store = ModelStore(model_dir)
    try:
        model = store.load_active()
    except FileNotFoundError:
        return {
            "mode": "advisory",
            "active_version": "untrained-baseline",
            "last_trained_at": None,
            "accuracy": None,
            "validation_rows": 0,
            "promotion_threshold": str(MODEL_PROMOTION_THRESHOLD),
            "promoted": False,
            "feature_set": ["momentum", "average_volume"],
            "can_place_orders": False,
        }
    return {
        "mode": "advisory",
        "active_version": model.version,
        "last_trained_at": model.created_at,
        "accuracy": str(model.accuracy),
        "validation_rows": model.validation_rows,
        "promotion_threshold": str(model.promotion_threshold),
        "promoted": model.promoted,
        "feature_set": list(model.feature_names),
        "can_place_orders": False,
    }


def _export_dashboard(path: Path, *, model_dir: Path = Path("data/models")) -> None:
    data = {
        "status": _status(),
        "model": _model_status(model_dir),
        "scheduled_orders": [
            {
                "id": "paper-open-check",
                "symbol": "SPY",
                "market": "US",
                "eligible_at": "2026-07-06T13:30:00+00:00",
                "expires_at": "2026-07-06T20:00:00+00:00",
                "status": "pending",
                "model_version": _model_status(model_dir)["active_version"],
                "gate": "must pass fresh risk and compliance checks",
            }
        ],
        "equity_summary": {
            key: str(value)
            for key, value in AnalysisAgent().summarize_equity([Decimal("100000"), Decimal("100500"), Decimal("100100")]).items()
        },
        "validation_gates": [
            {"name": "Unit tests", "state": "ready"},
            {
                "name": "Model accuracy gate",
                "state": "ready" if _model_status(model_dir)["promoted"] else "blocked",
            },
            {"name": "Read-only public dashboard", "state": "ready"},
            {"name": "Private execution tunnel", "state": "blocked"},
            {"name": "Four-week paper gate", "state": "not-started"},
            {"name": "Live-small compliance", "state": "blocked"},
        ],
        "deployment": _deployment_status(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _submit_order(args: argparse.Namespace) -> int:
    if args.confirm_real_money != REAL_ORDER_CONFIRMATION:
        print(
            json.dumps(
                {
                    "decision": "blocked",
                    "reasons": [
                        f"--confirm-real-money must equal {REAL_ORDER_CONFIRMATION}",
                    ],
                    "live_order_submitted": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    settings = load_settings()
    report = live_preflight_report(settings)
    broker_name = args.broker or settings.primary_broker.value
    if broker_name == "any":
        print(
            json.dumps(
                {
                    "decision": "blocked",
                    "reasons": ["broker must be groww or alpaca for live order submission"],
                    "live_order_submitted": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    if settings.primary_broker.value not in {"any", broker_name}:
        print(
            json.dumps(
                {
                    "decision": "blocked",
                    "reasons": [f"primary broker is {settings.primary_broker.value}, not {broker_name}"],
                    "live_order_submitted": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    if not report["ready_to_trade"]:
        print(
            json.dumps(
                {
                    "decision": "blocked",
                    "reasons": ["live preflight is not ready"],
                    "live_order_submitted": False,
                    "preflight": report,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    if not report["apis"][broker_name]["ready"]:
        print(
            json.dumps(
                {
                    "decision": "blocked",
                    "reasons": [f"{broker_name} preflight is not ready"],
                    "live_order_submitted": False,
                    "preflight": report,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    market = args.market or ("IN" if broker_name == "groww" else "US")
    intent = OrderIntent(
        symbol=args.symbol.upper(),
        market=market,
        instrument_type=InstrumentType(args.instrument_type),
        side=Side(args.side),
        quantity=Decimal(args.quantity),
        limit_price=Decimal(args.limit_price),
        stop_loss=Decimal(args.stop_loss),
        take_profit=Decimal(args.take_profit),
        strategy_id=args.strategy_id,
    )
    if broker_name == "groww":
        broker = GrowwBrokerAdapter(settings, groww_client=GrowwSDKClient.from_settings(settings))
    elif broker_name == "alpaca":
        broker = AlpacaBrokerAdapter(settings)
    else:
        print(
            json.dumps(
                {
                    "decision": "blocked",
                    "reasons": [f"unsupported live broker: {broker_name}"],
                    "live_order_submitted": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    decision = ExecutionAgent(settings, broker).submit(
        intent,
        AccountSnapshot(
            account_id=settings.account_id,
            cash=Decimal(args.account_cash),
            equity=Decimal(args.account_equity),
        ),
        [],
        now=datetime.now(timezone.utc),
    )
    print(
        json.dumps(
            {
                "decision": "allowed" if decision.allowed else "blocked",
                "reasons": list(decision.reasons),
                "broker": broker_name,
                "symbol": intent.symbol,
                "side": intent.side.value,
                "quantity": str(intent.quantity),
                "limit_price": str(intent.limit_price),
                "stop_loss": str(intent.stop_loss),
                "take_profit": str(intent.take_profit),
                "live_order_submitted": decision.allowed,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if decision.allowed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="market-sentinel")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    subcommands.add_parser("live-preflight")
    subcommands.add_parser("ruflo-run-once")
    train_parser = subcommands.add_parser("train-model")
    train_parser.add_argument("--model-dir", default="data/models")
    export_parser = subcommands.add_parser("export-dashboard")
    export_parser.add_argument("--path", default="apps/control-center/public/status.json")
    export_parser.add_argument("--model-dir", default="data/models")
    order_parser = subcommands.add_parser("submit-order")
    order_parser.add_argument("--broker", choices=["groww", "alpaca"])
    order_parser.add_argument("--symbol", required=True)
    order_parser.add_argument("--market", choices=["IN", "US"])
    order_parser.add_argument("--instrument-type", choices=[item.value for item in InstrumentType], default="equity")
    order_parser.add_argument("--side", choices=["buy", "sell"], required=True)
    order_parser.add_argument("--quantity", required=True)
    order_parser.add_argument("--limit-price", required=True)
    order_parser.add_argument("--stop-loss", required=True)
    order_parser.add_argument("--take-profit", required=True)
    order_parser.add_argument("--strategy-id", default="manual-supervised")
    order_parser.add_argument("--account-cash", default="100000")
    order_parser.add_argument("--account-equity", default="100000")
    order_parser.add_argument("--confirm-real-money", required=True)
    args = parser.parse_args(argv)

    if args.command == "status":
        print(json.dumps(_status(), indent=2, sort_keys=True))
        return 0
    if args.command == "live-preflight":
        print(json.dumps(live_preflight_report(load_settings()), indent=2, sort_keys=True))
        return 0
    if args.command == "ruflo-run-once":
        print(json.dumps(RUFLOAgent().supervised_run_once(load_settings()), indent=2, sort_keys=True))
        return 0
    if args.command == "train-model":
        version = _train_model(Path(args.model_dir))
        print(json.dumps({"active_version": version}, indent=2, sort_keys=True))
        return 0
    if args.command == "export-dashboard":
        _export_dashboard(Path(args.path), model_dir=Path(args.model_dir))
        return 0
    if args.command == "submit-order":
        return _submit_order(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
