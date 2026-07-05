from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Prediction:
    score: Decimal
    passed: bool
    model_version: str = "baseline-rule"


class MLPredictionAgent:
    def __init__(self, min_score: Decimal = Decimal("0.55")):
        self.min_score = min_score

    def score(self, features: dict[str, Decimal]) -> Prediction:
        momentum = features.get("momentum", Decimal("0"))
        raw_score = Decimal("0.50") + (momentum * Decimal("2"))
        bounded = max(Decimal("0"), min(Decimal("1"), raw_score))
        return Prediction(score=bounded, passed=bounded >= self.min_score)
