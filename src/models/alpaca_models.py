from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Union, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum

# Enums
class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    OPG = "opg"
    CLS = "cls"
    IOC = "ioc"
    FOK = "fok"

class AssetClass(str, Enum):
    US_EQUITY = "us_equity"
    US_OPTION = "us_option"
    CRYPTO = "crypto"

# Request Models (Payloads)
class OptionOrderRequest(BaseModel):
    contract_id: str
    side: OrderSide
    type: OrderType = Field(default=OrderType.MARKET)
    time_in_force: TimeInForce = Field(default=TimeInForce.DAY)
    qty: int
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    client_order_id: Optional[str] = None

    class Config:
        use_enum_values = True

# Response/Data Models (Unpacking)
class Greeks(BaseModel):
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    implied_volatility: float = 0.0

class QuoteData(BaseModel):
    bid_price: float = Field(alias="bp", default=0.0)
    ask_price: float = Field(alias="ap", default=0.0)
    bid_size: int = Field(alias="bs", default=0)
    ask_size: int = Field(alias="as", default=0)
    timestamp: Optional[str] = Field(alias="t", default=None)

    @validator('bid_price', 'ask_price', pre=True)
    def handle_none_prices(cls, v):
        return v or 0.0

class BarData(BaseModel):
    open: float = Field(alias="o", default=0.0)
    high: float = Field(alias="h", default=0.0)
    low: float = Field(alias="l", default=0.0)
    close: float = Field(alias="c", default=0.0)
    volume: int = Field(alias="v", default=0)
    vwap: float = Field(alias="vw", default=0.0)
    num_trades: int = Field(alias="n", default=0)
    timestamp: Optional[str] = Field(alias="t", default=None)

class OptionSnapshot(BaseModel):
    latestQuote: Optional[QuoteData] = None
    latestTrade: Optional[Dict[str, Any]] = None
    dailyBar: Optional[BarData] = None
    greeks: Optional[Greeks] = None
    impliedVolatility: Optional[float] = None
    openInterest: Optional[int] = None

    class Config:
        # Allows fields to be populated even if input dict has different casing if aliases match
        # But mostly we want to unpack the raw API response which is mixed camel/snake depending on endpoint version
        populate_by_name = True

class OptionChainResponse(BaseModel):
    snapshots: Dict[str, OptionSnapshot]
    next_page_token: Optional[str] = None

class AccountResponse(BaseModel):
    id: str
    account_number: str
    status: str
    currency: str
    buying_power: Decimal
    regt_buying_power: Decimal
    daytrading_buying_power: Decimal
    cash: Decimal
    portfolio_value: Decimal
    pattern_day_trader: bool
    trading_blocked: bool
    transfers_blocked: bool
    account_blocked: bool
    created_at: datetime
    shorting_enabled: bool
    equity: Decimal
    last_equity: Decimal
    initial_margin: Decimal
    maintenance_margin: Decimal
    
    class Config:
        # Handle API response fields that might be extra
        extra = "ignore" 

