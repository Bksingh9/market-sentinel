from __future__ import annotations

from decimal import Decimal

from market_sentinel.models import Bar


class FeatureStore:
    def __init__(self, window: int = 5):
        if window < 2:
            raise ValueError("window must be at least 2")
        self.window = window

    def for_next_bar(self, bars: list[Bar]) -> dict[str, Decimal]:
        if len(bars) < self.window:
            raise ValueError("not enough prior bars")
        prior = bars[-(self.window + 1) : -1] if len(bars) > self.window else bars[-self.window :]
        first_close = prior[0].close
        last_close = prior[-1].close
        momentum = (last_close - first_close) / first_close
        average_volume = Decimal(sum(bar.volume for bar in prior)) / Decimal(len(prior))
        return {
            "last_close": last_close,
            "momentum": momentum.quantize(Decimal("0.0001")).normalize(),
            "average_volume": average_volume,
        }
