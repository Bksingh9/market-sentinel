from __future__ import annotations

from decimal import Decimal


class AnalysisAgent:
    def summarize_equity(self, equity_curve: list[Decimal]) -> dict[str, Decimal]:
        if not equity_curve:
            return {"start": Decimal("0"), "end": Decimal("0"), "return": Decimal("0"), "max_drawdown": Decimal("0")}
        peak = equity_curve[0]
        max_drawdown = Decimal("0")
        for value in equity_curve:
            peak = max(peak, value)
            if peak > 0:
                drawdown = (peak - value) / peak
                max_drawdown = max(max_drawdown, drawdown)
        start = equity_curve[0]
        end = equity_curve[-1]
        total_return = Decimal("0") if start == 0 else (end - start) / start
        return {
            "start": start,
            "end": end,
            "return": total_return.quantize(Decimal("0.0001")),
            "max_drawdown": max_drawdown.quantize(Decimal("0.0001")),
        }
