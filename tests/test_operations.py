import json
import io
import inspect
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from market_sentinel.analysis import AnalysisAgent
from market_sentinel.audit import AuditLog
from market_sentinel.cli import _assert_challenger_month_available, main
from market_sentinel.models import AuditEvent, Fill, Side
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


if __name__ == "__main__":
    unittest.main()
