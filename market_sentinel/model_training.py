from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from typing import Any

import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from market_sentinel.ml_features import FEATURE_ORDER, FeatureRow
from market_sentinel.ml_labels import MetaLabelRow


ALLOWED_C_VALUES = frozenset(
    {Decimal("0.1"), Decimal("1.0"), Decimal("10.0")}
)
ALLOWED_THRESHOLDS = frozenset(
    {Decimal("0.55"), Decimal("0.60"), Decimal("0.65")}
)
MODEL_TYPE = "sklearn-logistic-meta-v1"


@dataclass(frozen=True)
class MarketModelArtifact:
    version: str
    market: str
    symbol: str
    currency: str
    model_type: str
    sklearn_version: str
    feature_schema: str
    feature_order: tuple[str, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    fit_feature_deciles: dict[str, tuple[float, ...]]
    coefficients: tuple[float, ...]
    intercept: float
    calibrator_coefficient: float
    calibrator_intercept: float
    threshold: Decimal
    c_value: Decimal
    dataset_id: str
    dataset_checksum: str
    label_version: str
    cost_profile_version: str
    fit_range: tuple[str, str]
    calibration_range: tuple[str, str]
    test_ranges: tuple[tuple[str, str], ...]
    fold_metrics: tuple[dict[str, object], ...]
    aggregate_metrics: dict[str, object]
    promoted_for_paper: bool
    failure_reasons: tuple[str, ...]
    behavior_checksum: str
    created_at: str
    code_commit: str
    parent_champion_version: str | None

    def to_payload(self) -> dict[str, object]:
        return _json_safe(asdict(self))

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "MarketModelArtifact":
        required = {item.name for item in fields(cls)}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(
                "model artifact is missing fields: " + ", ".join(missing)
            )
        artifact = cls(
            version=str(payload["version"]),
            market=str(payload["market"]),
            symbol=str(payload["symbol"]),
            currency=str(payload["currency"]),
            model_type=str(payload["model_type"]),
            sklearn_version=str(payload["sklearn_version"]),
            feature_schema=str(payload["feature_schema"]),
            feature_order=tuple(str(item) for item in payload["feature_order"]),
            scaler_mean=tuple(float(item) for item in payload["scaler_mean"]),
            scaler_scale=tuple(float(item) for item in payload["scaler_scale"]),
            fit_feature_deciles={
                str(name): tuple(float(item) for item in values)
                for name, values in dict(payload["fit_feature_deciles"]).items()
            },
            coefficients=tuple(float(item) for item in payload["coefficients"]),
            intercept=float(payload["intercept"]),
            calibrator_coefficient=float(payload["calibrator_coefficient"]),
            calibrator_intercept=float(payload["calibrator_intercept"]),
            threshold=Decimal(str(payload["threshold"])),
            c_value=Decimal(str(payload["c_value"])),
            dataset_id=str(payload["dataset_id"]),
            dataset_checksum=str(payload["dataset_checksum"]),
            label_version=str(payload["label_version"]),
            cost_profile_version=str(payload["cost_profile_version"]),
            fit_range=tuple(str(item) for item in payload["fit_range"]),
            calibration_range=tuple(
                str(item) for item in payload["calibration_range"]
            ),
            test_ranges=tuple(
                tuple(str(item) for item in pair)
                for pair in payload["test_ranges"]
            ),
            fold_metrics=tuple(
                dict(item) for item in payload["fold_metrics"]
            ),
            aggregate_metrics=dict(payload["aggregate_metrics"]),
            promoted_for_paper=_require_bool(
                payload["promoted_for_paper"],
                "promoted_for_paper",
            ),
            failure_reasons=tuple(
                str(item) for item in payload["failure_reasons"]
            ),
            behavior_checksum=str(payload["behavior_checksum"]),
            created_at=str(payload["created_at"]),
            code_commit=str(payload["code_commit"]),
            parent_champion_version=None
            if payload["parent_champion_version"] is None
            else str(payload["parent_champion_version"]),
        )
        _validate_artifact(artifact)
        if _compute_behavior_checksum(artifact) != artifact.behavior_checksum:
            raise ValueError("model behavior checksum mismatch")
        return artifact


def fit_fold_model(
    fit_rows: tuple[MetaLabelRow, ...],
    calibration_rows: tuple[MetaLabelRow, ...],
    *,
    c_value: Decimal,
    threshold: Decimal,
    metadata: dict[str, object],
) -> MarketModelArtifact:
    if c_value not in ALLOWED_C_VALUES or threshold not in ALLOWED_THRESHOLDS:
        raise ValueError("unsupported C value or decision threshold")
    if not fit_rows or not calibration_rows:
        raise ValueError("fit and calibration rows are required")
    if {item.label for item in fit_rows} != {0, 1}:
        raise ValueError("fit rows must contain both classes")
    if {item.label for item in calibration_rows} != {0, 1}:
        raise ValueError("calibration rows must contain both classes")

    fit_matrix = _feature_matrix(fit_rows)
    fit_labels = np.asarray([item.label for item in fit_rows], dtype=int)
    calibration_matrix = _feature_matrix(calibration_rows)
    calibration_labels = np.asarray(
        [item.label for item in calibration_rows],
        dtype=int,
    )

    scaler = StandardScaler()
    scaled_fit = scaler.fit_transform(fit_matrix)
    estimator = LogisticRegression(
        C=float(c_value),
        solver="lbfgs",
        random_state=17,
        max_iter=1000,
    )
    estimator.fit(scaled_fit, fit_labels)

    scaled_calibration = scaler.transform(calibration_matrix)
    calibration_scores = estimator.decision_function(
        scaled_calibration
    ).reshape(-1, 1)
    calibrator = LogisticRegression(
        C=1_000_000.0,
        solver="lbfgs",
        random_state=17,
        max_iter=1000,
    )
    calibrator.fit(calibration_scores, calibration_labels)

    decile_points = np.linspace(0.0, 1.0, 11)
    deciles = {
        name: tuple(
            float(value)
            for value in np.quantile(fit_matrix[:, index], decile_points)
        )
        for index, name in enumerate(FEATURE_ORDER)
    }
    artifact = MarketModelArtifact(
        version=str(_metadata(metadata, "version")),
        market=str(_metadata(metadata, "market")),
        symbol=str(_metadata(metadata, "symbol")),
        currency=str(_metadata(metadata, "currency")),
        model_type=MODEL_TYPE,
        sklearn_version=sklearn.__version__,
        feature_schema=fit_rows[0].feature_row.feature_schema,
        feature_order=FEATURE_ORDER,
        scaler_mean=tuple(float(value) for value in scaler.mean_),
        scaler_scale=tuple(float(value) for value in scaler.scale_),
        fit_feature_deciles=deciles,
        coefficients=tuple(float(value) for value in estimator.coef_[0]),
        intercept=float(estimator.intercept_[0]),
        calibrator_coefficient=float(calibrator.coef_[0][0]),
        calibrator_intercept=float(calibrator.intercept_[0]),
        threshold=threshold,
        c_value=c_value,
        dataset_id=str(_metadata(metadata, "dataset_id")),
        dataset_checksum=str(_metadata(metadata, "dataset_checksum")),
        label_version=str(_metadata(metadata, "label_version")),
        cost_profile_version=str(_metadata(metadata, "cost_profile_version")),
        fit_range=_string_pair(_metadata(metadata, "fit_range"), "fit_range"),
        calibration_range=_string_pair(
            _metadata(metadata, "calibration_range"),
            "calibration_range",
        ),
        test_ranges=tuple(
            _string_pair(item, "test_ranges")
            for item in metadata.get("test_ranges", ())
        ),
        fold_metrics=tuple(
            dict(item) for item in metadata.get("fold_metrics", ())
        ),
        aggregate_metrics=dict(metadata.get("aggregate_metrics", {})),
        promoted_for_paper=bool(metadata.get("promoted_for_paper", False)),
        failure_reasons=tuple(
            str(item) for item in metadata.get("failure_reasons", ())
        ),
        behavior_checksum="",
        created_at=str(
            metadata.get("created_at", datetime.now(timezone.utc).isoformat())
        ),
        code_commit=str(_metadata(metadata, "code_commit")),
        parent_champion_version=None
        if metadata.get("parent_champion_version") is None
        else str(metadata["parent_champion_version"]),
    )
    artifact = replace(
        artifact,
        behavior_checksum=_compute_behavior_checksum(artifact),
    )
    _validate_artifact(artifact)
    return artifact


def predict_probability(
    artifact: MarketModelArtifact,
    row: FeatureRow,
) -> Decimal:
    if (row.market, row.symbol, row.currency, row.feature_schema) != (
        artifact.market,
        artifact.symbol,
        artifact.currency,
        artifact.feature_schema,
    ):
        raise ValueError("feature row is incompatible with model artifact")
    raw_values = [float(row.values[name]) for name in artifact.feature_order]
    scaled = [
        (value - mean) / scale
        for value, mean, scale in zip(
            raw_values,
            artifact.scaler_mean,
            artifact.scaler_scale,
            strict=True,
        )
    ]
    decision = artifact.intercept + sum(
        coefficient * value
        for coefficient, value in zip(
            artifact.coefficients,
            scaled,
            strict=True,
        )
    )
    calibrated_logit = artifact.calibrator_intercept + (
        artifact.calibrator_coefficient * decision
    )
    clipped = max(-709.0, min(709.0, calibrated_logit))
    probability = 1.0 / (1.0 + math.exp(-clipped))
    return Decimal(str(probability))


def _feature_matrix(rows: tuple[MetaLabelRow, ...]) -> np.ndarray:
    return np.asarray(
        [
            [float(item.feature_row.values[name]) for name in FEATURE_ORDER]
            for item in rows
        ],
        dtype=float,
    )


def _metadata(metadata: dict[str, object], name: str) -> object:
    if name not in metadata:
        raise ValueError(f"model metadata is missing {name}")
    return metadata[name]


def _string_pair(value: object, name: str) -> tuple[str, str]:
    pair = tuple(str(item) for item in value)
    if len(pair) != 2:
        raise ValueError(f"{name} entries must contain a start and end")
    return pair


def _behavior_payload(artifact: MarketModelArtifact) -> dict[str, object]:
    return {
        "feature_schema": artifact.feature_schema,
        "feature_order": artifact.feature_order,
        "scaler_mean": artifact.scaler_mean,
        "scaler_scale": artifact.scaler_scale,
        "coefficients": artifact.coefficients,
        "intercept": artifact.intercept,
        "calibrator_coefficient": artifact.calibrator_coefficient,
        "calibrator_intercept": artifact.calibrator_intercept,
        "threshold": str(artifact.threshold),
        "label_version": artifact.label_version,
        "cost_profile_version": artifact.cost_profile_version,
        "protection": {
            "stop_fraction": "0.02",
            "target_fraction": "0.03",
            "maximum_holding_sessions": 10,
        },
    }


def _compute_behavior_checksum(artifact: MarketModelArtifact) -> str:
    encoded = json.dumps(
        _behavior_payload(artifact),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_artifact(artifact: MarketModelArtifact) -> None:
    if artifact.model_type != MODEL_TYPE:
        raise ValueError("unsupported model artifact type")
    if artifact.feature_order != FEATURE_ORDER:
        raise ValueError("unsupported model feature order")
    if artifact.c_value not in ALLOWED_C_VALUES:
        raise ValueError("unsupported model C value")
    if artifact.threshold not in ALLOWED_THRESHOLDS:
        raise ValueError("unsupported model threshold")
    expected_length = len(FEATURE_ORDER)
    if not (
        len(artifact.scaler_mean)
        == len(artifact.scaler_scale)
        == len(artifact.coefficients)
        == expected_length
    ):
        raise ValueError("model parameter lengths do not match feature order")
    numeric_values = (
        *artifact.scaler_mean,
        *artifact.scaler_scale,
        *artifact.coefficients,
        artifact.intercept,
        artifact.calibrator_coefficient,
        artifact.calibrator_intercept,
        *(
            value
            for deciles in artifact.fit_feature_deciles.values()
            for value in deciles
        ),
    )
    if not all(math.isfinite(value) for value in numeric_values):
        raise ValueError("model artifact contains non-finite values")
    if any(value <= 0 for value in artifact.scaler_scale):
        raise ValueError("model scaler values must be positive")
    if set(artifact.fit_feature_deciles) != set(FEATURE_ORDER):
        raise ValueError("model deciles do not match feature order")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value
