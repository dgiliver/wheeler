import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
import yaml
from datetime import datetime, time, timedelta
import pytz
import pandas as pd
import logging

from src.wheel_bot import WheelBot
from src.models.position import Position, PositionType

logger = logging.getLogger(__name__)

@pytest.fixture
def mock_config_file(tmp_path):
    config = {
        'alpaca': {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'base_url': 'https://paper-api.alpaca.markets'
        },
        'default_position_size': 0.2,
        'watchlist': [
            {
                'symbol': 'AAPL',
                'max_position_size': 0.1,
                'min_strike_delta': 0.3,
                'max_strike_delta': 0.15
            }
        ]
    }
    
    config_file = tmp_path / "test_config.yml"
    with open(config_file, 'w') as f:
        yaml.dump(config, f)
    
    return str(config_file)

@pytest.fixture
def mock_alpaca_service(mocker):
    mock = mocker.patch('src.services.alpaca_service.AlpacaService')
    mock_instance = mock.return_value
    
    # Mock account info with dictionary response
    mock_instance.get_account.return_value = {
        'id': 'test_account',
        'portfolio_value': '100000',
        'cash': '100000',
        'currency': 'USD'
    }
    
    return mock_instance

def test_wheel_bot_initialization(mock_config_file, mock_alpaca_service):
    """Test bot initialization"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        assert bot.config.environment == 'paper'
        assert bot.config.watchlist[0].symbol == 'AAPL'
        assert isinstance(bot.config.watchlist[0].max_position_size, Decimal)

def test_wheel_bot_initialization_error(mock_config_file, mock_alpaca_service):
    """Test bot initialization with account error"""
    # Mock failed account response
    mock_alpaca_service.get_account.return_value = None
    
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        with pytest.raises(ValueError, match="Could not get account information"):
            WheelBot(mock_config_file)

@pytest.mark.asyncio
async def test_check_positions(mock_config_file, mock_alpaca_service, liquid_option):
    """Test checking positions"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Setup mock position
        mock_position = Position(
            symbol="AAPL",
            entry_price=Decimal("150"),
            quantity=100,
            position_type=PositionType.CASH_SECURED_PUT,
            expiration=datetime.now(),
            strike_price=Decimal("145"),
            premium_received=Decimal("500"),
            entry_date=datetime.now()
        )
        
        bot.account_manager.positions = [mock_position]
        
        # Setup price data mock
        mock_alpaca_service.get_price_history.return_value = pd.DataFrame({
            'close': [140.0]
        }, index=pd.date_range(start='2024-01-01', periods=1))
        
        # Setup option chain mock
        mock_alpaca_service.get_option_chain.return_value = [{
            'id': 'option1',
            'symbol': 'AAPL240119P00145000',
            'strike': 145.0,
            'bid': float(liquid_option.bid),
            'ask': float(liquid_option.ask),
            'volume': liquid_option.volume,
            'open_interest': liquid_option.open_interest,
            'implied_volatility': liquid_option.implied_volatility,
            'delta': liquid_option.delta
        }]
        
        # Run check positions
        bot._check_positions()
        
        # Verify API calls
        mock_alpaca_service.get_price_history.assert_called_once()
        mock_alpaca_service.get_option_chain.assert_called_once()

def test_look_for_entries_no_existing_positions(mock_config_file, mock_alpaca_service, liquid_option):
    """Test entry logic when there are no existing positions"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Setup mock data
        mock_alpaca_service.get_position.return_value = None
        bot.account_manager.positions = []
        
        # Setup price data
        mock_alpaca_service.get_price_history.return_value = pd.DataFrame({
            'close': [100, 95, 90, 85, 80]
        }, index=pd.date_range(start='2024-01-01', periods=5))
        
        # Setup option chain
        mock_alpaca_service.get_option_chain.return_value = [{
            'id': 'option1',
            'symbol': 'AAPL240119P00090000',
            'strike': 90.0,
            'bid': float(liquid_option.bid),
            'ask': float(liquid_option.ask),
            'volume': liquid_option.volume,
            'open_interest': liquid_option.open_interest,
            'implied_volatility': liquid_option.implied_volatility,
            'delta': liquid_option.delta
        }]
        
        # Run look for entries
        bot._look_for_entries()
        
        # Verify API calls
        mock_alpaca_service.get_position.assert_called_once()
        mock_alpaca_service.get_price_history.assert_called_once()
        mock_alpaca_service.get_option_chain.assert_called_once()

def test_look_for_entries_with_existing_position(mock_config_file, mock_alpaca_service, liquid_option):
    """Test that we skip entry checks when a position exists"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Setup existing position in account manager
        existing_position = Position(
            symbol="AAPL",  # Match symbol from mock_config
            entry_price=Decimal("150"),
            quantity=100,
            position_type=PositionType.CASH_SECURED_PUT,
            expiration=datetime.now() + timedelta(days=30),
            strike_price=Decimal("145"),
            premium_received=Decimal("500"),
            entry_date=datetime.now()
        )
        bot.account_manager.positions = [existing_position]
        
        # Run look for entries
        bot._look_for_entries()
        
        # Verify we didn't make unnecessary API calls
        mock_alpaca_service.get_price_history.assert_not_called()
        mock_alpaca_service.get_option_chain.assert_not_called()

