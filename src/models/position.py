from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class PositionType(str, Enum):
    CASH_SECURED_PUT = "CSP"
    COVERED_CALL = "CC"
    STOCK = "STOCK"
    OPTION = "OPTION"


class OptionQuote(BaseModel):
    bid: Decimal
    ask: Decimal
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float

    @property
    def spread_percentage(self) -> float:
        """Calculate the bid-ask spread as a percentage"""
        if self.ask == 0:
            return float("inf")
        return float((self.ask - self.bid) / self.ask * 100)

    @property
    def is_liquid(self) -> bool:
        """Check if the option is liquid enough"""
        return self.volume > 50 and self.open_interest > 100 and self.spread_percentage < 15


class Position(BaseModel):
    symbol: str
    entry_price: Decimal
    quantity: int
    position_type: PositionType
    expiration: datetime | None = None
    strike_price: Decimal | None = None
    premium_received: Decimal | None = Field(default=Decimal("0"))
    entry_date: datetime = Field(default_factory=datetime.now)
    max_loss: Decimal | None = None
    contracts: int = 1

    class Config:
        arbitrary_types_allowed = True

    @property
    def total_cost(self) -> Decimal:
        """Calculate total position cost"""
        if self.position_type == PositionType.STOCK:
            return self.entry_price * Decimal(str(self.quantity))
        else:
            # For options, use strike price * 100 shares per contract * number of contracts
            if self.strike_price is None:
                return Decimal("0")
            return self.strike_price * Decimal("100") * Decimal(str(self.contracts))

    @property
    def days_held(self) -> int:
        return (datetime.now() - self.entry_date).days
