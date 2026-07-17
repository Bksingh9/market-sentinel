from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any, Callable

from market_sentinel.api_clients import UrllibHttpClient
from market_sentinel.config import Settings, load_settings
from market_sentinel.dataset_store import DatasetStore
from market_sentinel.historical_clients import (
    AlpacaHistoricalClient,
    GrowwHistoricalClient,
    sanitize_provider_error,
)
from market_sentinel.historical_data import (
    AdjustmentMode,
    expected_sessions,
    validate_daily_bars,
)
from market_sentinel.ml_evaluation import (
    evaluate_fold,
    evaluate_validation,
    replay_fold,
    select_calibration_configuration,
)
from market_sentinel.ml_features import (
    FEATURE_ORDER,
    FEATURE_SCHEMA_VERSION,
    CandidateRule,
    FeatureRow,
    build_feature_rows,
    is_market_candidate,
)
from market_sentinel.ml_labels import (
    CostBreakdown,
    CostProfile,
    CostSchedule,
    MetaLabelRow,
    label_candidate,
)
from market_sentinel.ml_validation import (
    WalkForwardConfig,
    assert_oos_eligibility,
    build_walk_forward_folds,
)
from market_sentinel.model_store import ModelStore
from market_sentinel.model_training import fit_fold_model, predict_probability
from market_sentinel.models import InstrumentType
from market_sentinel.ruflo import RUFLOAgent, live_preflight_report
from market_sentinel.trial_ledger import TrialLedger, TrialRecord


REAL_ORDER_CONFIRMATION = "I_CONFIRM_REAL_MONEY_ORDER"
LABEL_VERSION = "protected-2-3-10-v1"
LANES = {
    ("US", "SPY"): {
        "provider": "alpaca",
        "currency": "USD",
        "adjustment": "all",
        "minimum_average_volume": "1000000",
        "maximum_volatility_20": "0.05",
    },
    ("IN", "NIFTYBEES"): {
        "provider": "groww",
        "currency": "INR",
        "adjustment": "provider-unspecified",
        "minimum_average_volume": "100000",
        "maximum_volatility_20": "0.05",
    },
}


def _lane(market: str, symbol: str) -> dict[str, str]:
    try:
        return LANES[(market, symbol)]
    except KeyError as exc:
        raise ValueError("only US/SPY and IN/NIFTYBEES are supported") from exc


def _status() -> dict[str, object]:
    settings = load_settings()
    return {
        "mode": settings.mode.value,
        "primary_broker": settings.primary_broker.value,
        "account_id": settings.account_id,
        "live_small_blocked_by_default": settings.mode.value != "live-small",
        "apis": {
            "alpaca_real_api_enabled": settings.alpaca_real_api_enabled,
            "alpaca_credentials_present": bool(
                settings.alpaca_key_id and settings.alpaca_secret_key
            ),
            "groww_real_api_enabled": settings.groww_real_api_enabled,
            "groww_credentials_present": bool(
                settings.groww_algo_id
                and (
                    settings.groww_access_token
                    or (settings.groww_api_key and settings.groww_secret_key)
                )
            ),
            "groww_static_ip_configured": bool(
                settings.groww_static_outbound_ip
                and settings.groww_static_ip_allowlisted
            ),
            "dhan_real_api_enabled": settings.dhan_real_api_enabled,
            "dhan_credentials_present": bool(
                settings.dhan_client_id and settings.dhan_access_token
            ),
            "dhan_static_ip_configured": bool(
                settings.dhan_static_outbound_ip
                and settings.dhan_static_ip_allowlisted
            ),
            "dhan_security_map_present": bool(settings.dhan_security_id_map),
            "twilio_alerts_enabled": settings.twilio_alerts_enabled,
            "twilio_credentials_present": bool(
                settings.twilio_account_sid and settings.twilio_auth_token
            ),
            "twilio_sender_configured": bool(
                settings.twilio_messaging_service_sid or settings.twilio_from
            ),
            "twilio_messaging_service_configured": bool(
                settings.twilio_messaging_service_sid
            ),
            "twilio_status_callback_configured": bool(
                settings.twilio_status_callback_url
            ),
        },
        "live_preflight": live_preflight_report(settings),
        "ruflo": RUFLOAgent().checklist_status(),
        "deployment": _deployment_status(),
    }


