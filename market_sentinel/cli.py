from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from market_sentinel.analysis import AnalysisAgent
from market_sentinel.config import load_settings
from market_sentinel.model_store import ModelStore
from market_sentinel.model_training import TrainingExample, train_linear_model
from market_sentinel.ruflo import RUFLOAgent, live_preflight_report


MODEL_PROMOTION_THRESHOLD = Decimal("0.9000")


def _status() -> dict[str, object]:
    settings = load_settings()
    return {
        "mode": settings.mode.value,
        "account_id": settings.account_id,
        "live_small_blocked_by_default": settings.mode.value != "live-small",
        "apis": {
            "alpaca_real_api_enabled": settings.alpaca_real_api_enabled,
            "alpaca_credentials_present": bool(settings.alpaca_key_id and settings.alpaca_secret_key),
            "groww_real_api_enabled": settings.groww_real_api_enabled,
            "groww_credentials_present": bool(settings.groww_access_token and settings.groww_algo_id),
            "twilio_alerts_enabled": settings.twilio_alerts_enabled,
            "twilio_credentials_present": bool(settings.twilio_account_sid and settings.twilio_auth_token),
            "twilio_sender_configured": bool(settings.twilio_messaging_service_sid or settings.twilio_from),
            "twilio_messaging_service_configured": bool(settings.twilio_messaging_service_sid),
            "twilio_status_callback_configured": bool(settings.twilio_status_callback_url),
        },
        "live_preflight": live_preflight_report(settings),
        "ruflo": RUFLOAgent().checklist_status(),
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
            {"name": "Four-week paper gate", "state": "not-started"},
            {"name": "Live-small compliance", "state": "blocked"},
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
