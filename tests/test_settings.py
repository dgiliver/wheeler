import pytest
from decimal import Decimal
from src.config.settings import StockConfig, AlpacaConfig

def test_stock_config_defaults():
    config = StockConfig(
        symbol="AAPL",
        max_position_size=Decimal("0.1")
    )
    
    assert config.symbol == "AAPL"
    assert config.max_position_size == Decimal("0.1")
    assert config.min_strike_delta == 0.3
    assert config.max_strike_delta == 0.15
    assert config.min_days_to_expiry == 30
    assert config.max_days_to_expiry == 45

def test_stock_config_custom_values():
    config = StockConfig(
        symbol="SPY",
        max_position_size=Decimal("0.2"),
        min_strike_delta=0.25,
        max_strike_delta=0.1,
        min_days_to_expiry=45,
        max_days_to_expiry=60
    )
    
    assert config.symbol == "SPY"
    assert config.max_position_size == Decimal("0.2")
    assert config.min_strike_delta == 0.25
    assert config.max_strike_delta == 0.1
    assert config.min_days_to_expiry == 45
    assert config.max_days_to_expiry == 60

def test_alpaca_config():
    watchlist = [
        StockConfig(symbol="AAPL", max_position_size=Decimal("0.1")),
        StockConfig(symbol="SPY", max_position_size=Decimal("0.15"))
    ]
    
    config = AlpacaConfig(
        environment="paper",
        watchlist=watchlist
    )
    
    assert config.environment == "paper"
    assert len(config.watchlist) == 2
    assert config.default_position_size == 0.2  # Default value 