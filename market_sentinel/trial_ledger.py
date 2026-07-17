from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrialRecord:
    trial_id: str
    stage: str
    market: str
    symbol: str
    dataset_id: str
    dataset_checksum: str
    dataset_range: tuple[str, str]
    feature_schema: str
    label_version: str
    cost_profile_version: str
    fold_definitions: tuple[dict[str, object], ...]
    c_value: Decimal
    threshold_candidates: tuple[Decimal, ...]
    selected_threshold: Decimal | None
    fold_metrics: tuple[dict[str, object], ...]
    aggregate_metrics: dict[str, object]
    promoted_for_paper: bool
    failure_reasons: tuple[str, ...]
    code_commit: str
    created_at: str

    def to_payload(self) -> dict[str, object]:
        return _json_safe(asdict(self))

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "TrialRecord":
        required = {item.name for item in fields(cls)}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError("trial record is missing fields: " + ", ".join(missing))
        promoted = payload["promoted_for_paper"]
        if not isinstance(promoted, bool):
            raise ValueError("promoted_for_paper must be boolean")
        return cls(
            trial_id=str(payload["trial_id"]),
            stage=str(payload["stage"]),
            market=str(payload["market"]),
            symbol=str(payload["symbol"]),
            dataset_id=str(payload["dataset_id"]),
            dataset_checksum=str(payload["dataset_checksum"]),
            dataset_range=tuple(str(item) for item in payload["dataset_range"]),
            feature_schema=str(payload["feature_schema"]),
            label_version=str(payload["label_version"]),
            cost_profile_version=str(payload["cost_profile_version"]),
            fold_definitions=tuple(
                dict(item) for item in payload["fold_definitions"]
            ),
            c_value=Decimal(str(payload["c_value"])),
            threshold_candidates=tuple(
                Decimal(str(item)) for item in payload["threshold_candidates"]
            ),
            selected_threshold=None
            if payload["selected_threshold"] is None
            else Decimal(str(payload["selected_threshold"])),
            fold_metrics=tuple(dict(item) for item in payload["fold_metrics"]),
            aggregate_metrics=dict(payload["aggregate_metrics"]),
            promoted_for_paper=promoted,
            failure_reasons=tuple(
                str(item) for item in payload["failure_reasons"]
            ),
            code_commit=str(payload["code_commit"]),
            created_at=str(payload["created_at"]),
        )


class TrialLedger:
    def __init__(self, path: Path):
        self.path = path

    def append(self, record: TrialRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if record.trial_id in {item.trial_id for item in self.read_all()}:
            raise ValueError("trial id already exists")
        line = json.dumps(
            record.to_payload(),
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def read_all(self) -> tuple[TrialRecord, ...]:
        if not self.path.exists():
            return ()
        return tuple(
            TrialRecord.from_payload(json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value