def _deployment_status() -> dict[str, object]:
    return {
        "public_control_center": "read-only",
        "private_execution": "local-supervised",
        "selected_tunnel": "cloudflare/cloudflared",
        "tunnel_access_policy": (
            "Cloudflare Access or equivalent identity gate required"
        ),
        "live_order_endpoint_public": False,
        "broker_secrets_public": False,
        "operator_confirmation_required": REAL_ORDER_CONFIRMATION,
        "public_dashboard_url": None,
    }


def _assert_challenger_month_available(
    records: tuple[TrialRecord, ...],
    market: str,
    symbol: str,
    as_of: datetime,
) -> None:
    month = as_of.strftime("%Y-%m")
    if any(
        record.stage == "walk-forward-validation"
        and record.market == market
        and record.symbol == symbol
        and record.created_at[:7] == month
        for record in records
    ):
        raise RuntimeError(f"challenger already created for {month}")


def _download_data(
    args: argparse.Namespace,
    *,
    settings: Settings | None = None,
    http_client: Any | None = None,
    groww_sdk: Any | None = None,
    store: DatasetStore | None = None,
) -> dict[str, object]:
    lane = _lane(args.market, args.symbol)
    current_settings = settings or load_settings()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if lane["provider"] == "alpaca":
        if not (
            current_settings.alpaca_key_id
            and current_settings.alpaca_secret_key
        ):
            raise ValueError("Alpaca historical credentials are not configured")
        client = AlpacaHistoricalClient(
            http_client or UrllibHttpClient(),
            key_id=current_settings.alpaca_key_id,
            secret_key=current_settings.alpaca_secret_key,
        )
        client.endpoint = (
            current_settings.alpaca_market_data_endpoint + "/v2/stocks/bars"
        )
        download = client.download(
            symbol=args.symbol,
            start=start,
            end=end,
            feed="iex",
        )
        feed = "iex"
    else:
        sdk = groww_sdk or _create_groww_historical_sdk(current_settings)
        download = GrowwHistoricalClient(sdk).download(
            symbol=args.symbol,
            start=start,
            end=end,
        )
        feed = None
    adjustment = AdjustmentMode(lane["adjustment"])
    validated = validate_daily_bars(
        download.bars,
        expected_symbol=args.symbol,
        expected_market=args.market,
        expected_currency=lane["currency"],
        expected_adjustment=adjustment,
        last_completed_session=end,
    )
    stored = (store or DatasetStore(Path(args.data_root))).write(
        validated,
        requested_start=start,
        requested_end=end,
        interval="1Day",
        page_count=download.page_count,
        feed=feed,
    )
    return {
        "status": "stored",
        "market": args.market,
        "symbol": args.symbol,
        "dataset_id": stored.manifest.dataset_id,
        "rows": stored.manifest.row_count,
        "first_trading_date": stored.manifest.first_trading_date.isoformat(),
        "last_trading_date": stored.manifest.last_trading_date.isoformat(),
    }


def _create_groww_historical_sdk(settings: Settings) -> Any:
    from growwapi import GrowwAPI

    if settings.groww_access_token:
        return GrowwAPI(settings.groww_access_token)
    if settings.groww_api_key and settings.groww_secret_key:
        token = GrowwAPI.get_access_token(
            api_key=settings.groww_api_key,
            secret=settings.groww_secret_key,
        )
        return GrowwAPI(token)
    raise ValueError("Groww historical credentials are not configured")


