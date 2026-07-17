from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Callable

from market_sentinel.brokers import BrokerAdapter
from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.execution import ExecutionAgent
from market_sentinel.historical_data import expected_sessions
from market_sentinel.models import (
    AccountSnapshot,
    Decision,
    OrderIntent,
    Position,
)


@dataclass(frozen=True)
class PaperLaneState:
    market: str
    symbol: str
    model_version: str
    behavior_checksum: str
    activated_on: date
    last_completed_session: date | None
    sessions_observed: int
    completed_outcomes: int
    prediction_coverage: Decimal
    realized_costs: Decimal
    maximum_drawdown: Decimal
    data_failures: int
    execution_rejects: int
    drift_status: str
    calibration_brier: Decimal | None
    calibration_status: str
    status: str


class PaperValidationStore:
    def __init__(self, root: Path):
        self.root = root

    def activate(
        self,
        market: str,
        symbol: str,
        model_version: str,
        behavior_checksum: str,
        activated_on: date,
    ) -> PaperLaneState:
        _validate_lane(market, symbol)
        current = self.load(market, symbol)
        if current is not None and current.behavior_checksum == behavior_checksum:
            state = replace(current, model_version=model_version)
        else:
            state = PaperLaneState(
                market=market,
                symbol=symbol,
                model_version=model_version,
                behavior_checksum=behavior_checksum,
                activated_on=activated_on,
                last_completed_session=None,
                sessions_observed=0,
                completed_outcomes=0,
                prediction_coverage=Decimal("0"),
                realized_costs=Decimal("0"),
                maximum_drawdown=Decimal("0"),
                data_failures=0,
                execution_rejects=0,
                drift_status="insufficient-history",
                calibration_brier=None,
                calibration_status="insufficient-history",
                status="observing",
            )
            outcomes = self._outcomes_path(market, symbol)
            if outcomes.exists():
                outcomes.unlink()
            calibration = self._calibration_path(market, symbol)
            if calibration.exists():
                calibration.unlink()
        self._write_state(state)
        return state

    def observe_completed_session(
        self,
        market: str,
        symbol: str,
        session: date,
    ) -> PaperLaneState:
        state = self._required_state(market, symbol)
        if session <= state.activated_on:
            raise ValueError("paper sessions must be after activation")
        if (
            state.last_completed_session is not None
            and session <= state.last_completed_session
        ):
            raise ValueError("paper session is duplicate or historical")
        search_start = (
            state.activated_on + timedelta(days=1)
            if state.last_completed_session is None
            else state.last_completed_session + timedelta(days=1)
        )
        candidates = expected_sessions(market, search_start, session)
        if not candidates or candidates[0] != session:
            raise ValueError("paper session skips an expected exchange session")
        observed = state.sessions_observed + 1
        updated = replace(
            state,
            last_completed_session=session,
            sessions_observed=observed,
            status="human-review-eligible" if observed >= 60 else "observing",
        )
        self._write_state(updated)
        return updated

    def record_resolved_prediction(
        self,
        market: str,
        symbol: str,
        probability: Decimal,
        label: int,
    ) -> PaperLaneState:
        state = self._required_state(market, symbol)
        if not Decimal("0") <= probability <= Decimal("1"):
            raise ValueError("paper probability must be between zero and one")
        if label not in {0, 1}:
            raise ValueError("paper label must be zero or one")
        path = self._outcomes_path(market, symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {"probability": str(probability), "label": label},
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        outcomes = tuple(
            json.loads(item)
            for item in path.read_text(encoding="utf-8").splitlines()
            if item.strip()
        )
        count = len(outcomes)
        brier = None
        calibration_status = "insufficient-history"
        if count >= 60:
            brier = sum(
                (
                    Decimal(str(item["probability"]))
                    - Decimal(int(item["label"]))
                )
                ** 2
                for item in outcomes
            ) / Decimal(count)
            calibration_status = "reported"
            self._calibration_path(market, symbol).write_text(
                json.dumps(
                    {
                        "brier_score": str(brier),
                        "buckets": _calibration_buckets(outcomes),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        updated = replace(
            state,
            completed_outcomes=count,
            calibration_brier=brier,
            calibration_status=calibration_status,
        )
        self._write_state(updated)
        return updated

    def load(self, market: str, symbol: str) -> PaperLaneState | None:
        path = self._state_path(market, symbol)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PaperLaneState(
            market=str(payload["market"]),
            symbol=str(payload["symbol"]),
            model_version=str(payload["model_version"]),
            behavior_checksum=str(payload["behavior_checksum"]),
            activated_on=date.fromisoformat(str(payload["activated_on"])),
            last_completed_session=None
            if payload["last_completed_session"] is None
            else date.fromisoformat(str(payload["last_completed_session"])),
            sessions_observed=int(payload["sessions_observed"]),
            completed_outcomes=int(payload["completed_outcomes"]),
            prediction_coverage=Decimal(str(payload["prediction_coverage"])),
            realized_costs=Decimal(str(payload["realized_costs"])),
            maximum_drawdown=Decimal(str(payload["maximum_drawdown"])),
            data_failures=int(payload["data_failures"]),
            execution_rejects=int(payload["execution_rejects"]),
            drift_status=str(payload["drift_status"]),
            calibration_brier=None
            if payload["calibration_brier"] is None
            else Decimal(str(payload["calibration_brier"])),
            calibration_status=str(payload["calibration_status"]),
            status=str(payload["status"]),
        )

    def _required_state(self, market: str, symbol: str) -> PaperLaneState:
        state = self.load(market, symbol)
        if state is None:
            raise ValueError("paper lane is not active")
        return state

    def _write_state(self, state: PaperLaneState) -> None:
        path = self._state_path(state.market, state.symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            key: value.isoformat()
            if isinstance(value, date)
            else str(value)
            if isinstance(value, Decimal)
            else value
            for key, value in asdict(state).items()
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _state_path(self, market: str, symbol: str) -> Path:
        return self.root / market / symbol / "state.json"

    def _outcomes_path(self, market: str, symbol: str) -> Path:
        return self.root / market / symbol / "outcomes.jsonl"

    def _calibration_path(self, market: str, symbol: str) -> Path:
        return self.root / market / symbol / "calibration.json"


class PaperCoordinator:
    def __init__(
        self,
        *,
        settings: Settings,
        alpaca_paper_factory: Callable[[], BrokerAdapter],
        local_simulator: BrokerAdapter,
    ):
        if (
            settings.mode != RuntimeMode.PAPER
            or settings.alpaca_live_trading_enabled
            or settings.alpaca_paper_trading_endpoint
            != "https://paper-api.alpaca.markets"
        ):
            raise ValueError("Alpaca paper endpoint required")
        self.settings = settings
        self.alpaca_paper_factory = alpaca_paper_factory
        self.local_simulator = local_simulator

    def broker_for(self, market: str, symbol: str) -> BrokerAdapter:
        if (market, symbol) == ("US", "SPY"):
            return self.alpaca_paper_factory()
        if (market, symbol) == ("IN", "NIFTYBEES"):
            return self.local_simulator
        raise ValueError("unsupported paper lane")

    def submit_candidate(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
        positions: list[Position],
        *,
        now: datetime,
    ) -> Decision:
        broker = self.broker_for(intent.market, intent.symbol)
        return ExecutionAgent(self.settings, broker).submit(
            intent,
            account,
            positions,
            now=now,
        )


def _validate_lane(market: str, symbol: str) -> None:
    if (market, symbol) not in {("US", "SPY"), ("IN", "NIFTYBEES")}:
        raise ValueError("unsupported paper lane")


def _calibration_buckets(
    outcomes: tuple[dict[str, object], ...],
) -> list[dict[str, object]]:
    buckets: list[dict[str, object]] = []
    for index in range(10):
        lower = Decimal(index) / Decimal("10")
        upper = Decimal(index + 1) / Decimal("10")
        members = [
            item
            for item in outcomes
            if lower <= Decimal(str(item["probability"])) < upper
            or (
                index == 9
                and Decimal(str(item["probability"])) == Decimal("1")
            )
        ]
        if members:
            buckets.append(
                {
                    "lower": str(lower),
                    "upper": str(upper),
                    "count": len(members),
                    "observed_rate": str(
                        Decimal(sum(int(item["label"]) for item in members))
                        / Decimal(len(members))
                    ),
                }
            )
    return buckets
