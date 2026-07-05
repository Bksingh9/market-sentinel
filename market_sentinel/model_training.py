from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class TrainingExample:
    features: dict[str, Decimal]
    label: int


@dataclass(frozen=True)
class LinearModel:
    version: str
    feature_names: tuple[str, ...]
    weights: dict[str, Decimal]
    bias: Decimal
    training_rows: int
    accuracy: Decimal
    created_at: str

    def predict_score(self, features: dict[str, Decimal]) -> Decimal:
        linear = self.bias
        for name in self.feature_names:
            linear += self.weights.get(name, Decimal("0")) * features.get(name, Decimal("0"))
        score = Decimal("0.5") + linear
        bounded = max(Decimal("0"), min(Decimal("1"), score))
        return bounded.quantize(Decimal("0.0001"))

    def to_payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "feature_names": list(self.feature_names),
            "weights": {name: str(value) for name, value in self.weights.items()},
            "bias": str(self.bias),
            "training_rows": self.training_rows,
            "accuracy": str(self.accuracy),
            "created_at": self.created_at,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "LinearModel":
        weights_payload = payload["weights"]
        if not isinstance(weights_payload, dict):
            raise ValueError("weights payload must be an object")
        return cls(
            version=str(payload["version"]),
            feature_names=tuple(str(item) for item in payload["feature_names"]),
            weights={str(name): Decimal(str(value)) for name, value in weights_payload.items()},
            bias=Decimal(str(payload["bias"])),
            training_rows=int(payload["training_rows"]),
            accuracy=Decimal(str(payload["accuracy"])),
            created_at=str(payload["created_at"]),
        )


def _linear_score(
    weights: dict[str, Decimal],
    bias: Decimal,
    feature_names: tuple[str, ...],
    features: dict[str, Decimal],
) -> Decimal:
    score = bias
    for name in feature_names:
        score += weights[name] * features.get(name, Decimal("0"))
    return score


def train_linear_model(
    examples: list[TrainingExample],
    *,
    epochs: int = 10,
    learning_rate: Decimal = Decimal("0.1"),
) -> LinearModel:
    if not examples:
        raise ValueError("at least one training example is required")
    feature_names = tuple(sorted({name for example in examples for name in example.features}))
    weights = {name: Decimal("0") for name in feature_names}
    bias = Decimal("0")

    for _ in range(epochs):
        for example in examples:
            predicted = 1 if _linear_score(weights, bias, feature_names, example.features) >= 0 else 0
            error = Decimal(example.label - predicted)
            bias += learning_rate * error
            for name in feature_names:
                weights[name] += learning_rate * error * example.features.get(name, Decimal("0"))

    correct = 0
    for example in examples:
        predicted_score = Decimal("0.5") + _linear_score(weights, bias, feature_names, example.features)
        predicted = 1 if predicted_score >= Decimal("0.5") else 0
        if predicted == example.label:
            correct += 1
    accuracy = (Decimal(correct) / Decimal(len(examples))).quantize(Decimal("0.0001"))
    created = datetime.now(timezone.utc)
    return LinearModel(
        version=f"model-{created.strftime('%Y%m%d%H%M%S%f')}",
        feature_names=feature_names,
        weights=weights,
        bias=bias,
        training_rows=len(examples),
        accuracy=accuracy,
        created_at=created.isoformat(),
    )
