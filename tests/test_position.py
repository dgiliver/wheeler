from datetime import datetime
from decimal import Decimal

from src.models.position import Position, PositionType


def test_position_total_cost_stock():
    """Test total cost calculation for stock position"""
    position = Position(symbol="AAPL", entry_price=Decimal("150"), quantity=100, position_type=PositionType.STOCK)
    assert position.total_cost == Decimal("15000")


def test_position_total_cost_options():
    """Test total cost calculation for option position with multiple contracts"""
    position = Position(
        symbol="AAPL",
        entry_price=Decimal("1.50"),
        quantity=200,  # 2 contracts * 100 shares
        position_type=PositionType.CASH_SECURED_PUT,
        strike_price=Decimal("145"),
        contracts=2,
    )
    # Cost should be strike price * 100 shares * number of contracts
    assert position.total_cost == Decimal("29000")  # 145 * 100 * 2


def test_position_initialization_defaults():
    """Test position initialization with default values"""
    position = Position(symbol="AAPL", entry_price=Decimal("150"), quantity=100, position_type=PositionType.STOCK)
    assert position.premium_received == Decimal("0")
    assert position.contracts == 1
    assert isinstance(position.entry_date, datetime)


def test_position_with_multiple_contracts():
    """Test position with multiple contracts"""
    position = Position(
        symbol="AAPL",
        entry_price=Decimal("1.50"),
        quantity=300,  # 3 contracts * 100 shares
        position_type=PositionType.CASH_SECURED_PUT,
        strike_price=Decimal("145"),
        contracts=3,
        premium_received=Decimal("450"),  # $1.50 premium * 300 shares
    )
    assert position.contracts == 3
    assert position.premium_received == Decimal("450")
