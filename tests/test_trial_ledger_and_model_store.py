import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from market_sentinel.trial_ledger import TrialLedger, TrialRecord


class TrialLedgerTest(unittest.TestCase):
    def test_trial_ids_are_immutable_and_failed_trials_remain_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = TrialLedger(Path(directory) / "trials.jsonl")
            ledger.append(self.record("trial-1", promoted=False))
            with self.assertRaisesRegex(ValueError, "trial id already exists"):
                ledger.append(self.record("trial-1", promoted=True))
            self.assertEqual(
                [item.trial_id for item in ledger.read_all()],
                ["trial-1"],
            )
            self.assertFalse(ledger.read_all()[0].promoted_for_paper)

    @staticmethod
    def record(trial_id: str, *, promoted: bool) -> TrialRecord:
        return TrialRecord(
            trial_id=trial_id,
            stage="walk-forward-validation",
            market="US",
            symbol="SPY",
            dataset_id="d" * 64,
            dataset_checksum="d" * 64,
            dataset_range=("2024-01-01", "2026-01-01"),
            feature_schema="daily-meta-v1",
            label_version="protected-2-3-10-v1",
            cost_profile_version="us-cost-v1",
            fold_definitions=(),
            c_value=Decimal("1.0"),
            threshold_candidates=(Decimal("0.55"), Decimal("0.60")),
            selected_threshold=Decimal("0.60"),
            fold_metrics=(),
            aggregate_metrics={},
            promoted_for_paper=promoted,
            failure_reasons=() if promoted else ("expectancy gate failed",),
            code_commit="test-commit",
            created_at="2026-07-17T00:00:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
