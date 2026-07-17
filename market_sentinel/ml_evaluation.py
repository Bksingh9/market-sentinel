from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from market_sentinel.ml_labels import MetaLabelRow


@dataclass(frozen=True)
class CalibrationChoice:
    c_value: Decimal
    threshold: Decimal
    expectancy: Decimal
    maximum_drawdown: Decimal
    brier_score: Decimal
    acceptance_coverage: Decimal


@dataclass(frozen=True)
class ReplayMetrics:
    completed_trades: int
    gross_return: Decimal
    net_return: Decimal
    total_costs: Decimal
    win_rate: Decimal | None
    expectancy: Decimal | None
    maximum_drawdown: Decimal


@dataclass(frozen=True)
class FoldMetrics:
    fold_id: str
    candidate_count: int
    positive_count: int
    negative_count: int
    accuracy: Decimal
    precision: Decimal | None
    recall: Decimal | None
    brier_score: Decimal
    training_prevalence: Decimal
    prevalence_brier_score: Decimal
    acceptance_coverage: Decimal
    rejected_candidates: int
    calibration_buckets: tuple[dict[str, object], ...]
    filtered: ReplayMetrics
    baseline: ReplayMetrics


@dataclass(frozen=True)
class ValidationReport:
    fold_metrics: tuple[FoldMetrics, ...]
    aggregate_metrics: dict[str, object]
    acceptance_coverage: Decimal
    attempted_configurations: int
    promoted_for_paper: bool
    failure_reasons: tuple[str, ...]


def replay_fold(
    rows: tuple[MetaLabelRow, ...],
    accepted: tuple[bool, ...],
) -> ReplayMetrics:
    if len(rows) != len(accepted):
        raise ValueError("replay decision count mismatch")
    if tuple(sorted(rows, key=lambda item: item.feature_row.feature_as_of)) != rows:
        raise ValueError("replay rows must be chronological")

    completed: list[MetaLabelRow] = []
    open_until = None
    for row, is_accepted in zip(rows, accepted, strict=True):
        if not is_accepted:
            continue
        if (
            open_until is not None
            and row.feature_row.feature_as_of <= open_until
        ):
            continue
        completed.append(row)
        open_until = row.label_end_at

    gross = sum((item.gross_pnl for item in completed), Decimal("0"))
    costs = sum((item.total_cost for item in completed), Decimal("0"))
    net = sum((item.net_pnl for item in completed), Decimal("0"))
    equity = Decimal("0")
    peak = Decimal("0")
    maximum_drawdown = Decimal("0")
    for item in completed:
        equity += item.net_pnl
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, peak - equity)
    count = len(completed)
    return ReplayMetrics(
        completed_trades=count,
        gross_return=gross,
        net_return=net,
        total_costs=costs,
        win_rate=None
        if count == 0
        else Decimal(sum(item.net_pnl > 0 for item in completed)) / Decimal(count),
        expectancy=None if count == 0 else net / Decimal(count),
        maximum_drawdown=maximum_drawdown,
    )


def select_calibration_configuration(
    rows: tuple[MetaLabelRow, ...],
    probabilities_by_c: dict[Decimal, tuple[Decimal, ...]],
) -> CalibrationChoice:
    allowed_c = (Decimal("0.1"), Decimal("1.0"), Decimal("10.0"))
    allowed_thresholds = (
        Decimal("0.55"),
        Decimal("0.60"),
        Decimal("0.65"),
    )
    if not rows:
        raise ValueError("calibration rows are required")
    if set(probabilities_by_c) != set(allowed_c):
        raise ValueError("calibration must compare exactly the predeclared C values")
    choices: list[CalibrationChoice] = []
    for c_value in allowed_c:
        probabilities = probabilities_by_c[c_value]
        if len(probabilities) != len(rows):
            raise ValueError("calibration probability count mismatch")
        brier = sum(
            (probability - Decimal(rows[index].label)) ** 2
            for index, probability in enumerate(probabilities)
        ) / Decimal(len(rows))
        for threshold in allowed_thresholds:
            accepted = tuple(
                probability >= threshold for probability in probabilities
            )
            coverage = Decimal(sum(accepted)) / Decimal(len(accepted))
            replay = replay_fold(rows, accepted)
            if (
                Decimal("0.10") <= coverage <= Decimal("0.80")
                and replay.expectancy is not None
            ):
                choices.append(
                    CalibrationChoice(
                        c_value,
                        threshold,
                        replay.expectancy,
                        replay.maximum_drawdown,
                        brier,
                        coverage,
                    )
                )
    if not choices:
        raise ValueError(
            "no calibration configuration meets coverage and "
            "completed-trade requirements"
        )
    return max(
        choices,
        key=lambda item: (
            item.expectancy,
            -item.maximum_drawdown,
            -item.brier_score,
            -item.c_value,
            item.threshold,
        ),
    )


