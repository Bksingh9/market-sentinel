import inspect
import tempfile
import unittest
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from market_sentinel.ml_features import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, FeatureRow
from market_sentinel.model_store import ModelStore
from market_sentinel.model_training import MarketModelArtifact, fit_fold_model
from market_sentinel.prediction import MarketMLPredictionAgent


@dataclass(frozen=True)
class StubRow:
    feature_row: FeatureRow
    label: int


class MLRuntimeTest(unittest.TestCase):
    def test_active_pointers_are_market_and_symbol_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            store.save(self.artifact("US", "SPY", "spy-v1"))
            store.save(self.artifact("IN", "NIFTYBEES", "nifty-v1"))
            store.activate_for_paper("US", "SPY", "spy-v1")
            store.activate_for_paper("IN", "NIFTYBEES", "nifty-v1")
            spy = store.load_active(
                "US",
                "SPY",
                expected_schema="daily-meta-v1",
                expected_dataset_checksum="a" * 64,
            )
            nifty = store.load_active(
                "IN",
                "NIFTYBEES",
                expected_schema="daily-meta-v1",
                expected_dataset_checksum="b" * 64,
            )
            self.assertEqual(spy.version, "spy-v1")
            self.assertEqual(nifty.version, "nifty-v1")

    def test_eight_sigma_outlier_and_psi_above_point_two_five_block(self):
        agent = MarketMLPredictionAgent(self.artifact("US", "SPY", "spy-v1"))
        outlier = self.row(value=Decimal("9"))
        self.assertFalse(
            agent.score(
                outlier,
                history=(),
                expected_feature_as_of=outlier.feature_as_of,
            ).passed
        )
        shifted_history = tuple(self.row(value=Decimal("3")) for _ in range(60))
        current = self.row(value=Decimal("3"))
        prediction = agent.score(
            current,
            history=shifted_history,
            expected_feature_as_of=current.feature_as_of,
        )
        self.assertFalse(prediction.passed)
        self.assertIn("material population drift", prediction.reasons)

    def test_stale_feature_date_blocks_candidate(self):
        agent = MarketMLPredictionAgent(self.artifact("US", "SPY", "spy-v1"))
        row = self.row(value=Decimal("0"))
        prediction = agent.score(
            row,
            history=(),
            expected_feature_as_of=row.feature_as_of + timedelta(days=1),
        )
        self.assertEqual(
            prediction.reasons,
            ("stale or unexpected feature date",),
        )

    def test_prediction_module_has_no_broker_or_execution_authority(self):
        source = inspect.getsource(
            __import__("market_sentinel.prediction", fromlist=["*"])
        )
        self.assertNotIn("market_sentinel.brokers", source)
        self.assertNotIn("ExecutionAgent", source)
        self.assertNotIn("place_order", source)

    def artifact(
        self,
        market: str,
        symbol: str,
        version: str,
    ) -> MarketModelArtifact:
        fit_rows = tuple(self.stub_row(index, calibrating=False) for index in range(40))
        calibration_rows = tuple(
            self.stub_row(index + 100, calibrating=True) for index in range(40)
        )
        artifact = fit_fold_model(
            fit_rows,
            calibration_rows,
            c_value=Decimal("1.0"),
            threshold=Decimal("0.60"),
            metadata={
                "version": version,
                "market": "US",
                "symbol": "SPY",
                "currency": "USD",
                "dataset_id": ("a" if market == "US" else "b") * 64,
                "dataset_checksum": ("a" if market == "US" else "b") * 64,
                "label_version": "protected-2-3-10-v1",
                "cost_profile_version": "cost-v1",
                "fit_range": ("2024-01-01", "2024-02-09"),
                "calibration_range": ("2024-04-10", "2024-05-19"),
                "test_ranges": (),
                "fold_metrics": (),
                "aggregate_metrics": {},
                "created_at": "2026-07-17T00:00:00+00:00",
                "code_commit": "test-commit",
            },
        )
        return replace(
            artifact,
            market=market,
            symbol=symbol,
            currency="USD" if market == "US" else "INR",
            promoted_for_paper=True,
        )

    def stub_row(self, index: int, *, calibrating: bool) -> StubRow:
        label = index % 2
        value = Decimal("1") if label else Decimal("-1")
        if calibrating:
            value += Decimal("0.1")
        return StubRow(self.row(value=value, offset=index), label)

    @staticmethod
    def row(value: Decimal, offset: int = 0) -> FeatureRow:
        start = date(2024, 1, 1) + timedelta(days=offset)
        return FeatureRow(
            symbol="SPY",
            market="US",
            currency="USD",
            feature_as_of=start,
            entry_eligible_at=start + timedelta(days=1),
            feature_schema=FEATURE_SCHEMA_VERSION,
            last_close=Decimal("100"),
            current_volume=Decimal("1000"),
            average_volume_20=Decimal("1000"),
            values={name: value for name in FEATURE_ORDER},
        )


if __name__ == "__main__":
    unittest.main()
