import pytest
import pandas as pd
from decimal import Decimal
from datetime import datetime, timedelta
from src.analysis.strategy_analyzer import StrategyAnalyzer
from src.models.position import Position, PositionType, OptionQuote

@pytest.fixture
def analyzer():
    return StrategyAnalyzer(
        max_spread_percentage=15.0,
        min_volume=50,
        min_open_interest=100
    )

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

def test_csp_entry_conditions(analyzer, liquid_option):
    # Create mock price data with oversold RSI
    price_data = pd.DataFrame({
        'close': [100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30]
    })
    
    should_enter, reason = analyzer.should_enter_csp(price_data, liquid_option)
    assert should_enter == True
    assert "RSI oversold" in reason

def test_roll_options_decision(analyzer, liquid_option):
    # Test put roll conditions with expiry > 5 days
    should_roll, reason = analyzer.should_roll_option(
        days_to_expiry=10,  # Changed from 3 to 10 to avoid near expiry check
        current_strike=Decimal('100'),
        current_price=Decimal('95'),
        is_put=True,
        option_quote=liquid_option
    )
    assert should_roll == True
    assert "Put at risk" in reason

def test_assignment_decision():
    analyzer = StrategyAnalyzer()
    
    # Test assignment acceptance with high IV
    should_accept, reason = analyzer.accept_assignment(
        cost_basis=Decimal('100'),
        current_price=Decimal('95'),
        implied_volatility=60
    )
    assert should_accept == True
    assert "High IV" in reason

def test_should_force_exit_on_loss(analyzer):
    position = Position(
        symbol="AAPL",
        entry_price=Decimal("150"),
        quantity=100,
        position_type=PositionType.STOCK,
        expiration=None,
        strike_price=None,
        premium_received=Decimal("0"),
        entry_date=datetime.now(),
        max_loss=Decimal("3750")  # 25% of position value
    )
    
    # Test with significant loss
    should_exit, reason = analyzer.should_force_exit(
        position=position,
        current_price=Decimal("110")  # Significant drop
    )
    assert should_exit == True
    assert "Loss threshold exceeded" in reason

def test_should_force_exit_on_wide_spread(analyzer, illiquid_option):
    position = Position(
        symbol="AAPL",
        entry_price=Decimal("3.00"),
        quantity=1,
        position_type=PositionType.CASH_SECURED_PUT,
        expiration=datetime.now() + timedelta(days=30),
        strike_price=Decimal("150"),
        premium_received=Decimal("300"),
        entry_date=datetime.now(),
        max_loss=Decimal("750")  # Add max loss threshold
    )
    
    should_exit, reason = analyzer.should_force_exit(
        position=position,
        current_price=Decimal("2.80"),
        option_quote=illiquid_option
    )
    assert should_exit == True
    assert "Spread too wide" in reason

def test_optimal_exit_price(analyzer, liquid_option, illiquid_option):
    # Test with liquid option
    optimal_price = analyzer.get_optimal_exit_price(
        liquid_option,
        Position(
            symbol="AAPL",
            entry_price=Decimal("1.05"),
            quantity=1,
            position_type=PositionType.COVERED_CALL,
            expiration=datetime.now() + timedelta(days=30),
            strike_price=Decimal("150"),
            premium_received=Decimal("105"),
            entry_date=datetime.now()
        )
    )
    assert optimal_price == Decimal("1.05")  # Should be midpoint
    
    # Test with illiquid option
    optimal_price = analyzer.get_optimal_exit_price(
        illiquid_option,
        Position(
            symbol="AAPL",
            entry_price=Decimal("1.25"),
            quantity=1,
            position_type=PositionType.COVERED_CALL,
            expiration=datetime.now() + timedelta(days=30),
            strike_price=Decimal("150"),
            premium_received=Decimal("125"),
            entry_date=datetime.now()
        )
    )
    assert optimal_price == Decimal("1.00")  # Should use bid price for quick exit 

