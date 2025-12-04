import pytest
import os
from dotenv import load_dotenv
import yaml
from decimal import Decimal
import pandas as pd
from datetime import datetime
from src.models import OptionQuote

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Setup mock environment variables for testing"""
    os.environ['ALPACA_PAPER_API_KEY'] = 'test_paper_key'
    os.environ['ALPACA_PAPER_API_SECRET'] = 'test_paper_secret'
    os.environ['ALPACA_PAPER_BASE_URL'] = 'https://paper-api.alpaca.markets'
    
    os.environ['ALPACA_LIVE_API_KEY'] = 'test_live_key'
    os.environ['ALPACA_LIVE_API_SECRET'] = 'test_live_secret'
    os.environ['ALPACA_LIVE_BASE_URL'] = 'https://api.alpaca.markets' 

@pytest.fixture
def mock_config_file(tmp_path):
    config = {
        'environment': 'paper',
        'default_position_size': 0.2,
        'polling': {
            'market_hours_interval': 60,
            'after_hours_interval': 300,
            'check_premarket': True,
            'check_afterhours': True
        },
        'watchlist': [
            {
                'symbol': 'AAPL',
                'max_position_size': 0.1,
                'min_strike_delta': 0.3,
                'max_strike_delta': 0.15,
                'min_days_to_expiry': 30,
                'max_days_to_expiry': 45
            }
        ]
    }
    
    config_file = tmp_path / "test_config.yml"
    with open(config_file, 'w') as f:
        yaml.dump(config, f)
    
    return str(config_file) 

@pytest.fixture
def mock_alpaca_api(mocker):
    mock = mocker.patch('alpaca_trade_api.REST')
    mock_instance = mock.return_value
    
    # Mock account info
    mock_account = mocker.Mock()
    mock_account.portfolio_value = '100000'
    mock_instance.get_account.return_value = mock_account
    
    # Mock get_bars to return a DataFrame
    def mock_get_bars(symbol, start=None, end=None):
        dates = pd.date_range(start='2024-01-01', periods=1)
        return pd.DataFrame(
            data=[[150.0, 152.0, 149.0, 151.0, 1000000]],
            index=dates,
            columns=['open', 'high', 'low', 'close', 'volume']
        )
    
    mock_instance.get_bars.side_effect = mock_get_bars
    
    return mock_instance

@pytest.fixture
def mock_alpaca_service(mocker):
    mock = mocker.patch('src.services.alpaca_service.AlpacaService')
    mock_instance = mock.return_value
    
    # Mock get_account
    mock_account = mocker.Mock()
    mock_account.portfolio_value = '100000'
    mock_instance.get_account.return_value = mock_account
    
    # Mock get_price_history to return DataFrame
    def mock_get_price_history(symbol, days=1):
        dates = pd.date_range(start='2024-01-01', periods=1)
        return pd.DataFrame(
            data=[[150.0]],
            index=dates,
            columns=['close']
        )
    
    mock_instance.get_price_history.side_effect = mock_get_price_history
    
    return mock_instance

@pytest.fixture
def liquid_option():
    return OptionQuote(
        bid=Decimal("1.00"),
        ask=Decimal("1.10"),
        volume=200,
        open_interest=500,
        implied_volatility=30.0,
        delta=0.3
    )

@pytest.fixture
def illiquid_option():
    return OptionQuote(
        bid=Decimal("1.00"),
        ask=Decimal("1.50"),  # Wide spread
        volume=10,  # Low volume
        open_interest=50,  # Low open interest
        implied_volatility=35.0,
        delta=0.25
    ) 