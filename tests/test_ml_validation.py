import unittest
from dataclasses import dataclass, replace
from datetime import date, timedelta

from market_sentinel.ml_validation import (
    WalkForwardConfig,
    assert_oos_eligibility,
    build_walk_forward_folds,
)


@dataclass(frozen=True)
class StubFeature:
    feature_as_of: date


@dataclass(frozen=True)
class StubRow:
    feature_row: StubFeature
    label_end_at: date
    label: int


class MLValidationTest(unittest.TestCase):
    def make_rows(
        self,
        count: int,
    ) -> tuple[tuple[StubRow, ...], tuple[date, ...]]:
        sessions = tuple(
            date(2024, 1, 1) + timedelta(days=index)
            for index in range((count * 2) + 20)
        )
        rows = tuple(
            StubRow(
                StubFeature(sessions[index * 2]),
                sessions[(index * 2) + 5],
                index % 2,
            )
            for index in range(count)
        )
        return rows, sessions

    def test_three_expanding_folds_have_two_ten_session_gaps(self):
        rows, sessions = self.make_rows(360)
        positions = {session: index for index, session in enumerate(sessions)}
        folds = build_walk_forward_folds(rows, sessions, WalkForwardConfig())
        self.assertGreaterEqual(len(folds), 3)
        for fold in folds:
            fit_end = rows[max(fold.fit_indices)].feature_row.feature_as_of
            calibration_start = rows[
                min(fold.calibration_indices)
            ].feature_row.feature_as_of
            calibration_end = rows[
                max(fold.calibration_indices)
            ].feature_row.feature_as_of
            test_start = rows[min(fold.test_indices)].feature_row.feature_as_of
            self.assertGreater(positions[calibration_start] - positions[fit_end], 10)
            self.assertGreater(positions[test_start] - positions[calibration_end], 10)
            self.assertGreaterEqual(len(fold.calibration_indices), 40)
            self.assertGreaterEqual(len(fold.test_indices), 30)

    def test_each_candidate_appears_in_only_one_test_fold(self):
        rows, sessions = self.make_rows(360)
        folds = build_walk_forward_folds(rows, sessions, WalkForwardConfig())
        test_indices = [index for fold in folds for index in fold.test_indices]
        self.assertEqual(len(test_indices), len(set(test_indices)))

    def test_label_horizon_may_not_cross_a_slice_boundary(self):
        original, sessions = self.make_rows(360)
        rows = list(original)
        rows[100] = replace(
            rows[100],
            label_end_at=rows[140].feature_row.feature_as_of,
        )
        folds = build_walk_forward_folds(
            tuple(rows),
            sessions,
            WalkForwardConfig(),
        )
        for fold in folds:
            calibration_start = rows[
                min(fold.calibration_indices)
            ].feature_row.feature_as_of
            self.assertTrue(
                all(
                    rows[index].label_end_at < calibration_start
                    for index in fold.fit_indices
                )
            )

    def test_oos_eligibility_enforces_total_and_class_minimums(self):
        rows, sessions = self.make_rows(360)
        folds = build_walk_forward_folds(rows, sessions, WalkForwardConfig())
        assert_oos_eligibility(rows, folds, WalkForwardConfig())
        all_negative = tuple(replace(row, label=0) for row in rows)
        with self.assertRaisesRegex(ValueError, "row or class minimum"):
            assert_oos_eligibility(all_negative, folds, WalkForwardConfig())

    def test_fewer_than_three_folds_is_rejected(self):
        rows, sessions = self.make_rows(360)
        with self.assertRaisesRegex(ValueError, "at least three"):
            build_walk_forward_folds(
                rows,
                sessions,
                WalkForwardConfig(test_folds=2),
            )


if __name__ == "__main__":
    unittest.main()
