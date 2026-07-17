import json
import unittest
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from market_sentinel.ml_features import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, FeatureRow
from market_sentinel.model_training import (
    MarketModelArtifact,
    fit_fold_model,
    predict_probability,
)


@dataclass(frozen=True)
class StubRow:
    feature_row: FeatureRow
    label: int


class MarketModelTrainingTest(unittest.TestCase):
    def test_scaler_uses_fit_rows_only(self):
        fit_rows, calibration_rows = self.rows(
            fit_value=1,
            calibration_value=1000,
        )
        artifact = fit_fold_model(
            fit_rows,
            calibration_rows,
            c_value=Decimal("1.0"),
            threshold=Decimal("0.60"),
            metadata=self.metadata(),
        )
        self.assertTrue(
            all(abs(value - 1.0) < 0.01 for value in artifact.scaler_mean)
        )

    def test_probability_and_threshold_round_trip_through_plain_json(self):
        fit_rows, calibration_rows = self.rows(
            fit_value=1,
            calibration_value=2,
        )
        artifact = fit_fold_model(
            fit_rows,
            calibration_rows,
            c_value=Decimal("0.1"),
            threshold=Decimal("0.65"),
            metadata=self.metadata(),
        )
        loaded = MarketModelArtifact.from_payload(
            json.loads(json.dumps(artifact.to_payload()))
        )
        probability = predict_probability(
            loaded,
            calibration_rows[0].feature_row,
        )
        self.assertGreaterEqual(probability, Decimal("0"))
        self.assertLessEqual(probability, Decimal("1"))
        self.assertEqual(loaded.threshold, Decimal("0.65"))

    def test_unknown_hyperparameter_or_threshold_is_rejected(self):
        fit_rows, calibration_rows = self.rows(
            fit_value=1,
            calibration_value=2,
        )
        with self.assertRaises(ValueError):
            fit_fold_model(
                fit_rows,
                calibration_rows,
                c_value=Decimal("2.0"),
                threshold=Decimal("0.50"),
                metadata=self.metadata(),
            )

    def test_behavior_checksum_detects_parameter_tampering(self):
        fit_rows, calibration_rows = self.rows(
            fit_value=1,
            calibration_value=2,
        )
        artifact = fit_fold_model(
            fit_rows,
            calibration_rows,
            c_value=Decimal("1.0"),
            threshold=Decimal("0.60"),
            metadata=self.metadata(),
        )
        payload = artifact.to_payload()
        payload["intercept"] = float(payload["intercept"]) + 1.0
        with self.assertRaisesRegex(ValueError, "behavior checksum mismatch"):
            MarketModelArtifact.from_payload(payload)

    def rows(
        self,
        *,
        fit_value: int,
        calibration_value: int,
    ) -> tuple[tuple[StubRow, ...], tuple[StubRow, ...]]:
        start = date(2024, 1, 1)

        def make_row(index: int, value: int) -> StubRow:
            feature = FeatureRow(
                symbol="SPY",
                market="US",
                currency="USD",
                feature_as_of=start + timedelta(days=index),
                entry_eligible_at=start + timedelta(days=index + 1),
                feature_schema=FEATURE_SCHEMA_VERSION,
                last_close=Decimal("100"),
                current_volume=Decimal("1000"),
                average_volume_20=Decimal("1000"),
                values={name: Decimal(value) for name in FEATURE_ORDER},
            )
            return StubRow(feature, index % 2)

        fit_rows = tuple(make_row(index, fit_value) for index in range(40))
        calibration_rows = tuple(
            make_row(index + 100, calibration_value) for index in range(40)
        )
        return fit_rows, calibration_rows

    @staticmethod
    def metadata() -> dict[str, object]:
        return {
            "version": "spy-fold-1",
            "market": "US",
            "symbol": "SPY",
            "currency": "USD",
            "dataset_id": "d" * 64,
            "dataset_checksum": "d" * 64,
            "label_version": "protected-2-3-10-v1",
            "cost_profile_version": "us-cost-v1",
            "fit_range": ("2024-01-01", "2024-02-09"),
            "calibration_range": ("2024-04-10", "2024-05-19"),
            "test_ranges": (("2024-06-01", "2024-07-01"),),
            "fold_metrics": (),
            "aggregate_metrics": {},
            "created_at": "2026-07-17T00:00:00+00:00",
            "code_commit": "test-commit",
        }


if __name__ == "__main__":
    unittest.main()
