from __future__ import annotations

from decimal import Decimal

from market_sentinel.models import AccountSnapshot, Fill, Position, Side


class PortfolioAgent:
    def __init__(self, cash: Decimal):
        self.cash = cash
        self.positions: dict[str, Position] = {}

    def apply_fill(self, fill: Fill) -> None:
        total_cost = (fill.quantity * fill.price) + fill.commission
        if fill.side == Side.BUY:
            self.cash -= total_cost
            current = self.positions.get(fill.symbol)
            if current is None:
                self.positions[fill.symbol] = Position(fill.symbol, "US", fill.quantity, fill.price)
            else:
                total_quantity = current.quantity + fill.quantity
                average = ((current.quantity * current.average_price) + (fill.quantity * fill.price)) / total_quantity
                self.positions[fill.symbol] = Position(current.symbol, current.market, total_quantity, average)
        elif fill.side == Side.SELL:
            self.cash += (fill.quantity * fill.price) - fill.commission

    def snapshot(self, account_id: str) -> AccountSnapshot:
        position_value = sum(position.quantity * position.average_price for position in self.positions.values())
        return AccountSnapshot(account_id=account_id, cash=self.cash, equity=self.cash + position_value)