def _build_dataset(
    args: argparse.Namespace,
    *,
    store: DatasetStore | None = None,
) -> dict[str, object]:
    lane = _lane(args.market, args.symbol)
    dataset_store = store or DatasetStore(Path(args.data_root))
    manifest, bars = dataset_store.load(
        args.market,
        args.symbol,
        args.dataset_id,
    )
    record_id, reconciled_dates = _corporate_action_record(
        None
        if args.corporate_action_record is None
        else Path(args.corporate_action_record)
    )
    validate_daily_bars(
        bars,
        expected_symbol=args.symbol,
        expected_market=args.market,
        expected_currency=lane["currency"],
        expected_adjustment=AdjustmentMode(lane["adjustment"]),
        last_completed_session=manifest.last_trading_date,
        reconciled_discontinuity_dates=reconciled_dates,
    )
    profile = _load_cost_profile(Path(args.cost_profile))
    rule = CandidateRule(
        Decimal(lane["minimum_average_volume"]),
        Decimal(lane["maximum_volatility_20"]),
    )
    feature_rows = build_feature_rows(bars)
    bar_positions = {item.trading_date: index for index, item in enumerate(bars)}
    labeled: list[MetaLabelRow] = []
    for row in feature_rows:
        if not is_market_candidate(row, rule):
            continue
        start_index = bar_positions[row.entry_eligible_at]
        future = bars[start_index : start_index + 10]
        if len(future) == 10:
            labeled.append(label_candidate(row, future, profile))
    payload = {
        "dataset_id": manifest.dataset_id,
        "dataset_checksum": manifest.dataset_id,
        "market": args.market,
        "symbol": args.symbol,
        "currency": lane["currency"],
        "feature_schema": FEATURE_SCHEMA_VERSION,
        "label_version": LABEL_VERSION,
        "cost_profile_version": profile.version,
        "reconciliation_record_id": record_id,
        "sessions": [item.trading_date.isoformat() for item in bars],
        "rows": [_meta_label_to_payload(item) for item in labeled],
    }
    research_path = _research_path(
        Path(args.data_root),
        args.market,
        args.symbol,
        args.dataset_id,
    )
    _write_immutable_json(research_path, payload)
    return {
        "status": "built",
        "dataset_id": manifest.dataset_id,
        "candidate_rows": len(labeled),
        "feature_schema": FEATURE_SCHEMA_VERSION,
        "label_version": LABEL_VERSION,
    }


