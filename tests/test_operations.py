import json
import io
import inspect
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from market_sentinel.analysis import AnalysisAgent
from market_sentinel.audit import AuditLog
from market_sentinel.cli import (
    _assert_challenger_month_available,
    _export_dashboard,
    _meta_label_to_payload,
    _promote_to_paper,
    _research_path,
    _train_market_model,
    _write_immutable_json,
    main,
)
from market_sentinel.config import RuntimeMode, Settings
from market_sentinel.dataset_store import DatasetStore
from market_sentinel.historical_data import (
    AdjustmentMode,
    CanonicalDailyBar,
    expected_sessions,
)
from market_sentinel.ml_features import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, FeatureRow
from market_sentinel.ml_labels import CostBreakdown, MetaLabelRow
from market_sentinel.model_store import ModelStore
from market_sentinel.models import AuditEvent, Fill, Side
from market_sentinel.models import AccountSnapshot, InstrumentType, OrderIntent
from market_sentinel.paper_validation import PaperCoordinator
from market_sentinel.portfolio import PortfolioAgent
from market_sentinel.ruflo import RUFLOAgent


class OperationsTest(unittest.TestCase):
    def test_portfolio_applies_buy_fill(self):
        portfolio = PortfolioAgent(cash=Decimal("1000"))
        portfolio.apply_fill(Fill("SPY", Side.BUY, Decimal("1"), Decimal("500"), Decimal("1"), datetime.now(timezone.utc)))

        snapshot = portfolio.snapshot("paper-local")

        self.assertEqual(snapshot.cash, Decimal("499"))
        self.assertEqual(snapshot.equity, Decimal("999"))

    def test_audit_log_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit.jsonl"
            log = AuditLog(path)
            log.append(AuditEvent("risk.block", "blocked for test", "warning", details={"reason": "cap"}))

            events = log.read_latest(limit=1)

        self.assertEqual(events[0]["event_type"], "risk.block")
        self.assertEqual(events[0]["details"]["reason"], "cap")

    def test_analysis_reports_drawdown(self):
        summary = AnalysisAgent().summarize_equity([Decimal("100"), Decimal("110"), Decimal("90")])

        self.assertEqual(summary["max_drawdown"], Decimal("0.1818"))

    def test_ruflo_has_no_order_authority(self):
        report = RUFLOAgent().checklist_status()

        self.assertFalse(report["can_place_orders"])

    def test_train_market_model_requires_real_dataset_and_never_uses_synthetic_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "train-market-model",
                        "--market",
                        "US",
                        "--symbol",
                        "SPY",
                        "--dataset-id",
                        "missing",
                        "--data-root",
                        directory,
                    ]
                )
        self.assertNotEqual(exit_code, 0)
        self.assertIn("dataset", output.getvalue().lower())
        self.assertNotIn("accuracy gate", output.getvalue().lower())

    def test_historical_commands_do_not_import_or_construct_live_brokers(self):
        source = inspect.getsource(__import__("market_sentinel.cli", fromlist=["*"]))
        research_source = source[
            source.index("def _download_data") : source.index("def _submit_order")
        ]
        self.assertNotIn("GrowwBrokerAdapter", research_source)
        self.assertNotIn("AlpacaBrokerAdapter", research_source)
        self.assertNotIn("ExecutionAgent", research_source)

    def test_failed_validation_cannot_activate_paper_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "promote-to-paper",
                        "--market",
                        "US",
                        "--symbol",
                        "SPY",
                        "--version",
                        "failed-v1",
                        "--model-root",
                        directory,
                    ]
                )
            pointer = Path(directory) / "US" / "SPY" / "active-paper.txt"
        self.assertEqual(exit_code, 1)
        self.assertFalse(pointer.exists())

    def test_only_one_challenger_per_lane_per_calendar_month(self):
        records = (
            SimpleNamespace(
                stage="walk-forward-validation",
                market="US",
                symbol="SPY",
                created_at="2026-07-01T00:00:00+00:00",
            ),
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "challenger already created for 2026-07",
        ):
            _assert_challenger_month_available(
                records,
                "US",
                "SPY",
                datetime(2026, 7, 20, tzinfo=timezone.utc),
            )

    def test_paper_promotion_starts_lane_clock_without_changing_live_mode(self):
        calls: list[tuple[object, ...]] = []

        class FakeModelStore:
            def load(self, market, symbol, version):
                return SimpleNamespace(
                    promoted_for_paper=True,
                    behavior_checksum="behavior-a",
                )

            def activate_for_paper(self, market, symbol, version):
                calls.append(("model", market, symbol, version))

        class FakePaperStore:
            def activate(self, market, symbol, version, checksum, activated_on):
                calls.append(
                    ("paper", market, symbol, version, checksum, activated_on)
                )

        args = SimpleNamespace(
            market="US",
            symbol="SPY",
            version="spy-v1",
            model_root="models",
            paper_root="paper",
        )
        result = _promote_to_paper(
            args,
            model_store_factory=lambda _: FakeModelStore(),
            paper_store_factory=lambda _: FakePaperStore(),
            activated_on=datetime(2026, 7, 17, tzinfo=timezone.utc).date(),
        )
        self.assertEqual(calls[0], ("model", "US", "SPY", "spy-v1"))
        self.assertEqual(calls[1][:5], ("paper", "US", "SPY", "spy-v1", "behavior-a"))
        self.assertFalse(result["live_mode_changed"])

    def test_dashboard_exports_two_non_aggregated_sanitized_lanes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            _export_dashboard(
                path,
                model_dir=Path(directory) / "models",
                data_root=Path(directory) / "datasets",
                paper_root=Path(directory) / "paper",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(payload["lanes"]), {"US:SPY", "IN:NIFTYBEES"})
        encoded = json.dumps(payload).lower()
        self.assertNotIn("ready_to_trade", encoded)
        self.assertNotIn("api_key", encoded)
        self.assertNotIn("secret", encoded)
        for lane in payload["lanes"].values():
            self.assertFalse(lane["paper"]["complete"])
            self.assertIn("modeled_costs", lane["validation"])
            self.assertIn("expectancy", lane["validation"])
            self.assertIn("coverage", lane["validation"])

    def test_dashboard_has_no_order_submission_or_manual_readiness_control(self):
        source = Path("apps/control-center/app/page.tsx").read_text(
            encoding="utf-8"
        ).lower()
        self.assertNotIn("submit-order", source)
        self.assertNotIn("ready_to_trade", source)
        self.assertNotIn("place order", source)

    def test_dual_lane_research_to_paper_never_calls_live_order_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = DualLaneHarness(Path(directory))
            spy = harness.run_lane("US", "SPY")
            nifty = harness.run_lane("IN", "NIFTYBEES")
            harness.submit_paper_candidates()

        self.assertEqual(spy.execution_target, "alpaca-paper")
        self.assertEqual(nifty.execution_target, "local-simulator")
        self.assertNotEqual(spy.dataset_id, nifty.dataset_id)
        self.assertNotEqual(spy.model_version, nifty.model_version)
        self.assertEqual(harness.live_endpoint_calls, [])
        self.assertEqual(harness.groww_order_calls, [])
        self.assertEqual(
            harness.alpaca_paper_calls,
            ["https://paper-api.alpaca.markets/v2/orders"],
        )
        self.assertEqual(harness.local_simulator_fills, 1)

    def test_cli_module_invocation_runs_status_command(self):
        result = subprocess.run(
            [sys.executable, "-m", "market_sentinel.cli", "status"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn('"mode"', result.stdout)

    def test_submit_order_requires_real_money_confirmation(self):
        stream = io.StringIO()

        with redirect_stdout(stream):
            exit_code = main(
                [
                    "submit-order",
                    "--broker",
                    "groww",
                    "--symbol",
                    "IDEA",
                    "--side",
                    "buy",
                    "--quantity",
                    "1",
                    "--limit-price",
                    "10.5",
                    "--stop-loss",
                    "10",
                    "--take-profit",
                    "11",
                    "--confirm-real-money",
                    "NO",
                ]
            )

        data = json.loads(stream.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertFalse(data["live_order_submitted"])
        self.assertIn("--confirm-real-money", data["reasons"][0])

    def test_submit_order_blocks_when_live_preflight_is_not_ready(self):
        stream = io.StringIO()

        with redirect_stdout(stream):
            exit_code = main(
                [
                    "submit-order",
                    "--broker",
                    "groww",
                    "--symbol",
                    "IDEA",
                    "--side",
                    "buy",
                    "--quantity",
                    "1",
                    "--limit-price",
                    "10.5",
                    "--stop-loss",
                    "10",
                    "--take-profit",
                    "11",
                    "--confirm-real-money",
                    "I_CONFIRM_REAL_MONEY_ORDER",
                ]
            )

        data = json.loads(stream.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(data["live_order_submitted"])
        self.assertEqual(data["decision"], "blocked")
        self.assertIn("live preflight is not ready", data["reasons"])


class RecordingBroker:
    def __init__(self, name: str, calls: list[str], endpoint: str | None = None):
        self.name = name
        self.calls = calls
        self.endpoint = endpoint

    def place_order(self, intent: OrderIntent) -> Fill:
        self.calls.append(
            f"{self.endpoint}/v2/orders" if self.endpoint else intent.symbol
        )
        return Fill(
            intent.symbol,
            intent.side,
            intent.quantity,
            intent.limit_price,
            Decimal("0"),
            datetime.now(timezone.utc),
        )


class DualLaneHarness:
    def __init__(self, root: Path):
        self.root = root
        self.data_root = root / "datasets"
        self.model_root = root / "models"
        self.trial_root = root / "trials"
        self.paper_root = root / "paper"
        self.live_endpoint_calls: list[str] = []
        self.groww_order_calls: list[str] = []
        self.alpaca_paper_calls: list[str] = []
        self.local_calls: list[str] = []
        self.local_simulator_fills = 0

    def run_lane(self, market: str, symbol: str) -> SimpleNamespace:
        dataset_id = self._write_research_dataset(market, symbol)
        result = _train_market_model(
            Namespace(
                market=market,
                symbol=symbol,
                dataset_id=dataset_id,
                data_root=str(self.data_root),
                model_root=str(self.model_root),
                trial_root=str(self.trial_root),
            ),
            now=datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc),
        )
        if not result["promoted_for_paper"]:
            raise AssertionError(result["failure_reasons"])
        version = str(result["version"])
        _promote_to_paper(
            Namespace(
                market=market,
                symbol=symbol,
                version=version,
                model_root=str(self.model_root),
                paper_root=str(self.paper_root),
            ),
            activated_on=date(2026, 7, 17),
        )
        return SimpleNamespace(
            dataset_id=dataset_id,
            model_version=version,
            execution_target=(
                "alpaca-paper" if market == "US" else "local-simulator"
            ),
        )

    def submit_paper_candidates(self) -> None:
        alpaca = RecordingBroker(
            "alpaca",
            self.alpaca_paper_calls,
            "https://paper-api.alpaca.markets",
        )

        class LocalSimulator(RecordingBroker):
            def place_order(inner_self, intent: OrderIntent) -> Fill:
                self.local_simulator_fills += 1
                return super().place_order(intent)

        local = LocalSimulator("mock", self.local_calls)
        coordinator = PaperCoordinator(
            settings=Settings(mode=RuntimeMode.PAPER),
            alpaca_paper_factory=lambda: alpaca,
            local_simulator=local,
        )
        account = AccountSnapshot(
            "paper-local",
            Decimal("100000"),
            Decimal("100000"),
        )
        now = datetime(2026, 7, 17, tzinfo=timezone.utc)
        coordinator.submit_candidate(
            self._intent("US", "SPY"),
            account,
            [],
            now=now,
        )
        coordinator.submit_candidate(
            self._intent("IN", "NIFTYBEES"),
            account,
            [],
            now=now,
        )

    def _write_research_dataset(self, market: str, symbol: str) -> str:
        currency = "USD" if market == "US" else "INR"
        provider = "alpaca" if market == "US" else "groww"
        adjustment = (
            AdjustmentMode.ALL
            if market == "US"
            else AdjustmentMode.PROVIDER_UNSPECIFIED
        )
        sessions = expected_sessions(
            market,
            date(2020, 1, 1),
            date(2025, 12, 31),
        )[:740]
        bar = CanonicalDailyBar(
            provider=provider,
            provider_symbol=symbol,
            symbol=symbol,
            market=market,
            currency=currency,
            trading_date=sessions[0],
            source_timezone=(
                "America/New_York" if market == "US" else "Asia/Kolkata"
            ),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=1000000,
            adjustment_mode=adjustment,
            retrieved_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
            source_checksum=("a" if market == "US" else "b") * 64,
        )
        stored = DatasetStore(self.data_root).write(
            (bar,),
            requested_start=sessions[0],
            requested_end=sessions[-1],
            interval="1Day",
            page_count=1,
            feed="iex" if market == "US" else None,
        )
        rows = tuple(
            self._row(market, symbol, currency, sessions, index)
            for index in range(360)
        )
        payload = {
            "dataset_id": stored.manifest.dataset_id,
            "dataset_checksum": stored.manifest.dataset_id,
            "market": market,
            "symbol": symbol,
            "currency": currency,
            "feature_schema": FEATURE_SCHEMA_VERSION,
            "label_version": "protected-2-3-10-v1",
            "cost_profile_version": f"{market.lower()}-cost-test-v1",
            "reconciliation_record_id": None,
            "sessions": [item.isoformat() for item in sessions],
            "rows": [_meta_label_to_payload(item) for item in rows],
        }
        _write_immutable_json(
            _research_path(
                self.data_root,
                market,
                symbol,
                stored.manifest.dataset_id,
            ),
            payload,
        )
        return stored.manifest.dataset_id

    @staticmethod
    def _row(
        market: str,
        symbol: str,
        currency: str,
        sessions: tuple[date, ...],
        index: int,
    ) -> MetaLabelRow:
        label = index % 2
        feature_date = sessions[index * 2]
        entry_date = sessions[(index * 2) + 1]
        end_date = entry_date
        feature_value = Decimal("1") if label else Decimal("-1")
        feature = FeatureRow(
            symbol=symbol,
            market=market,
            currency=currency,
            feature_as_of=feature_date,
            entry_eligible_at=entry_date,
            feature_schema=FEATURE_SCHEMA_VERSION,
            last_close=Decimal("100"),
            current_volume=Decimal("1000000"),
            average_volume_20=Decimal("1000000"),
            values={name: feature_value for name in FEATURE_ORDER},
        )
        gross = Decimal("0.021") if label else Decimal("-0.009")
        cost = Decimal("0.001")
        net = gross - cost
        return MetaLabelRow(
            feature_row=feature,
            label=label,
            entry_date=entry_date,
            entry_price_before_costs=Decimal("100"),
            exit_date=end_date,
            exit_price_before_costs=Decimal("100") + gross,
            label_end_at=end_date,
            holding_sessions=1,
            exit_reason="target" if label else "stop",
            gross_pnl=gross,
            costs=CostBreakdown(
                commission=Decimal("0.001"),
                regulatory=Decimal("0"),
                tax=Decimal("0"),
                spread=Decimal("0"),
                slippage=Decimal("0"),
                flat=Decimal("0"),
            ),
            total_cost=cost,
            net_pnl=net,
            cost_profile_version=f"{market.lower()}-cost-test-v1",
        )

    @staticmethod
    def _intent(market: str, symbol: str) -> OrderIntent:
        return OrderIntent(
            symbol=symbol,
            market=market,
            instrument_type=InstrumentType.ETF,
            side=Side.BUY,
            quantity=Decimal("1"),
            limit_price=Decimal("100"),
            stop_loss=Decimal("98"),
            take_profit=Decimal("103"),
            strategy_id="dual-lane-paper-test",
        )


if __name__ == "__main__":
    unittest.main()
