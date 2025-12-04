import logging
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from src.config.settings import AlpacaConfig, StockConfig
from src.services.alpaca_service import AlpacaService

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_config():
    return AlpacaConfig(
        environment="paper",
        watchlist=[
            StockConfig(symbol="AAPL", max_position_size=Decimal("0.1"), min_strike_delta=0.3, max_strike_delta=0.15)
        ],
    )


@pytest.fixture
def mock_response():
    def _mock_response(status_code=200, json_data=None, text=""):
        mock = Mock()
        mock.ok = status_code == 200
        mock.status_code = status_code
        mock.content = True
        mock.text = text

        # Set up json method as a Mock that returns the data
        mock.json = Mock(return_value=json_data if json_data is not None else {})
        return mock

    return _mock_response


@pytest.fixture
def mock_yf_ticker():
    with patch("yfinance.Ticker") as mock:
        # Setup mock history data
        mock_history = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [98.0, 99.0],
                "Close": [101.0, 102.0],
                "Volume": [1000000, 1100000],
            },
            index=pd.date_range(start="2024-01-01", periods=2),
        )

        mock_instance = Mock()
        mock_instance.history.return_value = mock_history
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_trading_client():
    """Mock the Alpaca TradingClient"""
    mock_client = MagicMock()

    # Mock account
    mock_account = MagicMock()
    mock_account.portfolio_value = "150000"
    mock_account.cash = "100000"
    mock_account.equity = "150000"
    mock_account.daytrade_count = 0
    mock_account.pattern_day_trader = False
    mock_client.get_account.return_value = mock_account

    # Mock positions (empty by default)
    mock_client.get_all_positions.return_value = []

    return mock_client


@pytest.fixture
def alpaca_service(mock_config, mock_response, mock_trading_client):
    """Create AlpacaService instance with mock config"""
    with (
        patch("requests.request", return_value=mock_response(json_data={})),
        patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client),
    ):
        return AlpacaService(mock_config)


def test_get_account(mock_config, mock_trading_client):
    """Test getting account information"""
    with patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client):
        service = AlpacaService(mock_config)
        account = service.get_account()

        assert account is not None
        assert account["portfolio_value"] == "150000"
        assert account["cash"] == "100000"


def test_get_positions(mock_config, mock_trading_client):
    """Test getting all positions"""
    # Setup mock position
    mock_position = MagicMock()
    mock_position.symbol = "AAPL"
    mock_position.qty = "100"
    mock_position.avg_entry_price = "150.00"
    mock_position.asset_class = "us_equity"
    mock_trading_client.get_all_positions.return_value = [mock_position]

    with patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client):
        service = AlpacaService(mock_config)
        positions = service.get_positions()

        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"


def test_get_price_history_success(alpaca_service, mock_yf_ticker):
    """Test successful price history retrieval"""
    df = alpaca_service.get_price_history("AAPL", days=2)

    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df["close"].iloc[-1] == 102.0


def test_get_price_history_empty(alpaca_service, mock_yf_ticker):
    """Test handling of empty price history"""
    # Mock empty DataFrame response
    mock_yf_ticker.return_value.history.return_value = pd.DataFrame()

    df = alpaca_service.get_price_history("AAPL")
    assert df.empty


def test_get_price_history_error(alpaca_service, mock_yf_ticker):
    """Test error handling in price history retrieval"""
    # Mock error in yfinance
    mock_yf_ticker.return_value.history.side_effect = Exception("YF API Error")

    df = alpaca_service.get_price_history("AAPL")
    assert df.empty