def _train_market_model(
    args: argparse.Namespace,
    *,
    now: datetime | None = None,
    data_store: DatasetStore | None = None,
    model_store: ModelStore | None = None,
    ledger: TrialLedger | None = None,
) -> dict[str, object]:
    _lane(args.market, args.symbol)
    store = data_store or DatasetStore(Path(args.data_root))
    manifest, _ = store.load(args.market, args.symbol, args.dataset_id)
    research = _load_research_payload(
        _research_path(
            Path(args.data_root),
            args.market,
            args.symbol,
            args.dataset_id,
        )
    )
    rows = tuple(_meta_label_from_payload(item) for item in research["rows"])
    sessions = tuple(date.fromisoformat(item) for item in research["sessions"])
    config = WalkForwardConfig()
    folds = build_walk_forward_folds(rows, sessions, config)
    assert_oos_eligibility(rows, folds, config)
    timestamp = now or datetime.now(timezone.utc)
    trial_ledger = ledger or TrialLedger(
        Path(args.trial_root) / args.market / args.symbol / "trials.jsonl"
    )
    existing_records = trial_ledger.read_all()
    _assert_challenger_month_available(
        existing_records,
        args.market,
        args.symbol,
        timestamp,
    )
    candidate_version = (
        f"{args.market.lower()}-{args.symbol.lower()}-"
        f"{timestamp.strftime('%Y%m%d%H%M%S')}"
    )
    fold_metrics = []
    fold_artifacts = []
    for fold in folds:
        fit_rows = tuple(rows[index] for index in fold.fit_indices)
        calibration_rows = tuple(
            rows[index] for index in fold.calibration_indices
        )
        test_rows = tuple(rows[index] for index in fold.test_indices)
        probabilities_by_c: dict[Decimal, tuple[Decimal, ...]] = {}
        artifacts_by_c = {}
        for c_value in (Decimal("0.1"), Decimal("1.0"), Decimal("10.0")):
            artifact = fit_fold_model(
                fit_rows,
                calibration_rows,
                c_value=c_value,
                threshold=Decimal("0.55"),
                metadata=_fold_metadata(
                    candidate_version,
                    fold.fold_id,
                    manifest,
                    research,
                    fit_rows,
                    calibration_rows,
                    timestamp,
                ),
            )
            artifacts_by_c[c_value] = artifact
            probabilities_by_c[c_value] = tuple(
                predict_probability(artifact, item.feature_row)
                for item in calibration_rows
            )
        choice = select_calibration_configuration(
            calibration_rows,
            probabilities_by_c,
        )
        for c_value, probabilities in probabilities_by_c.items():
            for threshold in (
                Decimal("0.55"),
                Decimal("0.60"),
                Decimal("0.65"),
            ):
                accepted = tuple(
                    probability >= threshold for probability in probabilities
                )
                replay = replay_fold(calibration_rows, accepted)
                trial_ledger.append(
                    TrialRecord(
                        trial_id=(
                            f"{candidate_version}-{fold.fold_id}-"
                            f"c{c_value}-t{threshold}"
                        ),
                        stage="calibration-selection",
                        market=args.market,
                        symbol=args.symbol,
                        dataset_id=manifest.dataset_id,
                        dataset_checksum=manifest.dataset_id,
                        dataset_range=(
                            manifest.first_trading_date.isoformat(),
                            manifest.last_trading_date.isoformat(),
                        ),
                        feature_schema=FEATURE_SCHEMA_VERSION,
                        label_version=LABEL_VERSION,
                        cost_profile_version=str(
                            research["cost_profile_version"]
                        ),
                        fold_definitions=(_fold_to_payload(fold),),
                        c_value=c_value,
                        threshold_candidates=(threshold,),
                        selected_threshold=threshold
                        if (c_value, threshold)
                        == (choice.c_value, choice.threshold)
                        else None,
                        fold_metrics=(),
                        aggregate_metrics={
                            "coverage": Decimal(sum(accepted))
                            / Decimal(len(accepted)),
                            "expectancy": replay.expectancy,
                            "maximum_drawdown": replay.maximum_drawdown,
                        },
                        promoted_for_paper=False,
                        failure_reasons=(),
                        code_commit=_code_commit(),
                        created_at=timestamp.isoformat(),
                    )
                )
        selected = fit_fold_model(
            fit_rows,
            calibration_rows,
            c_value=choice.c_value,
            threshold=choice.threshold,
            metadata=_fold_metadata(
                candidate_version,
                fold.fold_id,
                manifest,
                research,
                fit_rows,
                calibration_rows,
                timestamp,
            ),
        )
        probabilities = tuple(
            predict_probability(selected, item.feature_row) for item in test_rows
        )
        prevalence = Decimal(sum(item.label for item in fit_rows)) / Decimal(
            len(fit_rows)
        )
        fold_metrics.append(
            evaluate_fold(
                fold.fold_id,
                test_rows,
                probabilities,
                threshold=choice.threshold,
                training_prevalence=prevalence,
            )
        )
        fold_artifacts.append(selected)
    report = evaluate_validation(
        fold_metrics,
        attempted_configurations=9 * len(folds),
    )
    target_store = model_store or ModelStore(Path(args.model_root))
    parent_pointer = (
        Path(args.model_root)
        / args.market
        / args.symbol
        / "active-paper.txt"
    )
    parent = (
        parent_pointer.read_text(encoding="utf-8").strip()
        if parent_pointer.exists()
        else None
    )
    final = replace(
        fold_artifacts[-1],
        version=candidate_version,
        test_ranges=tuple(
            (
                rows[min(fold.test_indices)].feature_row.feature_as_of.isoformat(),
                rows[max(fold.test_indices)].feature_row.feature_as_of.isoformat(),
            )
            for fold in folds
        ),
        fold_metrics=tuple(_json_safe(asdict(item)) for item in fold_metrics),
        aggregate_metrics=_json_safe(report.aggregate_metrics),
        promoted_for_paper=report.promoted_for_paper,
        failure_reasons=report.failure_reasons,
        parent_champion_version=parent,
    )
    target_store.save(final)
    trial_ledger.append(
        TrialRecord(
            trial_id=f"{candidate_version}-validation",
            stage="walk-forward-validation",
            market=args.market,
            symbol=args.symbol,
            dataset_id=manifest.dataset_id,
            dataset_checksum=manifest.dataset_id,
            dataset_range=(
                manifest.first_trading_date.isoformat(),
                manifest.last_trading_date.isoformat(),
            ),
            feature_schema=FEATURE_SCHEMA_VERSION,
            label_version=LABEL_VERSION,
            cost_profile_version=str(research["cost_profile_version"]),
            fold_definitions=tuple(_fold_to_payload(item) for item in folds),
            c_value=final.c_value,
            threshold_candidates=(
                Decimal("0.55"),
                Decimal("0.60"),
                Decimal("0.65"),
            ),
            selected_threshold=final.threshold,
            fold_metrics=final.fold_metrics,
            aggregate_metrics=final.aggregate_metrics,
            promoted_for_paper=final.promoted_for_paper,
            failure_reasons=final.failure_reasons,
            code_commit=_code_commit(),
            created_at=timestamp.isoformat(),
        )
    )
    return {
        "status": "validated" if final.promoted_for_paper else "failed",
        "version": final.version,
        "promoted_for_paper": final.promoted_for_paper,
        "failure_reasons": list(final.failure_reasons),
        "active_pointer_changed": False,
    }