def test_should_roll_option_itm_put():
    """Test rolling decision for ITM put"""
    analyzer = StrategyAnalyzer()
    option_quote = OptionQuote(
        bid=Decimal("1.00"),
        ask=Decimal("1.10"),
        volume=1000,
        open_interest=5000,
        implied_volatility=30.0,
        delta=-0.7  # Deep ITM
    )
    
    should_roll, reason = analyzer.should_roll_option(
        days_to_expiry=10,  # Changed from 5 to 10 to avoid near expiry check
        current_strike=Decimal("150"),
        current_price=Decimal("140"),  # ITM put
        is_put=True,
        option_quote=option_quote
    )
    
    assert should_roll == True
    assert "Put at risk" in reason

def test_should_roll_option_near_expiry():
    """Test rolling decision for near expiry option"""
    analyzer = StrategyAnalyzer()
    option_quote = OptionQuote(
        bid=Decimal("1.00"),
        ask=Decimal("1.10"),
        volume=1000,
        open_interest=5000,
        implied_volatility=30.0,
        delta=-0.3
    )
    
    should_roll, reason = analyzer.should_roll_option(
        days_to_expiry=3,  # Very close to expiry
        current_strike=Decimal("150"),
        current_price=Decimal("155"),  # OTM put
        is_put=True,
        option_quote=option_quote
    )
    
    assert should_roll == True
    assert "Near expiry" in reason 

def test_csp_entry_illiquid_option(analyzer, illiquid_option):
    """Test CSP entry with illiquid option"""
    price_data = pd.DataFrame({
        'close': [100, 95, 90, 85, 80]
    })
    
    should_enter, reason = analyzer.should_enter_csp(price_data, illiquid_option)
    assert should_enter == False
    assert "Insufficient liquidity" in reason

def test_should_force_exit_no_max_loss():
    """Test force exit when no max loss is set"""
    analyzer = StrategyAnalyzer()
    position = Position(
        symbol="AAPL",
        entry_price=Decimal("150"),
        quantity=100,
        position_type=PositionType.STOCK,
        expiration=None,
        strike_price=None,
        premium_received=Decimal("0"),
        entry_date=datetime.now(),
        max_loss=None  # No max loss set
    )
    
    should_exit, reason = analyzer.should_force_exit(
        position=position,
        current_price=Decimal("140")
    )
    assert should_exit == False
    assert "No max loss set" in reason

def test_should_roll_option_call_itm():
    """Test rolling decision for ITM call"""
    analyzer = StrategyAnalyzer()
    option_quote = OptionQuote(
        bid=Decimal("1.00"),
        ask=Decimal("1.10"),
        volume=1000,
        open_interest=5000,
        implied_volatility=30.0,
        delta=0.7  # Deep ITM
    )
    
    should_roll, reason = analyzer.should_roll_option(
        days_to_expiry=10,
        current_strike=Decimal("140"),
        current_price=Decimal("150"),  # ITM call
        is_put=False,  # Testing call option
        option_quote=option_quote
    )
    
    assert should_roll == True
    assert "Call at risk" in reason

def test_should_roll_option_no_action_needed():
    """Test rolling decision when no action is needed"""
    analyzer = StrategyAnalyzer()
    option_quote = OptionQuote(
        bid=Decimal("1.00"),
        ask=Decimal("1.10"),
        volume=1000,
        open_interest=5000,
        implied_volatility=30.0,
        delta=0.3
    )
    
    should_roll, reason = analyzer.should_roll_option(
        days_to_expiry=20,  # Far from expiry
        current_strike=Decimal("150"),
        current_price=Decimal("160"),  # OTM put
        is_put=True,
        option_quote=option_quote
    )
    
    assert should_roll == False
    assert "No roll needed" in reason

def test_accept_assignment_avoid():
    """Test assignment decision when it should be avoided"""
    analyzer = StrategyAnalyzer()
    
    should_accept, reason = analyzer.accept_assignment(
        cost_basis=Decimal("100"),
        current_price=Decimal("85"),  # Significant drop
        implied_volatility=30.0  # Low IV
    )
    
    assert should_accept == False
    assert "Avoid assignment" in reason

def test_rsi_calculation_insufficient_data():
    """Test RSI calculation with insufficient data returns neutral default"""
    analyzer = StrategyAnalyzer()
    
    # Create price data with only a few points (less than 14+1 periods needed)
    price_data = pd.DataFrame({
        'close': [100, 95, 90]  # Less than 15 periods required
    })
    
    rsi = analyzer._calculate_rsi(price_data)
    # Implementation returns neutral RSI (50.0) when insufficient data
    assert rsi == 50.0 