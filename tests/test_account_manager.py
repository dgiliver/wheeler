import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from src.managers.account_manager import AccountManager
from src.models.position import Position, PositionType

@pytest.fixture
def account_manager():
    return AccountManager(total_balance=Decimal("100000"), max_position_size=0.2)

def test_can_open_position_new(account_manager):
    """Test opening a new position"""
    # 20% of 100k = 20k max position size
    assert account_manager.can_open_position(Decimal("19000")) == True
    assert account_manager.can_open_position(Decimal("21000")) == False

def test_can_open_position_existing(account_manager):
    """Test adding to existing position"""
    # Add existing position
    account_manager.positions.append(
        Position(
            symbol="AAPL",
            entry_price=Decimal("150"),
            quantity=100,
            position_type=PositionType.STOCK
        )
    )
    
    # Try to add more to AAPL position
    # Current position cost = 15000, max = 20000
    assert account_manager.can_open_position(Decimal("4000"), "AAPL") == True
    assert account_manager.can_open_position(Decimal("6000"), "AAPL") == False

def test_get_max_contracts_new_position(account_manager):
    """Test calculating max contracts for new position"""
    # Max position size = 20k
    # Contract cost = 150 strike * 100 shares = 15k
    max_contracts = account_manager.get_max_contracts(strike_price=Decimal("150"))
    assert max_contracts == 1  # Can only afford 1 contract

def test_get_max_contracts_existing_position(account_manager):
    """Test calculating max contracts with existing position"""
    # Add existing position costing 15k
    account_manager.positions.append(
        Position(
            symbol="AAPL",
            entry_price=Decimal("150"),
            quantity=100,
            position_type=PositionType.STOCK
        )
    )
    
    # Try to add contracts to AAPL
    # Remaining position size = 20k - 15k = 5k
    max_contracts = account_manager.get_max_contracts(
        strike_price=Decimal("150"),
        existing_symbol="AAPL"
    )
    assert max_contracts == 0  # Can't afford any more contracts at this strike

def test_get_max_contracts_different_symbol(account_manager):
    """Test max contracts for different symbol with existing position"""
    # Add AAPL position
    account_manager.positions.append(
        Position(
            symbol="AAPL",
            entry_price=Decimal("150"),
            quantity=100,
            position_type=PositionType.STOCK
        )
    )
    
    # Try to open AMD position
    # Each symbol gets its own 20k allocation
    max_contracts = account_manager.get_max_contracts(
        strike_price=Decimal("100"),
        existing_symbol="AMD"
    )
    assert max_contracts == 2  # Can afford 2 contracts at $100 strike

def test_day_trade_tracking():
    """Test PDT tracking with account equity and day trade count"""
    # Account under $25k threshold - PDT rules apply
    account = AccountManager(total_balance=Decimal('20000'))
    
    # Simulate PDT status from Alpaca
    account.update_pdt_status(
        equity=Decimal('20000'),
        daytrade_count=2,
        is_pattern_day_trader=False
    )
    
    # 2 day trades used, 1 remaining - should be allowed
    can_trade, _ = account.can_day_trade()
    assert can_trade == True
    assert account.would_exceed_day_trades() == False
    
    # Update to 3 day trades - should be blocked
    account.update_pdt_status(
        equity=Decimal('20000'),
        daytrade_count=3,
        is_pattern_day_trader=False
    )
    
    can_trade, reason = account.can_day_trade()
    assert can_trade == False
    assert "PDT limit reached" in reason
    assert account.would_exceed_day_trades() == True


def test_pdt_not_restricted_above_threshold():
    """Test that accounts above $25k are not PDT restricted"""
    account = AccountManager(total_balance=Decimal('50000'))
    
    # Even with 3 day trades, should be allowed above threshold
    account.update_pdt_status(
        equity=Decimal('50000'),
        daytrade_count=3,
        is_pattern_day_trader=False
    )
    
    can_trade, reason = account.can_day_trade()
    assert can_trade == True
    assert "not subject to PDT" in reason
    assert account.would_exceed_day_trades() == False

def test_cost_basis_calculation():
    account = AccountManager(total_balance=Decimal('100000'))
    
    # Add a stock position and some options premiums
    stock_position = Position(
        symbol="AAPL",
        entry_price=Decimal('150'),
        quantity=100,
        position_type=PositionType.STOCK,
        expiration=None,
        strike_price=None,
        premium_received=Decimal('0'),
        entry_date=datetime.now()
    )
    
    csp_position = Position(
        symbol="AAPL",
        entry_price=Decimal('0'),
        quantity=1,
        position_type=PositionType.CASH_SECURED_PUT,
        expiration=datetime.now(),
        strike_price=Decimal('145'),
        premium_received=Decimal('500'),
        entry_date=datetime.now()
    )
    
    account.positions.extend([stock_position, csp_position])
    
    # Cost basis should be: (150 * 100) - 500 = 14500
    assert account.get_position_cost_basis("AAPL") == Decimal('14500') 