def _validate_market_model(args: argparse.Namespace) -> dict[str, object]:
    artifact = ModelStore(Path(args.model_root)).load(
        args.market,
        args.symbol,
        args.version,
    )
    return {
        "version": artifact.version,
        "market": artifact.market,
        "symbol": artifact.symbol,
        "promoted_for_paper": artifact.promoted_for_paper,
        "failure_reasons": list(artifact.failure_reasons),
        "aggregate_metrics": _json_safe(artifact.aggregate_metrics),
    }


def _promote_to_paper(args: argparse.Namespace) -> dict[str, object]:
    store = ModelStore(Path(args.model_root))
    artifact = store.load(args.market, args.symbol, args.version)
    if not artifact.promoted_for_paper:
        raise ValueError("failed validation cannot activate a paper model")
    store.activate_for_paper(args.market, args.symbol, args.version)
    return {
        "status": "active-for-paper",
        "market": args.market,
        "symbol": args.symbol,
        "version": args.version,
        "live_mode_changed": False,
    }


def _paper_status(args: argparse.Namespace) -> dict[str, object]:
    path = Path(args.paper_root) / args.market / args.symbol / "state.json"
    if not path.exists():
        return {
            "market": args.market,
            "symbol": args.symbol,
            "status": "not-started",
            "sessions_observed": 0,
            "required_sessions": 60,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _submit_order(args: argparse.Namespace) -> int:
    from market_sentinel.brokers import (
        AlpacaBrokerAdapter,
        GrowwBrokerAdapter,
        GrowwSDKClient,
    )
    from market_sentinel.execution import ExecutionAgent
    from market_sentinel.models import (
        AccountSnapshot,
        OrderIntent,
        Side,
    )

    if args.confirm_real_money != REAL_ORDER_CONFIRMATION:
        _print_json(
            {
                "decision": "blocked",
                "reasons": [
                    f"--confirm-real-money must equal {REAL_ORDER_CONFIRMATION}",
                ],
                "live_order_submitted": False,
            }
        )
        return 2
    settings = load_settings()
    report = live_preflight_report(settings)
    broker_name = args.broker or settings.primary_broker.value
    if broker_name == "any":
        _print_json(
            {
                "decision": "blocked",
                "reasons": ["broker must be groww or alpaca for live order submission"],
                "live_order_submitted": False,
            }
        )
        return 2
    if settings.primary_broker.value not in {"any", broker_name}:
        _print_json(
            {
                "decision": "blocked",
                "reasons": [
                    f"primary broker is {settings.primary_broker.value}, not {broker_name}"
                ],
                "live_order_submitted": False,
            }
        )
        return 2
    if not report["ready_to_trade"] or not report["apis"][broker_name]["ready"]:
        _print_json(
            {
                "decision": "blocked",
                "reasons": ["live preflight is not ready"],
                "live_order_submitted": False,
                "preflight": report,
            }
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
    broker = (
        GrowwBrokerAdapter(
            settings,
            groww_client=GrowwSDKClient.from_settings(settings),
        )
        if broker_name == "groww"
        else AlpacaBrokerAdapter(settings)
    )
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
    _print_json(
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
        }
    )
    return 0 if decision.allowed else 1


def _export_dashboard(
    path: Path,
    *,
    model_dir: Path = Path("data/models"),
    data_root: Path = Path("data/datasets"),
    paper_root: Path = Path("data/paper"),
) -> None:
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "historical-validation-and-paper-only",
        "lanes": {
            "US:SPY": _lane_dashboard_status(
                "US", "SPY", "Alpaca", "Alpaca paper", model_dir, data_root, paper_root
            ),
            "IN:NIFTYBEES": _lane_dashboard_status(
                "IN", "NIFTYBEES", "Groww", "local simulator", model_dir, data_root, paper_root
            ),
        },
        "disclaimer": (
            "Historical and paper results do not guarantee future performance. "
            "Real-money activation is outside this workflow."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(data), indent=2, sort_keys=True), encoding="utf-8")