def test_look_for_entries_with_alpaca_position(mock_config_file, mock_alpaca_service, liquid_option):
    """Test that we skip entry checks when Alpaca reports an existing position"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Reset all mocks
        mock_alpaca_service.get_position.reset_mock()
        mock_alpaca_service.get_price_history.reset_mock()
        mock_alpaca_service.get_option_chain.reset_mock()
        
        # Setup mock data - existing position in Alpaca
        mock_alpaca_service.get_position.return_value = {
            'symbol': 'AAPL',
            'qty': 100,
            'avg_entry_price': '150.00'
        }
        bot.account_manager.positions = []  # No positions in account manager
        
        # Run look for entries
        bot._look_for_entries()
        
        # Verify we didn't make unnecessary API calls
        mock_alpaca_service.get_price_history.assert_not_called()
        mock_alpaca_service.get_option_chain.assert_not_called()

def test_trading_time_detection(mock_config_file, mock_alpaca_service):
    # Patch AlpacaService to use our mock
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        et_tz = pytz.timezone('US/Eastern')
        
        # Test regular market hours
        market_time = datetime.strptime("2024-03-20 14:30:00", "%Y-%m-%d %H:%M:%S")
        market_time = et_tz.localize(market_time)
        assert bot._is_trading_time(market_time) == True
        
        # Test after hours
        after_hours = datetime.strptime("2024-03-20 17:30:00", "%Y-%m-%d %H:%M:%S")
        after_hours = et_tz.localize(after_hours)
        assert bot._is_trading_time(after_hours) == True  # True if check_afterhours is True
        
        # Test non-trading hours
        non_trading = datetime.strptime("2024-03-20 03:30:00", "%Y-%m-%d %H:%M:%S")
        non_trading = et_tz.localize(non_trading)
        assert bot._is_trading_time(non_trading) == False

def test_polling_intervals(mock_config_file, mock_alpaca_service):
    # Patch AlpacaService to use our mock
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        assert bot.config.polling.market_hours_interval == 60
        assert bot.config.polling.after_hours_interval == 300 

def test_look_for_entries_empty_option_chain(mock_config_file, mock_alpaca_service):
    """Test behavior when no options are available"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Reset mock call counts
        mock_alpaca_service.get_position.reset_mock()
        mock_alpaca_service.get_price_history.reset_mock()
        mock_alpaca_service.get_option_chain.reset_mock()
        
        # Setup mock data
        mock_alpaca_service.get_position.return_value = None
        mock_alpaca_service.get_price_history.return_value = pd.DataFrame({
            'close': [100.0]
        }, index=pd.date_range(start='2024-01-01', periods=1))  # Add price history data
        mock_alpaca_service.get_option_chain.return_value = []  # Empty option chain
        
        # Run look for entries
        bot._look_for_entries()
        
        # Verify API calls
        mock_alpaca_service.get_position.assert_called_once()
        mock_alpaca_service.get_price_history.assert_called_once()
        mock_alpaca_service.get_option_chain.assert_called_once()

def test_check_positions_no_positions(mock_config_file, mock_alpaca_service):
    """Test position checking with empty portfolio"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        bot.account_manager.positions = []
        
        # Run check positions
        bot._check_positions()
        
        # Verify no API calls were made
        mock_alpaca_service.get_price_history.assert_not_called()
        mock_alpaca_service.get_option_chain.assert_not_called()

def test_check_positions_stock_position(mock_config_file, mock_alpaca_service):
    """Test position checking with stock position (no expiration)"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Setup stock position (no expiration)
        stock_position = Position(
            symbol="AAPL",
            entry_price=Decimal("150"),
            quantity=100,
            position_type=PositionType.STOCK,
            expiration=None,  # Stock positions have no expiration
            strike_price=None,
            premium_received=None,
            entry_date=datetime.now()
        )
        bot.account_manager.positions = [stock_position]
        
        # Run check positions
        bot._check_positions()
        
        # Verify no option-related API calls were made
        mock_alpaca_service.get_option_chain.assert_not_called()

