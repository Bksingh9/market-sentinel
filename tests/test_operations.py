import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from market_sentinel.analysis import AnalysisAgent
from market_sentinel.audit import AuditLog
from market_sentinel.cli import _export_dashboard, main
from market_sentinel.model_store import ModelStore
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

    def test_dashboard_export_includes_model_and_scheduled_orders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.json"
            _export_dashboard(path)
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["model"]["mode"], "advisory")
        self.assertEqual(data["scheduled_orders"][0]["status"], "pending")

    def test_train_model_command_saves_and_activates_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            model_dir = Path(temp_dir) / "models"
            with redirect_stdout(io.StringIO()):
                exit_code = main(["train-model", "--model-dir", str(model_dir)])
            model = ModelStore(model_dir).load_active()

        self.assertEqual(exit_code, 0)
        self.assertGreaterEqual(model.training_rows, 3)
        self.assertIn("momentum", model.feature_names)


if __name__ == "__main__":
    unittest.main()