def _lane_dashboard_status(
    market: str,
    symbol: str,
    provider: str,
    execution_target: str,
    model_dir: Path,
    data_root: Path,
    paper_root: Path,
) -> dict[str, object]:
    blocked: list[str] = []
    lane_data_root = data_root / market / symbol
    manifests = sorted(lane_data_root.glob("*/manifest.json")) if lane_data_root.exists() else []
    data_status: dict[str, object] = {"source": provider, "available": False}
    if manifests:
        manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
        data_status = {
            "source": provider,
            "available": True,
            "dataset_id": manifest["dataset_id"],
            "first_trading_date": manifest["first_trading_date"],
            "last_trading_date": manifest["last_trading_date"],
            "row_count": manifest["row_count"],
        }
    else:
        blocked.append("data-not-downloaded")
    pointer = model_dir / market / symbol / "active-paper.txt"
    model_status: dict[str, object] = {"active": False}
    validation_status: dict[str, object] = {"promoted_for_paper": False}
    if pointer.exists():
        version = pointer.read_text(encoding="utf-8").strip()
        artifact = ModelStore(model_dir).load(market, symbol, version)
        model_status = {
            "active": True,
            "version": artifact.version,
            "feature_schema": artifact.feature_schema,
            "threshold": str(artifact.threshold),
        }
        validation_status = {
            "promoted_for_paper": artifact.promoted_for_paper,
            "fold_metrics": _json_safe(artifact.fold_metrics),
            "aggregate_metrics": _json_safe(artifact.aggregate_metrics),
            "failure_reasons": list(artifact.failure_reasons),
        }
    else:
        blocked.append("model-not-validated")
    state_path = paper_root / market / symbol / "state.json"
    paper = {
        "sessions_observed": 0,
        "required_sessions": 60,
        "complete": False,
    }
    if state_path.exists():
        paper.update(json.loads(state_path.read_text(encoding="utf-8")))
        paper["complete"] = int(paper.get("sessions_observed", 0)) >= 60
    return {
        "mode": "paper-observation",
        "execution_target": execution_target,
        "data": data_status,
        "model": model_status,
        "validation": validation_status,
        "paper": paper,
        "drift": {"status": "insufficient-history"},
        "data_quality": {"status": "blocked" if blocked else "available"},
        "blocked_reasons": blocked,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="market-sentinel")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    subcommands.add_parser("live-preflight")
    subcommands.add_parser("ruflo-run-once")

    download_parser = subcommands.add_parser("download-data")
    _add_lane_arguments(download_parser)
    download_parser.add_argument("--start", required=True)
    download_parser.add_argument("--end", required=True)
    download_parser.add_argument("--data-root", default="data/datasets")

    build_parser = subcommands.add_parser("build-dataset")
    _add_lane_arguments(build_parser)
    build_parser.add_argument("--dataset-id", required=True)
    build_parser.add_argument("--cost-profile", required=True)
    build_parser.add_argument("--corporate-action-record")
    build_parser.add_argument("--data-root", default="data/datasets")

    train_parser = subcommands.add_parser("train-market-model")
    _add_lane_arguments(train_parser)
    train_parser.add_argument("--dataset-id", required=True)
    train_parser.add_argument("--data-root", default="data/datasets")
    train_parser.add_argument("--model-root", default="data/models")
    train_parser.add_argument("--trial-root", default="data/trials")

    validate_parser = subcommands.add_parser("validate-market-model")
    _add_lane_arguments(validate_parser)
    validate_parser.add_argument("--version", required=True)
    validate_parser.add_argument("--model-root", default="data/models")

    promote_parser = subcommands.add_parser("promote-to-paper")
    _add_lane_arguments(promote_parser)
    promote_parser.add_argument("--version", required=True)
    promote_parser.add_argument("--model-root", default="data/models")

    paper_status_parser = subcommands.add_parser("paper-status")
    _add_lane_arguments(paper_status_parser)
    paper_status_parser.add_argument("--paper-root", default="data/paper")

    export_parser = subcommands.add_parser("export-dashboard")
    export_parser.add_argument("--path", default="apps/control-center/public/status.json")
    export_parser.add_argument("--model-dir", default="data/models")
    export_parser.add_argument("--data-root", default="data/datasets")
    export_parser.add_argument("--paper-root", default="data/paper")

    order_parser = subcommands.add_parser("submit-order")
    order_parser.add_argument("--broker", choices=["groww", "alpaca"])
    order_parser.add_argument("--symbol", required=True)
    order_parser.add_argument("--market", choices=["IN", "US"])
    order_parser.add_argument(
        "--instrument-type",
        choices=[item.value for item in InstrumentType],
        default="equity",
    )
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
        _print_json(_status())
        return 0
    if args.command == "live-preflight":
        _print_json(live_preflight_report(load_settings()))
        return 0
    if args.command == "ruflo-run-once":
        _print_json(RUFLOAgent().supervised_run_once(load_settings()))
        return 0
    if args.command == "submit-order":
        return _submit_order(args)
    try:
        result: dict[str, object] | None = None
        if args.command == "download-data":
            result = _download_data(args)
        elif args.command == "build-dataset":
            result = _build_dataset(args)
        elif args.command == "train-market-model":
            result = _train_market_model(args)
        elif args.command == "validate-market-model":
            result = _validate_market_model(args)
        elif args.command == "promote-to-paper":
            result = _promote_to_paper(args)
        elif args.command == "paper-status":
            result = _paper_status(args)
        elif args.command == "export-dashboard":
            _export_dashboard(
                Path(args.path),
                model_dir=Path(args.model_dir),
                data_root=Path(args.data_root),
                paper_root=Path(args.paper_root),
            )
            result = {"status": "exported", "path": args.path}
        if result is None:
            return 2
        _print_json(result)
        return 0
    except (FileNotFoundError, ValueError, RuntimeError, KeyError) as exc:
        _print_json(
            {
                "status": "blocked",
                "error": _sanitized_command_error(exc),
            }
        )
        return 1


