import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import pandas as pd

from src.wheel_bot import WheelBot
from src.config.settings import AlpacaConfig, StockConfig
from src.models.position import Position, PositionType, OptionQuote

@pytest.fixture
def mock_market_data():
    """Create mock market data for testing"""
    dates = pd.date_range(start='2024-01-01', periods=20)
    data = {
        'date': dates,
        'close': [100] * 10 + [80] * 5 + [64] * 3 + [62] * 2,  # Price decline scenario
        'open': [x + 1 for x in [100] * 10 + [80] * 5 + [64] * 3 + [62] * 2],
        'high': [x + 2 for x in [100] * 10 + [80] * 5 + [64] * 3 + [62] * 2],
        'low': [x - 1 for x in [100] * 10 + [80] * 5 + [64] * 3 + [62] * 2],
        'volume': [1000000] * 20
    }
    return pd.DataFrame(data).set_index('date')

@pytest.fixture
def mock_yf_data():
    """Create mock Yahoo Finance data for testing"""
    return pd.DataFrame({
        'open': [100.0] * 10 + [80.0] * 5 + [64.0] * 3 + [62.0] * 2,
        'high': [102.0] * 10 + [82.0] * 5 + [66.0] * 3 + [64.0] * 2,
        'low': [98.0] * 10 + [78.0] * 5 + [62.0] * 3 + [60.0] * 2,
        'close': [100.0] * 10 + [80.0] * 5 + [64.0] * 3 + [62.0] * 2,
        'volume': [1000000] * 20
    }, index=pd.date_range(start='2024-01-01', periods=20))

@pytest.mark.integration
def test_full_wheel_cycle(mock_yf_data, mock_config_file, mock_alpaca_service, liquid_option):
    """Test a full wheel strategy cycle"""
    with patch('yfinance.Ticker') as mock_yf:
        # Setup YF mock
        mock_yf_instance = Mock()
        mock_yf_instance.history.return_value = mock_yf_data
        mock_yf.return_value = mock_yf_instance
        
        # Setup Alpaca mocks
        mock_alpaca_service.get_account.return_value = {
            'portfolio_value': '100000',
            'cash': '100000'
        }
        mock_alpaca_service.get_position.return_value = None
        
        with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
            bot = WheelBot(mock_config_file)
            
            # Test CSP entry
            mock_alpaca_service.get_option_chain.return_value = [{
                'id': 'csp1',
                'symbol': 'AAPL240119P00090000',
                'strike': 90.0,
                'bid': float(liquid_option.bid),
                'ask': float(liquid_option.ask),
                'volume': liquid_option.volume,
                'open_interest': liquid_option.open_interest,
                'implied_volatility': liquid_option.implied_volatility,
                'delta': liquid_option.delta
            }]
            
            bot._look_for_entries()
            # Add assertions for CSP entry

@pytest.mark.integration
def test_position_sizing_and_risk_management(mock_config_file, mock_alpaca_service):
    """Test position sizing and risk management"""
    # Setup mock responses
    mock_alpaca_service.get_account.return_value = {
        'portfolio_value': '100000',
        'cash': '100000'
    }
    
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Test position size limits
        max_position = bot.account_manager.get_max_contracts(
            strike_price=Decimal('100'),
            existing_symbol=None
        )
        assert max_position > 0
        assert max_position * Decimal('100') * Decimal('100') <= Decimal('20000')  # 20% of 100k

@pytest.mark.integration
def test_near_expiry_roll(mock_config_file, mock_alpaca_service, liquid_option):
    """Test rolling near-expiry options"""
    # Setup mock responses
    mock_alpaca_service.get_account.return_value = {
        'portfolio_value': '100000',
        'cash': '100000'
    }
    
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Add near-expiry position
        near_expiry_position = Position(
            symbol="AAPL",
            entry_price=Decimal("1.50"),
            quantity=100,
            position_type=PositionType.CASH_SECURED_PUT,
            expiration=datetime.now() + timedelta(days=2),  # Near expiry
            strike_price=Decimal("145"),
            premium_received=Decimal("150"),
            entry_date=datetime.now() - timedelta(days=28)
        )
        bot.account_manager.positions = [near_expiry_position]
        
        # Setup mock data for rolling
        mock_alpaca_service.get_price_history.return_value = pd.DataFrame({
            'close': [140.0]
        }, index=pd.date_range(start='2024-01-01', periods=1))
        
        mock_alpaca_service.get_option_chain.return_value = [{
            'id': 'roll1',
            'symbol': 'AAPL240216P00145000',  # Further expiry
            'strike': 145.0,
            'bid': float(liquid_option.bid),
            'ask': float(liquid_option.ask),
            'volume': liquid_option.volume,
            'open_interest': liquid_option.open_interest,
            'implied_volatility': liquid_option.implied_volatility,
            'delta': liquid_option.delta
        }]
        
        bot._check_positions()
        # Add assertions for rolling behavior