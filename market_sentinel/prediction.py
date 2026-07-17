from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import math

from market_sentinel.ml_features import FeatureRow
from market_sentinel.model_training import MarketModelArtifact, predict_probability


@dataclass(frozen=True)
class Prediction:
    score: Decimal
    passed: bool
    model_version: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class DriftState:
    scored_candidates: int
    feature_psi: dict[str, Decimal]
    status: str


class MarketMLPredictionAgent:
    def __init__(self, artifact: MarketModelArtifact):
        self.artifact = artifact

    def score(
        self,
        row: FeatureRow,
        *,
        history: tuple[FeatureRow, ...],
        expected_feature_as_of: date,
    ) -> Prediction:
        try:
            if not self.artifact.promoted_for_paper:
                return self._blocked("model is not promoted for paper")
            if row.feature_as_of != expected_feature_as_of:
                return self._blocked("stale or unexpected feature date")
            if (row.market, row.symbol, row.currency, row.feature_schema) != (
                self.artifact.market,
                self.artifact.symbol,
                self.artifact.currency,
                self.artifact.feature_schema,
            ):
                return self._blocked("feature row is incompatible with model")
            for index, name in enumerate(self.artifact.feature_order):
                value = float(row.values[name])
                mean = self.artifact.scaler_mean[index]
                scale = self.artifact.scaler_scale[index]
                if not math.isfinite(value):
                    return self._blocked(f"non-finite feature: {name}")
                if scale > 0 and abs(value - mean) > (8.0 * scale):
                    return self._blocked(f"hard outlier: {name}")
            drift = population_drift(self.artifact, history)
            if drift.status == "blocked":
                return self._blocked("material population drift")
            probability = predict_probability(self.artifact, row)
            if probability < 0 or probability > 1:
                return self._blocked("probability outside [0, 1]")
            passed = probability >= self.artifact.threshold
            return Prediction(
                probability,
                passed,
                self.artifact.version,
                () if passed else ("below frozen threshold",),
            )
        except (KeyError, ValueError, ArithmeticError, OverflowError) as exc:
            return self._blocked(
                f"model inference blocked: {type(exc).__name__}"
            )

    def _blocked(self, reason: str) -> Prediction:
        return Prediction(
            Decimal("0"),
            False,
            self.artifact.version,
            (reason,),
        )


def population_drift(
    artifact: MarketModelArtifact,
    history: tuple[FeatureRow, ...],
) -> DriftState:
    if len(history) < 60:
        return DriftState(len(history), {}, "insufficient-history")
    epsilon = 1e-6
    expected = 0.1
    feature_psi: dict[str, Decimal] = {}
    for name in artifact.feature_order:
        boundaries = artifact.fit_feature_deciles[name]
        if len(boundaries) != 11:
            raise ValueError("model feature deciles must have eleven boundaries")
        counts = [0] * 10
        for row in history:
            value = float(row.values[name])
            if not math.isfinite(value):
                raise ValueError("drift history contains non-finite feature")
            bucket = bisect_right(boundaries[1:-1], value)
            counts[min(9, max(0, bucket))] += 1
        psi = 0.0
        for count in counts:
            actual = count / len(history)
            psi += (actual - expected) * math.log(
                (actual + epsilon) / (expected + epsilon)
            )
        feature_psi[name] = Decimal(str(psi))
    status = (
        "blocked"
        if any(value > Decimal("0.25") for value in feature_psi.values())
        else "ok"
    )
    return DriftState(len(history), feature_psi, status)