def test_get_option_chain(mock_config, mock_response, mock_trading_client, caplog):
    """Test getting option chain"""
    caplog.set_level(logging.DEBUG)

    # Use a future date for the contract symbol
    future_date = datetime.now() + timedelta(days=30)
    contract_symbol = f"AAPL{future_date.strftime('%y%m%d')}P00150000"

    # Mock response for options snapshot with correct structure
    mock_data = {
        "snapshots": {
            contract_symbol: {
                "latestQuote": {"bp": 1.00, "ap": 1.10, "bs": 10, "as": 10},
                "greeks": {
                    "delta": -0.3,
                    "gamma": 0.01,
                    "theta": -0.05,
                    "vega": 0.1,
                    "rho": 0.01,
                    "implied_volatility": 0.3,
                },
                "openInterest": 500,
                "impliedVolatility": 0.3,
            }
        }
    }

    with (
        patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client),
        patch("requests.request", return_value=mock_response(json_data=mock_data)),
    ):
        service = AlpacaService(mock_config)
        chain = service.get_option_chain("AAPL", future_date, min_dte=0, max_dte=45)

        assert len(chain) == 1
        assert chain[0]["bid"] == 1.00
        assert chain[0]["ask"] == 1.10


def test_place_option_order(mock_config, mock_response, mock_trading_client):
    """Test placing an option order"""
    mock_data = {"id": "order1", "status": "accepted"}

    with (
        patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client),
        patch("requests.request", return_value=mock_response(json_data=mock_data)) as mock_request,
    ):
        service = AlpacaService(mock_config)
        order = service.place_option_order("AAPL240119P00150000", "sell", 1)

        assert order["id"] == "order1"

        # Verify the order placement call uses /v2/orders endpoint
        call_args = mock_request.call_args
        assert call_args[1]["url"].endswith("/v2/orders")
        assert call_args[1]["json"]["symbol"] == "AAPL240119P00150000"
        assert call_args[1]["json"]["side"] == "sell"


def test_api_error_handling(mock_config, mock_response, mock_trading_client, caplog):
    """Test API error handling"""
    caplog.set_level(logging.ERROR)
    error_text = "Bad Request"

    with (
        patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client),
        patch("requests.request", return_value=mock_response(status_code=400, text=error_text)),
    ):
        service = AlpacaService(mock_config)
        # Test with a method that uses _make_request
        result = service.get_option_positions()
        assert result == []
        assert "API error: 400" in caplog.text


def test_request_error_handling(mock_config, mock_trading_client, caplog):
    """Test request error handling"""
    caplog.set_level(logging.ERROR)
    error_msg = "Network error"

    with (
        patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client),
        patch("requests.request", side_effect=Exception(error_msg)),
    ):
        service = AlpacaService(mock_config)
        result = service.get_option_positions()
        assert result == []
        assert "Request error" in caplog.text


def test_get_option_positions(mock_config, mock_response, mock_trading_client):
    """Test getting option positions"""
    mock_data = [{"id": "pos1", "symbol": "AAPL240119P00150000", "quantity": 1}]

    with (
        patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client),
        patch("requests.request", return_value=mock_response(json_data=mock_data)),
    ):
        service = AlpacaService(mock_config)
        positions = service.get_option_positions()

        assert len(positions) == 1
        assert positions[0]["id"] == "pos1"


def test_exercise_option(mock_config, mock_response, mock_trading_client):
    """Test exercising an option"""
    with (
        patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client),
        patch("requests.request", return_value=mock_response()),
    ):
        service = AlpacaService(mock_config)
        result = service.exercise_option("pos1")

        assert result is True


def test_get_account_history(mock_config, mock_response, mock_trading_client):
    """Test getting account history"""
    mock_data = [{"id": "activity1", "activity_type": "FILL", "date": "2024-01-01T10:00:00Z"}]

    with (
        patch("src.services.alpaca_service.TradingClient", return_value=mock_trading_client),
        patch("requests.request", return_value=mock_response(json_data=mock_data)),
    ):
        service = AlpacaService(mock_config)
        history = service.get_account_history(start=datetime.now() - timedelta(days=7), end=datetime.now())

        assert len(history) == 1
        assert history[0]["id"] == "activity1"
