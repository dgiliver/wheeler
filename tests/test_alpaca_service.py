import logging
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import requests

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
def alpaca_service(mock_config, mock_response):
    """Create AlpacaService instance with mock config"""
    with patch("requests.request", return_value=mock_response(json_data={})):
        return AlpacaService(mock_config)


def test_get_account(alpaca_service, mock_response):
    """Test getting account information"""
    mock_data = {"id": "test_account", "cash": "100000", "portfolio_value": "150000"}

    with patch("requests.request", return_value=mock_response(json_data=mock_data)):
        account = alpaca_service.get_account()
        assert account == mock_data


def test_get_positions(alpaca_service, mock_response):
    """Test getting all positions"""
    mock_data = [{"symbol": "AAPL", "avg_entry_price": "150.00", "qty": "100", "created_at": "2024-01-01T10:00:00Z"}]

    with patch("requests.request", return_value=mock_response(json_data=mock_data)):
        positions = alpaca_service.get_positions()
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


def test_get_option_chain(alpaca_service, mock_response, caplog):
    """Test getting option chain"""
    caplog.set_level(logging.DEBUG)

    # Mock response for options snapshot
    mock_data = {
        "AAPL240119P00150000": {
            "latest_quote": {"bid_price": 1.00, "ask_price": 1.10, "trade_volume": 100},
            "greeks": {"implied_volatility": 0.3, "delta": -0.3},
            "open_interest": 500,
        }
    }

    with patch("requests.request", return_value=mock_response(json_data=mock_data)):
        # Use datetime that matches the contract symbol (2024-01-19)
        expiry = datetime(2024, 1, 19)
        chain = alpaca_service.get_option_chain("AAPL", expiry)
        assert len(chain) == 1
        assert chain[0]["bid"] == 1.00
        assert chain[0]["ask"] == 1.10


def test_place_option_order(alpaca_service, mock_response):
    """Test placing an option order"""
    mock_data = {"id": "order1", "status": "accepted"}

    with patch("requests.request", return_value=mock_response(json_data=mock_data)):
        order = alpaca_service.place_option_order("contract1", "buy", 1)
        assert order["id"] == "order1"

        # Verify the order placement call
        requests.request.assert_called_once_with(
            method="POST",
            url=f"{alpaca_service.trading_url}/v2/options/orders",
            headers=alpaca_service.headers,
            params=None,
            json={"contract_id": "contract1", "side": "buy", "type": "limit", "time_in_force": "gtc", "qty": 1},
        )


def test_api_error_handling(alpaca_service, mock_response, caplog):
    """Test API error handling"""
    caplog.set_level(logging.ERROR)
    error_text = "Bad Request"

    with patch("requests.request", return_value=mock_response(status_code=400, text=error_text)):
        result = alpaca_service.get_account()
        assert result is None
        assert f"API error: 400 - {error_text}" in caplog.text


def test_request_error_handling(alpaca_service, caplog):
    """Test request error handling"""
    caplog.set_level(logging.ERROR)
    error_msg = "Network error"

    with patch("requests.request", side_effect=Exception(error_msg)):
        result = alpaca_service.get_account()
        assert result is None
        assert f"Request error: {error_msg}" in caplog.text


def test_get_option_positions(mock_config, mock_response):
    """Test getting option positions"""
    mock_data = [{"id": "pos1", "symbol": "AAPL240119P00150000", "quantity": 1}]

    with patch("requests.request", return_value=mock_response(json_data=mock_data)):
        service = AlpacaService(mock_config)
        positions = service.get_option_positions()

        assert len(positions) == 1
        assert positions[0]["id"] == "pos1"


def test_exercise_option(mock_config, mock_response):
    """Test exercising an option"""
    with patch("requests.request", return_value=mock_response()):
        service = AlpacaService(mock_config)
        result = service.exercise_option("pos1")

        assert result is True


def test_get_account_history(mock_config, mock_response):
    """Test getting account history"""
    mock_data = [{"id": "activity1", "activity_type": "FILL", "date": "2024-01-01T10:00:00Z"}]

    with patch("requests.request", return_value=mock_response(json_data=mock_data)):
        service = AlpacaService(mock_config)
        history = service.get_account_history(start=datetime.now() - timedelta(days=7), end=datetime.now())

        assert len(history) == 1
        assert history[0]["id"] == "activity1"
