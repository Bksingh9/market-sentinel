import inspect
import unittest
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from market_sentinel.ml_evaluation import (
    FoldMetrics,
    ReplayMetrics,
    evaluate_validation,
    select_calibration_configuration,
)


@dataclass(frozen=True)
class StubFeature:
    feature_as_of: date


@dataclass(frozen=True)
class StubRow:
    feature_row: StubFeature
    label_end_at: date
    label: int
    gross_pnl: Decimal
    total_cost: Decimal
    net_pnl: Decimal


class MLEvaluationTest(unittest.TestCase):
    def test_configuration_selection_has_no_test_fold_input(self):
        rows = self.calibration_rows()
        probabilities = self.calibration_probabilities_by_c(rows)
        selected = select_calibration_configuration(rows, probabilities)
        self.assertIn(
            selected.c_value,
            {Decimal("0.1"), Decimal("1.0"), Decimal("10.0")},
        )
        self.assertIn(
            selected.threshold,
            {Decimal("0.55"), Decimal("0.60"), Decimal("0.65")},
        )
        self.assertNotIn(
            "test",
            inspect.signature(select_calibration_configuration).parameters,
        )

    def test_failed_mandatory_fold_cannot_be_averaged_away(self):
        folds = self.passing_folds()
        folds[1] = self.with_filtered_expectancy(
            folds[1],
            Decimal("-0.01"),
        )
        report = evaluate_validation(folds, attempted_configurations=3)
        self.assertFalse(report.promoted_for_paper)
        self.assertIn(
            "fold-2 filtered expectancy is not positive",
            report.failure_reasons,
        )

    def test_all_promotion_gates_are_independent(self):
        report = evaluate_validation(
            self.passing_folds(),
            attempted_configurations=3,
        )
        self.assertTrue(report.promoted_for_paper)
        self.assertEqual(report.attempted_configurations, 3)
        self.assertGreaterEqual(report.acceptance_coverage, Decimal("0.10"))
        self.assertLessEqual(report.acceptance_coverage, Decimal("0.80"))

    def calibration_rows(self) -> tuple[StubRow, ...]:
        start = date(2024, 1, 1)
        return tuple(
            StubRow(
                feature_row=StubFeature(start + timedelta(days=index * 2)),
                label_end_at=start + timedelta(days=(index * 2) + 1),
                label=index % 2,
                gross_pnl=Decimal("0.03") if index % 2 else Decimal("-0.02"),
                total_cost=Decimal("0.001"),
                net_pnl=Decimal("0.029") if index % 2 else Decimal("-0.021"),
            )
            for index in range(60)
        )

    @staticmethod
    def calibration_probabilities_by_c(
        rows: tuple[StubRow, ...],
    ) -> dict[Decimal, tuple[Decimal, ...]]:
        probabilities = tuple(
            Decimal("0.70") if row.label else Decimal("0.40") for row in rows
        )
        return {
            Decimal("0.1"): probabilities,
            Decimal("1.0"): probabilities,
            Decimal("10.0"): probabilities,
        }

    @staticmethod
    def passing_folds() -> list[FoldMetrics]:
        filtered = ReplayMetrics(
            completed_trades=20,
            gross_return=Decimal("0.6"),
            net_return=Decimal("0.4"),
            total_costs=Decimal("0.2"),
            win_rate=Decimal("0.60"),
            expectancy=Decimal("0.02"),
            maximum_drawdown=Decimal("0.10"),
        )
        baseline = ReplayMetrics(
            completed_trades=40,
            gross_return=Decimal("0.6"),
            net_return=Decimal("0.4"),
            total_costs=Decimal("0.2"),
            win_rate=Decimal("0.55"),
            expectancy=Decimal("0.01"),
            maximum_drawdown=Decimal("0.20"),
        )
        return [
            FoldMetrics(
                fold_id=f"fold-{index}",
                candidate_count=60,
                positive_count=30,
                negative_count=30,
                accuracy=Decimal("0.65"),
                precision=Decimal("0.65"),
                recall=Decimal("0.65"),
                brier_score=Decimal("0.20"),
                training_prevalence=Decimal("0.50"),
                prevalence_brier_score=Decimal("0.25"),
                acceptance_coverage=Decimal("0.50"),
                rejected_candidates=30,
                calibration_buckets=(),
                filtered=filtered,
                baseline=baseline,
            )
            for index in range(1, 4)
        ]

    @staticmethod
    def with_filtered_expectancy(
        fold: FoldMetrics,
        expectancy: Decimal,
    ) -> FoldMetrics:
        return replace(
            fold,
            filtered=replace(fold.filtered, expectancy=expectancy),
        )


if __name__ == "__main__":
    unittest.main()
