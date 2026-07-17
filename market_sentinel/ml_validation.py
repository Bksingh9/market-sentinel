from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import math

from market_sentinel.ml_labels import MetaLabelRow


@dataclass(frozen=True)
class WalkForwardConfig:
    test_folds: int = 3
    gap_sessions: int = 10
    calibration_fraction: Decimal = Decimal("0.20")
    min_calibration_rows: int = 40
    min_test_rows: int = 30
    min_total_oos: int = 150
    min_positive: int = 30
    min_negative: int = 30


@dataclass(frozen=True)
class FoldDefinition:
    fold_id: str
    fit_indices: tuple[int, ...]
    calibration_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


def _both_classes(
    rows: tuple[MetaLabelRow, ...],
    indices: tuple[int, ...],
) -> bool:
    return {rows[index].label for index in indices} == {0, 1}


def build_walk_forward_folds(
    rows: tuple[MetaLabelRow, ...],
    sessions: tuple[date, ...],
    config: WalkForwardConfig,
) -> tuple[FoldDefinition, ...]:
    if config.test_folds < 3:
        raise ValueError("at least three test folds are required")
    if tuple(sorted(rows, key=lambda item: item.feature_row.feature_as_of)) != rows:
        raise ValueError("walk-forward rows must be chronological")
    if tuple(sorted(set(sessions))) != sessions:
        raise ValueError("exchange sessions must be unique and chronological")
    positions = {session: index for index, session in enumerate(sessions)}
    if any(item.feature_row.feature_as_of not in positions for item in rows):
        raise ValueError("every candidate date must be an exchange session")

    test_size = max(
        config.min_test_rows,
        len(rows) // (config.test_folds + 3),
    )
    first_test = len(rows) - (test_size * config.test_folds)
    if first_test <= 0:
        raise ValueError("insufficient history before walk-forward test folds")
    folds: list[FoldDefinition] = []
    for fold_number in range(config.test_folds):
        test_start = first_test + (fold_number * test_size)
        test_stop = (
            len(rows)
            if fold_number == config.test_folds - 1
            else test_start + test_size
        )
        test_start_date = rows[test_start].feature_row.feature_as_of
        calibration_latest_position = (
            positions[test_start_date] - config.gap_sessions - 1
        )
        if calibration_latest_position < 0:
            raise ValueError(
                f"fold-{fold_number + 1} has no calibration history before its gap"
            )
        calibration_latest_date = sessions[calibration_latest_position]
        pretest_indices = tuple(
            index
            for index in range(test_start)
            if rows[index].feature_row.feature_as_of <= calibration_latest_date
        )
        calibration_size = max(
            config.min_calibration_rows,
            math.ceil(
                len(pretest_indices) * float(config.calibration_fraction)
            ),
        )
        calibration_indices = pretest_indices[-calibration_size:]
        if not calibration_indices:
            raise ValueError(
                f"fold-{fold_number + 1} has no calibration rows"
            )
        calibration_start_date = rows[
            calibration_indices[0]
        ].feature_row.feature_as_of
        fit_latest_position = (
            positions[calibration_start_date] - config.gap_sessions - 1
        )
        if fit_latest_position < 0:
            raise ValueError(
                f"fold-{fold_number + 1} has no fit history before its gap"
            )
        fit_latest_date = sessions[fit_latest_position]
        fit_indices = tuple(
            index
            for index in range(calibration_indices[0])
            if rows[index].feature_row.feature_as_of <= fit_latest_date
            and rows[index].label_end_at < calibration_start_date
        )
        calibration_indices = tuple(
            index
            for index in calibration_indices
            if rows[index].label_end_at < test_start_date
        )
        test_indices = tuple(range(test_start, test_stop))
        if (
            not fit_indices
            or len(calibration_indices) < config.min_calibration_rows
            or len(test_indices) < config.min_test_rows
        ):
            raise ValueError(
                f"fold-{fold_number + 1} does not meet row minimums"
            )
        if (
            not _both_classes(rows, fit_indices)
            or not _both_classes(rows, calibration_indices)
            or not _both_classes(rows, test_indices)
        ):
            raise ValueError(
                f"fold-{fold_number + 1} must contain both classes in every slice"
            )
        folds.append(
            FoldDefinition(
                f"fold-{fold_number + 1}",
                fit_indices,
                calibration_indices,
                test_indices,
            )
        )
    return tuple(folds)


def assert_oos_eligibility(
    rows: tuple[MetaLabelRow, ...],
    folds: tuple[FoldDefinition, ...],
    config: WalkForwardConfig,
) -> None:
    indices = [index for fold in folds for index in fold.test_indices]
    if len(indices) != len(set(indices)):
        raise ValueError("test candidates must be predicted exactly once")
    labels = [rows[index].label for index in indices]
    if (
        len(labels) < config.min_total_oos
        or labels.count(1) < config.min_positive
        or labels.count(0) < config.min_negative
    ):
        raise ValueError("out-of-sample row or class minimum not met")
