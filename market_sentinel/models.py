from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum


class InstrumentType(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    OPTION = "option"
    FUTURE = "future"
    COMMODITY = "commodity"
    CRYPTO = "crypto"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"
    SHORT = "short"
    COVER = "cover"


class DecisionStatus(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True)
class Quote:
    symbol: str
    market: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class Bar:
    symbol: str
    market: str
    close: Decimal
    high: Decimal
    low: Decimal
    volume: int
    timestamp: datetime


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    market: str
    instrument_type: InstrumentType
    side: Side
    quantity: Decimal
    limit_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    strategy_id: str

    def has_protection(self) -> bool:
        return self.stop_loss is not None and self.take_profit is not None


@dataclass(frozen=True)
class OrderRequest:
    intent: OrderIntent
    broker: str
    account_id: str
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    commission: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class Position:
    symbol: str
    market: str
    quantity: Decimal
    average_price: Decimal


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    cash: Decimal
    equity: Decimal
    daily_pnl: Decimal = Decimal("0")
    weekly_pnl: Decimal = Decimal("0")
    monthly_pnl: Decimal = Decimal("0")


@dataclass(frozen=True)
class Decision:
    status: DecisionStatus
    reasons: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.status == DecisionStatus.ALLOW

    @classmethod
    def allow(cls) -> "Decision":
        return cls(DecisionStatus.ALLOW, ())

    @classmethod
    def block(cls, *reasons: str) -> "Decision":
        return cls(DecisionStatus.BLOCK, tuple(reasons))


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    message: str
    severity: str = "info"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, str] = field(default_factory=dict)