def _add_lane_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--market", choices=["US", "IN"], required=True)
    parser.add_argument("--symbol", choices=["SPY", "NIFTYBEES"], required=True)


def _sanitized_command_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "dataset or model artifact was not found"
    settings = load_settings()
    secrets = tuple(
        item
        for item in (
            settings.alpaca_key_id,
            settings.alpaca_secret_key,
            settings.groww_api_key,
            settings.groww_secret_key,
            settings.groww_access_token,
        )
        if item
    )
    return sanitize_provider_error(str(exc), secrets)


def _corporate_action_record(
    path: Path | None,
) -> tuple[str | None, frozenset[date]]:
    if path is None:
        return None, frozenset()
    payload = json.loads(path.read_text(encoding="utf-8"))
    record_id = str(payload["record_id"]).strip()
    source_url = str(payload["source_url"]).strip()
    if not record_id or not source_url.startswith("https://"):
        raise ValueError("corporate-action record requires id and HTTPS source")
    dates = frozenset(
        date.fromisoformat(str(item))
        for item in payload.get("reconciled_exchange_dates", [])
    )
    return record_id, dates


def _load_cost_profile(path: Path) -> CostProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schedules = tuple(
        CostSchedule(
            effective_from=date.fromisoformat(str(item["effective_from"])),
            commission_bps=Decimal(str(item["commission_bps"])),
            regulatory_bps=Decimal(str(item["regulatory_bps"])),
            tax_bps=Decimal(str(item["tax_bps"])),
            spread_bps=Decimal(str(item["spread_bps"])),
            slippage_bps=Decimal(str(item["slippage_bps"])),
            flat_fee=Decimal(str(item["flat_fee"])),
            source_notes=str(item["source_notes"]),
        )
        for item in payload["schedules"]
    )
    return CostProfile(
        market=str(payload["market"]),
        currency=str(payload["currency"]),
        version=str(payload["version"]),
        schedules=schedules,
    )