def evaluate_fold(
    fold_id: str,
    rows: tuple[MetaLabelRow, ...],
    probabilities: tuple[Decimal, ...],
    *,
    threshold: Decimal,
    training_prevalence: Decimal,
) -> FoldMetrics:
    if not rows or len(rows) != len(probabilities):
        raise ValueError("fold rows and probabilities must be non-empty and aligned")
    if not Decimal("0") <= training_prevalence <= Decimal("1"):
        raise ValueError("training prevalence must be between zero and one")
    labels = [item.label for item in rows]
    predicted = [int(probability >= Decimal("0.50")) for probability in probabilities]
    accepted = tuple(probability >= threshold for probability in probabilities)
    true_positive = sum(
        prediction == 1 and label == 1
        for prediction, label in zip(predicted, labels, strict=True)
    )
    predicted_positive = sum(predicted)
    positive_count = labels.count(1)
    candidate_count = len(rows)
    brier = sum(
        (probability - Decimal(label)) ** 2
        for probability, label in zip(probabilities, labels, strict=True)
    ) / Decimal(candidate_count)
    prevalence_brier = sum(
        (training_prevalence - Decimal(label)) ** 2 for label in labels
    ) / Decimal(candidate_count)
    return FoldMetrics(
        fold_id=fold_id,
        candidate_count=candidate_count,
        positive_count=positive_count,
        negative_count=candidate_count - positive_count,
        accuracy=Decimal(
            sum(
                prediction == label
                for prediction, label in zip(predicted, labels, strict=True)
            )
        )
        / Decimal(candidate_count),
        precision=None
        if predicted_positive == 0
        else Decimal(true_positive) / Decimal(predicted_positive),
        recall=None
        if positive_count == 0
        else Decimal(true_positive) / Decimal(positive_count),
        brier_score=brier,
        training_prevalence=training_prevalence,
        prevalence_brier_score=prevalence_brier,
        acceptance_coverage=Decimal(sum(accepted)) / Decimal(candidate_count),
        rejected_candidates=candidate_count - sum(accepted),
        calibration_buckets=_calibration_buckets(rows, probabilities),
        filtered=replay_fold(rows, accepted),
        baseline=replay_fold(rows, (True,) * candidate_count),
    )


def evaluate_validation(
    folds: list[FoldMetrics] | tuple[FoldMetrics, ...],
    *,
    attempted_configurations: int,
) -> ValidationReport:
    fold_tuple = tuple(folds)
    failures: list[str] = []
    if len(fold_tuple) < 3:
        failures.append("fewer than three test folds")
    candidate_count = sum(item.candidate_count for item in fold_tuple)
    positive_count = sum(item.positive_count for item in fold_tuple)
    negative_count = sum(item.negative_count for item in fold_tuple)
    if candidate_count < 150:
        failures.append("fewer than 150 out-of-sample candidates")
    if positive_count < 30:
        failures.append("fewer than 30 positive out-of-sample labels")
    if negative_count < 30:
        failures.append("fewer than 30 negative out-of-sample labels")
    for fold in fold_tuple:
        if fold.candidate_count < 30:
            failures.append(f"{fold.fold_id} has fewer than 30 candidates")
        if fold.filtered.expectancy is None:
            failures.append(f"{fold.fold_id} filtered expectancy is undefined")
        elif fold.filtered.expectancy <= 0:
            failures.append(
                f"{fold.fold_id} filtered expectancy is not positive"
            )
        if fold.filtered.maximum_drawdown > fold.baseline.maximum_drawdown:
            failures.append(
                f"{fold.fold_id} filtered drawdown is worse than baseline"
            )
        if fold.brier_score >= fold.prevalence_brier_score:
            failures.append(
                f"{fold.fold_id} Brier score does not beat prevalence"
            )

    filtered_expectancy = _weighted_expectancy(
        tuple(item.filtered for item in fold_tuple)
    )
    baseline_expectancy = _weighted_expectancy(
        tuple(item.baseline for item in fold_tuple)
    )
    if (
        filtered_expectancy is None
        or baseline_expectancy is None
        or filtered_expectancy <= baseline_expectancy
    ):
        failures.append("aggregate filtered expectancy does not beat baseline")
    acceptance_coverage = (
        Decimal("0")
        if candidate_count == 0
        else sum(
            item.acceptance_coverage * Decimal(item.candidate_count)
            for item in fold_tuple
        )
        / Decimal(candidate_count)
    )
    if acceptance_coverage < Decimal("0.10"):
        failures.append("acceptance coverage is below 0.10")
    if acceptance_coverage > Decimal("0.80"):
        failures.append("acceptance coverage is above 0.80")
    aggregate = {
        "candidate_count": candidate_count,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "filtered_expectancy": filtered_expectancy,
        "baseline_expectancy": baseline_expectancy,
        "filtered_net_return": sum(
            (item.filtered.net_return for item in fold_tuple),
            Decimal("0"),
        ),
        "baseline_net_return": sum(
            (item.baseline.net_return for item in fold_tuple),
            Decimal("0"),
        ),
    }
    return ValidationReport(
        fold_metrics=fold_tuple,
        aggregate_metrics=aggregate,
        acceptance_coverage=acceptance_coverage,
        attempted_configurations=attempted_configurations,
        promoted_for_paper=not failures,
        failure_reasons=tuple(failures),
    )


def _weighted_expectancy(
    replays: tuple[ReplayMetrics, ...],
) -> Decimal | None:
    completed = sum(item.completed_trades for item in replays)
    if completed == 0:
        return None
    return sum((item.net_return for item in replays), Decimal("0")) / Decimal(
        completed
    )


def _calibration_buckets(
    rows: tuple[MetaLabelRow, ...],
    probabilities: tuple[Decimal, ...],
) -> tuple[dict[str, object], ...]:
    buckets: list[dict[str, object]] = []
    for index in range(10):
        lower = Decimal(index) / Decimal("10")
        upper = Decimal(index + 1) / Decimal("10")
        members = [
            (probability, rows[position].label)
            for position, probability in enumerate(probabilities)
            if lower <= probability < upper
            or (index == 9 and probability == Decimal("1"))
        ]
        if members:
            buckets.append(
                {
                    "lower": lower,
                    "upper": upper,
                    "count": len(members),
                    "mean_probability": sum(
                        (item[0] for item in members),
                        Decimal("0"),
                    )
                    / Decimal(len(members)),
                    "observed_rate": Decimal(sum(item[1] for item in members))
                    / Decimal(len(members)),
                }
            )
    return tuple(buckets)
