from dataclasses import dataclass, field
from typing import List
from decimal import Decimal
import os
from dotenv import load_dotenv
from datetime import time

load_dotenv()

@dataclass
class PDTConfig:
    """Pattern Day Trader rule configuration"""
    threshold: Decimal = Decimal('25000')  # PDT rules apply below this equity
    max_day_trades: int = 3  # Max day trades in rolling 5-day period
    warn_at: int = 2  # Log warning when day trade count reaches this

@dataclass
class PollingConfig:
    market_hours_interval: int = 60  # seconds
    after_hours_interval: int = 300  # 5 minutes
    market_open: time = time(9, 30)  # 9:30 AM ET
    market_close: time = time(16, 0)  # 4:00 PM ET
    check_premarket: bool = True
    check_afterhours: bool = True

@dataclass
class StockConfig:
    symbol: str
    max_position_size: Decimal  # Override default position size if needed
    min_strike_delta: float = 0.3  # 30% OTM for CSPs
    max_strike_delta: float = 0.15  # 15% OTM for CCs
    min_days_to_expiry: int = 14
    max_days_to_expiry: int = 45
    take_profit_pct: float = 60.0  # Take profit at this % of max profit
    is_high_iv: bool = False  # Flag for high-volatility tickers

@dataclass
class AlpacaConfig:
    environment: str  # 'paper' or 'live'
    watchlist: List[StockConfig]
    default_position_size: float = 0.2
    max_capital: Decimal = None  # Override Alpaca balance with this limit
    max_contracts_per_symbol: int = 1  # Safety limit per symbol
    polling: PollingConfig = field(default_factory=PollingConfig)
    pdt: PDTConfig = field(default_factory=PDTConfig)

    @property
    def api_key(self) -> str:
        return os.getenv(f"ALPACA_{self.environment.upper()}_API_KEY")
    
    @property
    def api_secret(self) -> str:
        return os.getenv(f"ALPACA_{self.environment.upper()}_API_SECRET")
    
    @property
    def base_url(self) -> str:
        return os.getenv(f"ALPACA_{self.environment.upper()}_BASE_URL") 