def test_check_positions_empty_option_chain(mock_config_file, mock_alpaca_service):
    """Test position checking when no options are available for rolling"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Setup option position
        option_position = Position(
            symbol="AAPL",
            entry_price=Decimal("150"),
            quantity=100,
            position_type=PositionType.CASH_SECURED_PUT,
            expiration=datetime.now() + timedelta(days=5),
            strike_price=Decimal("145"),
            premium_received=Decimal("500"),
            entry_date=datetime.now()
        )
        bot.account_manager.positions = [option_position]
        
        # Mock empty option chain
        mock_alpaca_service.get_option_chain.return_value = []
        
        # Setup price data
        def mock_get_price_history(symbol, days=1):
            dates = pd.date_range(start='2024-01-01', periods=1)
            return pd.DataFrame(
                data=[[140.0]],
                index=dates,
                columns=['close']
            )
        mock_alpaca_service.get_price_history.side_effect = mock_get_price_history
        
        # Run check positions
        bot._check_positions()
        
        # Verify we checked but couldn't find options
        mock_alpaca_service.get_option_chain.assert_called_once()

def test_config_loading_missing_fields(tmp_path):
    """Test config loading with missing optional fields"""
    config = {
        'watchlist': [
            {
                'symbol': 'AAPL',
                'max_position_size': 0.1
            }
        ]
    }
    
    config_file = tmp_path / "minimal_config.yml"
    with open(config_file, 'w') as f:
        yaml.dump(config, f)
    
    with patch('src.wheel_bot.AlpacaService') as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.get_account.return_value = {
            'portfolio_value': '100000',
            'cash': '100000'
        }
        
        bot = WheelBot(str(config_file))
        
        # Verify default values were used
        assert bot.config.environment == 'paper'
        assert bot.config.default_position_size == 0.2

@pytest.mark.parametrize('current_time_str,expected', [
    ("09:30:00", True),   # Market open
    ("16:00:00", False),  # Market close (exclusive)
    ("16:01:00", True),   # After-hours start
    ("04:00:00", True),   # Pre-market start
    ("19:59:59", True),   # Late after-hours
    ("20:00:00", False),  # After trading hours
    ("03:59:59", False),  # Before pre-market
])
def test_trading_time_detection_comprehensive(mock_config_file, mock_alpaca_service, current_time_str, expected):
    """Test trading time detection for various times"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        et_tz = pytz.timezone('US/Eastern')
        
        # Create datetime for testing
        current_time = datetime.strptime(f"2024-03-20 {current_time_str}", "%Y-%m-%d %H:%M:%S")
        current_time = et_tz.localize(current_time)
        
        result = bot._is_trading_time(current_time)
        logger.debug(f"Time {current_time_str} ET: expected={expected}, got={result}")
        assert result == expected 

def test_missing_env_vars(mock_config_file):
    """Test bot initialization with missing env vars"""
    with patch('src.wheel_bot.AlpacaService') as mock_service, \
         patch('src.wheel_bot.WheelBot._load_config') as mock_load_config:
        
        # Mock the config that would be loaded
        mock_config = Mock()
        mock_config.api_key = None
        mock_config.api_secret = None
        mock_config.base_url = None
        mock_config.environment = 'paper'
        mock_load_config.return_value = mock_config
        
        # Mock AlpacaService instance
        mock_instance = mock_service.return_value
        mock_account = Mock()
        mock_account.portfolio_value = "100000.00"
        mock_instance.get_account.return_value = mock_account
        
        with pytest.raises(ValueError, match="Missing required environment variables"):
            WheelBot(mock_config_file)

@pytest.mark.asyncio
async def test_run_error_handling(mock_config_file, mock_alpaca_service, caplog):
    """Test error handling in main run loop"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        
        # Make check_positions raise an error
        mock_alpaca_service.get_price_history.side_effect = Exception("API Error")
        
        # Run one iteration
        with patch('time.sleep') as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt]  # Run once then stop
            bot.run()
        
        assert "Error in main loop" in caplog.text

def test_trading_time_premarket(mock_config_file, mock_alpaca_service):
    """Test pre-market trading time check"""
    with patch('src.wheel_bot.AlpacaService', return_value=mock_alpaca_service):
        bot = WheelBot(mock_config_file)
        et_tz = pytz.timezone('US/Eastern')
        
        # Test pre-market with premarket enabled
        premarket_time = datetime.strptime("2024-03-20 08:30:00", "%Y-%m-%d %H:%M:%S")
        premarket_time = et_tz.localize(premarket_time)
        assert bot._is_trading_time(premarket_time) == True 