def _research_path(root: Path, market: str, symbol: str, dataset_id: str) -> Path:
    return root / market / symbol / dataset_id / "research.json"


def _write_immutable_json(path: Path, payload: dict[str, object]) -> None:
    encoded = json.dumps(
        _json_safe(payload),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise RuntimeError("immutable research dataset differs") from None


def _load_research_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _meta_label_to_payload(item: MetaLabelRow) -> dict[str, object]:
    return _json_safe(asdict(item))


def _meta_label_from_payload(payload: dict[str, Any]) -> MetaLabelRow:
    feature = payload["feature_row"]
    costs = payload["costs"]
    return MetaLabelRow(
        feature_row=FeatureRow(
            symbol=str(feature["symbol"]),
            market=str(feature["market"]),
            currency=str(feature["currency"]),
            feature_as_of=date.fromisoformat(str(feature["feature_as_of"])),
            entry_eligible_at=date.fromisoformat(str(feature["entry_eligible_at"])),
            feature_schema=str(feature["feature_schema"]),
            last_close=Decimal(str(feature["last_close"])),
            current_volume=Decimal(str(feature["current_volume"])),
            average_volume_20=Decimal(str(feature["average_volume_20"])),
            values={
                str(name): Decimal(str(value))
                for name, value in feature["values"].items()
            },
        ),
        label=int(payload["label"]),
        entry_date=date.fromisoformat(str(payload["entry_date"])),
        entry_price_before_costs=Decimal(str(payload["entry_price_before_costs"])),
        exit_date=date.fromisoformat(str(payload["exit_date"])),
        exit_price_before_costs=Decimal(str(payload["exit_price_before_costs"])),
        label_end_at=date.fromisoformat(str(payload["label_end_at"])),
        holding_sessions=int(payload["holding_sessions"]),
        exit_reason=str(payload["exit_reason"]),
        gross_pnl=Decimal(str(payload["gross_pnl"])),
        costs=CostBreakdown(
            commission=Decimal(str(costs["commission"])),
            regulatory=Decimal(str(costs["regulatory"])),
            tax=Decimal(str(costs["tax"])),
            spread=Decimal(str(costs["spread"])),
            slippage=Decimal(str(costs["slippage"])),
            flat=Decimal(str(costs["flat"])),
        ),
        total_cost=Decimal(str(payload["total_cost"])),
        net_pnl=Decimal(str(payload["net_pnl"])),
        cost_profile_version=str(payload["cost_profile_version"]),
    )


def _fold_metadata(
    version: str,
    fold_id: str,
    manifest: Any,
    research: dict[str, Any],
    fit_rows: tuple[MetaLabelRow, ...],
    calibration_rows: tuple[MetaLabelRow, ...],
    timestamp: datetime,
) -> dict[str, object]:
    return {
        "version": f"{version}-{fold_id}",
        "market": manifest.market,
        "symbol": manifest.symbol,
        "currency": manifest.currency,
        "dataset_id": manifest.dataset_id,
        "dataset_checksum": manifest.dataset_id,
        "label_version": str(research["label_version"]),
        "cost_profile_version": str(research["cost_profile_version"]),
        "fit_range": (
            fit_rows[0].feature_row.feature_as_of.isoformat(),
            fit_rows[-1].feature_row.feature_as_of.isoformat(),
        ),
        "calibration_range": (
            calibration_rows[0].feature_row.feature_as_of.isoformat(),
            calibration_rows[-1].feature_row.feature_as_of.isoformat(),
        ),
        "test_ranges": (),
        "fold_metrics": (),
        "aggregate_metrics": {},
        "created_at": timestamp.isoformat(),
        "code_commit": _code_commit(),
    }


def _fold_to_payload(fold: Any) -> dict[str, object]:
    return {
        "fold_id": fold.fold_id,
        "fit_indices": list(fold.fit_indices),
        "calibration_indices": list(fold.calibration_indices),
        "test_indices": list(fold.test_indices),
    }


def _code_commit() -> str:
    return os.environ.get("GIT_COMMIT", "local-uncommitted")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(_json_safe(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
