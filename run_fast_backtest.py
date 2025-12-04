#!/usr/bin/env python3
"""
FAST Comprehensive Wheel Strategy Backtester
Caches price data first, then runs backtests in memory.
Total runtime: ~5-10 minutes instead of hours.
"""

import os
import sys
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv
import pandas as pd
from scipy.stats import norm
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pandas_market_calendars as mcal

# ============================================================================
# CONFIGURATION
# ============================================================================

WHEEL_CANDIDATES = [
    ("PLTR", 0.70, "Palantir - High IV tech ~$70"),
    ("SOFI", 0.15, "SoFi - Fintech ~$15"),
    ("F", 0.15, "Ford - Auto ~$11"),
    ("INTC", 0.25, "Intel - Semis ~$24"),
    ("BAC", 0.45, "Bank of America ~$47"),
    ("AAL", 0.20, "American Airlines ~$17"),
    ("HOOD", 0.40, "Robinhood ~$40"),
]

DELTA_CONFIGS = [
    ("Ultra Conservative", 0.10, 0.20),
    ("Conservative", 0.20, 0.30),
    ("Moderate", 0.25, 0.35),
    ("Aggressive", 0.30, 0.40),
]

RSI_THRESHOLDS = [25, 30, 35, 40, 45]

BACKTEST_PERIODS = [
    ("2023", "2023-01-01", "2024-01-01"),
    ("2024", "2024-01-01", "2024-12-01"),
]

INITIAL_CAPITAL = 10000

# ============================================================================
# PRICE DATA CACHE
# ============================================================================

class PriceCache:
    """Cache all price data upfront"""
    
    def __init__(self):
        api_key = os.getenv('ALPACA_PAPER_API_KEY')
        api_secret = os.getenv('ALPACA_PAPER_API_SECRET')
        self.client = StockHistoricalDataClient(api_key, api_secret)
        self.cache: Dict[str, pd.DataFrame] = {}
        self.calendar = mcal.get_calendar('NYSE')
        
    def load_all_data(self, symbols: List[str], start: datetime, end: datetime):
        """Load all price data for all symbols at once"""
        print(f"\n📥 Loading price data for {len(symbols)} symbols...")
        
        for symbol in symbols:
            print(f"   Fetching {symbol}...", end=" ", flush=True)
            try:
                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Day,
                    start=start - timedelta(days=60),  # Extra for RSI calc
                    end=end
                )
                bars = self.client.get_stock_bars(request)
                
                if bars and hasattr(bars, 'df') and not bars.df.empty:
                    df = bars.df.reset_index()
                    if 'symbol' in df.columns:
                        df = df[df['symbol'] == symbol]
                    df['date'] = pd.to_datetime(df['timestamp']).dt.date
                    self.cache[symbol] = df
                    print(f"✓ ({len(df)} days)")
                else:
                    print("✗ No data")
            except Exception as e:
                print(f"✗ Error: {e}")
                
        print(f"   Loaded {len(self.cache)} symbols\n")
        
    def get_price(self, symbol: str, date: datetime) -> Optional[float]:
        """Get closing price for a date"""
        if symbol not in self.cache:
            return None
        df = self.cache[symbol]
        mask = df['date'] == date.date()
        if mask.any():
            return float(df[mask]['close'].iloc[0])
        return None
    
    def get_rsi(self, symbol: str, date: datetime, period: int = 14) -> Optional[float]:
        """Calculate RSI for a date"""
        if symbol not in self.cache:
            return None
        df = self.cache[symbol]
        df = df[df['date'] <= date.date()].tail(period + 10)
        
        if len(df) < period + 1:
            return None
            
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss.replace(0, 0.0001)
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

    def get_trading_days(self, start: datetime, end: datetime) -> List[datetime]:
        """Get list of trading days"""
        schedule = self.calendar.schedule(start_date=start, end_date=end)
        return [datetime.combine(d.date(), datetime.min.time()) for d in schedule.index]

# ============================================================================
# OPTION SIMULATOR
# ============================================================================

def calculate_delta(price: float, strike: float, dte: int, is_put: bool, iv: float = 0.35) -> float:
    """Calculate option delta using Black-Scholes"""
    T = max(1, dte) / 365.0
    r = 0.05
    
    if T <= 0 or price <= 0 or strike <= 0:
        return 0
        
    d1 = (math.log(price / strike) + (r + 0.5 * iv ** 2) * T) / (iv * math.sqrt(T))
    
    if is_put:
        return norm.cdf(d1) - 1
    return norm.cdf(d1)


def calculate_premium(price: float, strike: float, dte: int, is_put: bool, iv: float = 0.35) -> float:
    """Calculate option premium using Black-Scholes"""
    T = max(1, dte) / 365.0
    r = 0.05
    
    if T <= 0 or price <= 0 or strike <= 0:
        return 0.01
        
    d1 = (math.log(price / strike) + (r + 0.5 * iv ** 2) * T) / (iv * math.sqrt(T))
    d2 = d1 - iv * math.sqrt(T)
    
    if is_put:
        premium = strike * math.exp(-r * T) * norm.cdf(-d2) - price * norm.cdf(-d1)
    else:
        premium = price * norm.cdf(d1) - strike * math.exp(-r * T) * norm.cdf(d2)
        
    return max(0.01, premium)


def find_put_by_delta(price: float, dte: int, min_delta: float, max_delta: float, iv: float = 0.35) -> Optional[Dict]:
    """Find a put option within delta range"""
    # Generate strikes from -30% to -5% OTM
    for pct in range(-30, -4, 1):
        strike = round(price * (1 + pct/100), 2)
        delta = abs(calculate_delta(price, strike, dte, True, iv))
        
        if min_delta <= delta <= max_delta:
            premium = calculate_premium(price, strike, dte, True, iv)
            return {
                'strike': strike,
                'premium': premium,
                'delta': delta,
                'dte': dte
            }
    return None


def find_call_by_delta(price: float, cost_basis: float, dte: int, iv: float = 0.35) -> Optional[Dict]:
    """Find a covered call above cost basis"""
    # Generate strikes from +2% to +15% OTM
    for pct in range(2, 16, 1):
        strike = round(price * (1 + pct/100), 2)
        
        if strike < cost_basis:
            continue
            
        premium = calculate_premium(price, strike, dte, False, iv)
        delta = calculate_delta(price, strike, dte, False, iv)
        
        if premium > 0.10:  # Minimum premium
            return {
                'strike': strike,
                'premium': premium,
                'delta': delta,
                'dte': dte
            }
    return None

# ============================================================================
# FAST BACKTESTER
# ============================================================================

@dataclass
class Position:
    symbol: str
    position_type: str  # 'CSP', 'STOCK', 'CC'
    strike: float = 0
    expiration: datetime = None
    premium: float = 0
    shares: int = 0
    cost_basis: float = 0


@dataclass
class BacktestResult:
    period: str
    delta_config: str
    rsi_threshold: int
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    final_value: float
    premium_collected: float = 0
    assignments: int = 0


class FastBacktester:
    def __init__(self, cache: PriceCache, capital: float, 
                 min_delta: float, max_delta: float, rsi_threshold: int):
        self.cache = cache
        self.initial_capital = capital
        self.capital = capital
        self.min_delta = min_delta
        self.max_delta = max_delta
        self.rsi_threshold = rsi_threshold
        
        self.positions: List[Position] = []
        self.trades: List[Dict] = []
        self.daily_values: List[float] = []
        self.premium_collected = 0
        self.assignments = 0
        
    def run(self, symbols: List[Tuple[str, float]], start: datetime, end: datetime) -> BacktestResult:
        """Run backtest"""
        trading_days = self.cache.get_trading_days(start, end)
        
        for day in trading_days:
            self._process_day(day, symbols)
            self._record_value(day)
            
        return self._generate_results(start, end)
    
    def _process_day(self, date: datetime, symbols: List[Tuple[str, float]]):
        """Process a single trading day"""
        # Handle expirations
        for pos in self.positions[:]:
            if pos.position_type == 'CSP' and pos.expiration and date >= pos.expiration:
                self._handle_csp_expiration(date, pos)
            elif pos.position_type == 'CC' and pos.expiration and date >= pos.expiration:
                self._handle_cc_expiration(date, pos)
        
        # Sell covered calls on stock
        for pos in self.positions[:]:
            if pos.position_type == 'STOCK':
                self._try_sell_cc(date, pos)
        
        # Look for new CSP entries
        for symbol, max_pos_size in symbols:
            if self._has_position(symbol):
                continue
                
            price = self.cache.get_price(symbol, date)
            rsi = self.cache.get_rsi(symbol, date)
            
            if price is None or rsi is None:
                continue
                
            # Check RSI condition
            if rsi > self.rsi_threshold:
                continue
                
            # Check capital
            max_capital = self.initial_capital * max_pos_size
            if price * 100 > max_capital:
                continue
                
            # Find put option
            put = find_put_by_delta(price, 30, self.min_delta, self.max_delta)
            if put:
                self._sell_csp(date, symbol, put)
    
    def _has_position(self, symbol: str) -> bool:
        return any(p.symbol == symbol for p in self.positions)
    
    def _sell_csp(self, date: datetime, symbol: str, put: Dict):
        """Sell a cash-secured put"""
        premium = put['premium'] * 100  # Per contract
        self.capital += premium
        self.premium_collected += premium
        
        pos = Position(
            symbol=symbol,
            position_type='CSP',
            strike=put['strike'],
            expiration=date + timedelta(days=put['dte']),
            premium=put['premium']
        )
        self.positions.append(pos)
        self.trades.append({'date': date, 'action': 'SELL_CSP', 'symbol': symbol})
    
    def _handle_csp_expiration(self, date: datetime, pos: Position):
        """Handle CSP expiration"""
        price = self.cache.get_price(pos.symbol, date)
        if price is None:
            price = pos.strike  # Fallback
            
        if price < pos.strike:
            # Assigned - buy stock
            cost = pos.strike * 100
            self.capital -= cost
            self.assignments += 1
            
            stock_pos = Position(
                symbol=pos.symbol,
                position_type='STOCK',
                shares=100,
                cost_basis=pos.strike - pos.premium  # Adjusted cost basis
            )
            self.positions.remove(pos)
            self.positions.append(stock_pos)
            self.trades.append({'date': date, 'action': 'ASSIGNED', 'symbol': pos.symbol})
        else:
            # Expired worthless - keep premium
            self.positions.remove(pos)
            self.trades.append({'date': date, 'action': 'EXPIRED', 'symbol': pos.symbol})
    
    def _try_sell_cc(self, date: datetime, pos: Position):
        """Try to sell covered call on stock position"""
        # Check if already have a CC
        if any(p.symbol == pos.symbol and p.position_type == 'CC' for p in self.positions):
            return
            
        price = self.cache.get_price(pos.symbol, date)
        if price is None:
            return
            
        call = find_call_by_delta(price, pos.cost_basis, 30)
        if call:
            premium = call['premium'] * 100
            self.capital += premium
            self.premium_collected += premium
            
            cc_pos = Position(
                symbol=pos.symbol,
                position_type='CC',
                strike=call['strike'],
                expiration=date + timedelta(days=call['dte']),
                premium=call['premium']
            )
            self.positions.append(cc_pos)
            self.trades.append({'date': date, 'action': 'SELL_CC', 'symbol': pos.symbol})
    
    def _handle_cc_expiration(self, date: datetime, pos: Position):
        """Handle covered call expiration"""
        price = self.cache.get_price(pos.symbol, date)
        if price is None:
            price = pos.strike
            
        if price > pos.strike:
            # Called away - sell stock
            revenue = pos.strike * 100
            self.capital += revenue
            
            # Remove CC and stock positions
            stock_pos = next((p for p in self.positions 
                            if p.symbol == pos.symbol and p.position_type == 'STOCK'), None)
            if stock_pos:
                self.positions.remove(stock_pos)
            self.positions.remove(pos)
            self.trades.append({'date': date, 'action': 'CALLED_AWAY', 'symbol': pos.symbol})
        else:
            # Expired - keep shares and premium
            self.positions.remove(pos)
            self.trades.append({'date': date, 'action': 'CC_EXPIRED', 'symbol': pos.symbol})
    
    def _record_value(self, date: datetime):
        """Record portfolio value"""
        value = self.capital
        
        for pos in self.positions:
            if pos.position_type == 'STOCK':
                price = self.cache.get_price(pos.symbol, date)
                if price:
                    value += price * pos.shares
                    
        self.daily_values.append(value)
    
    def _generate_results(self, start: datetime, end: datetime) -> BacktestResult:
        """Generate backtest results"""
        if not self.daily_values:
            return BacktestResult("", "", 0, 0, 0, 0, 0, 0, 0, self.initial_capital)
            
        final_value = self.daily_values[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        days = (end - start).days
        annual_return = (1 + total_return) ** (365 / max(1, days)) - 1
        
        # Calculate Sharpe
        returns = pd.Series(self.daily_values).pct_change().dropna()
        if len(returns) > 0 and returns.std() > 0:
            sharpe = (returns.mean() * 252) / (returns.std() * math.sqrt(252))
        else:
            sharpe = 0
            
        # Calculate max drawdown
        peak = pd.Series(self.daily_values).cummax()
        drawdown = (pd.Series(self.daily_values) - peak) / peak
        max_dd = drawdown.min()
        
        # Win rate (expired without assignment = win)
        wins = len([t for t in self.trades if t['action'] in ['EXPIRED', 'CC_EXPIRED', 'CALLED_AWAY']])
        total_closed = len([t for t in self.trades if t['action'] in ['EXPIRED', 'CC_EXPIRED', 'CALLED_AWAY', 'ASSIGNED']])
        win_rate = wins / max(1, total_closed)
        
        return BacktestResult(
            period="",
            delta_config="",
            rsi_threshold=self.rsi_threshold,
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            total_trades=len(self.trades),
            final_value=final_value,
            premium_collected=self.premium_collected,
            assignments=self.assignments
        )


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*70)
    print("🚀 FAST WHEEL STRATEGY COMPREHENSIVE BACKTEST")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,}")
    print(f"Symbols: {', '.join([s[0] for s in WHEEL_CANDIDATES])}")
    
    # Load all price data once
    cache = PriceCache()
    symbols = [s[0] for s in WHEEL_CANDIDATES]
    
    # Get full date range
    all_starts = [datetime.strptime(p[1], "%Y-%m-%d") for p in BACKTEST_PERIODS]
    all_ends = [datetime.strptime(p[2], "%Y-%m-%d") for p in BACKTEST_PERIODS]
    cache.load_all_data(symbols, min(all_starts), max(all_ends))
    
    # Run all backtests
    results: List[BacktestResult] = []
    total_tests = len(BACKTEST_PERIODS) * len(DELTA_CONFIGS) * len(RSI_THRESHOLDS)
    current = 0
    
    print(f"Running {total_tests} backtest configurations...\n")
    
    for period_name, start_str, end_str in BACKTEST_PERIODS:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
        
        for delta_name, min_d, max_d in DELTA_CONFIGS:
            for rsi in RSI_THRESHOLDS:
                current += 1
                
                bt = FastBacktester(cache, INITIAL_CAPITAL, min_d, max_d, rsi)
                symbol_configs = [(s[0], s[1]) for s in WHEEL_CANDIDATES]
                result = bt.run(symbol_configs, start, end)
                
                result.period = period_name
                result.delta_config = delta_name
                result.rsi_threshold = rsi
                
                results.append(result)
                
                print(f"[{current}/{total_tests}] {period_name} | {delta_name} | RSI={rsi} → "
                      f"Return: {result.total_return:+.1%}, Trades: {result.total_trades}, "
                      f"Premium: ${result.premium_collected:.0f}")
    
    # Analyze results
    analyze_results(results)
    
    print(f"\n✅ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def analyze_results(results: List[BacktestResult]):
    """Analyze and display results"""
    df = pd.DataFrame([vars(r) for r in results])
    
    print(f"\n{'='*70}")
    print("📊 RESULTS ANALYSIS")
    print(f"{'='*70}")
    
    # Top 10 by return
    print("\n🏆 TOP 10 CONFIGURATIONS BY TOTAL RETURN:")
    print("-" * 65)
    top = df.nlargest(10, 'total_return')[
        ['period', 'delta_config', 'rsi_threshold', 'total_return', 
         'sharpe_ratio', 'max_drawdown', 'premium_collected', 'assignments']
    ]
    for _, row in top.iterrows():
        print(f"  {row['period']:10} | {row['delta_config']:18} | RSI={row['rsi_threshold']:2} | "
              f"Return: {row['total_return']:+6.1%} | Sharpe: {row['sharpe_ratio']:5.2f} | "
              f"DD: {row['max_drawdown']:6.1%} | Premium: ${row['premium_collected']:,.0f}")
    
    # By Delta
    print("\n\n📈 AVERAGE PERFORMANCE BY DELTA RANGE:")
    print("-" * 50)
    delta_avg = df.groupby('delta_config').agg({
        'total_return': 'mean',
        'sharpe_ratio': 'mean',
        'max_drawdown': 'mean',
        'premium_collected': 'mean',
        'assignments': 'mean'
    })
    for name, row in delta_avg.iterrows():
        print(f"  {name:18} | Return: {row['total_return']:+5.1%} | "
              f"Sharpe: {row['sharpe_ratio']:5.2f} | DD: {row['max_drawdown']:5.1%} | "
              f"Avg Premium: ${row['premium_collected']:,.0f}")
    
    # By RSI
    print("\n\n📊 AVERAGE PERFORMANCE BY RSI THRESHOLD:")
    print("-" * 50)
    rsi_avg = df.groupby('rsi_threshold').agg({
        'total_return': 'mean',
        'sharpe_ratio': 'mean',
        'total_trades': 'mean',
        'premium_collected': 'mean'
    })
    for rsi, row in rsi_avg.iterrows():
        print(f"  RSI={rsi:2} | Return: {row['total_return']:+5.1%} | "
              f"Sharpe: {row['sharpe_ratio']:5.2f} | Trades: {row['total_trades']:4.0f} | "
              f"Premium: ${row['premium_collected']:,.0f}")
    
    # By Period
    print("\n\n📅 AVERAGE PERFORMANCE BY PERIOD:")
    print("-" * 50)
    period_avg = df.groupby('period').agg({
        'total_return': 'mean',
        'sharpe_ratio': 'mean',
        'max_drawdown': 'mean',
        'assignments': 'mean'
    })
    for period, row in period_avg.iterrows():
        print(f"  {period:10} | Return: {row['total_return']:+5.1%} | "
              f"Sharpe: {row['sharpe_ratio']:5.2f} | DD: {row['max_drawdown']:5.1%} | "
              f"Avg Assignments: {row['assignments']:.1f}")
    
    # Conclusions
    best_delta = df.groupby('delta_config')['total_return'].mean().idxmax()
    best_rsi = df.groupby('rsi_threshold')['total_return'].mean().idxmax()
    best_overall = df.loc[df['total_return'].idxmax()]
    best_sharpe = df.loc[df['sharpe_ratio'].idxmax()]
    
    print(f"\n{'='*70}")
    print("💡 CONCLUSIONS & RECOMMENDATIONS")
    print(f"{'='*70}")
    
    print(f"""
🏆 BEST OVERALL CONFIGURATION:
   Period: {best_overall['period']}
   Delta: {best_overall['delta_config']}
   RSI Threshold: {best_overall['rsi_threshold']}
   → Return: {best_overall['total_return']:+.1%}
   → Premium Collected: ${best_overall['premium_collected']:,.0f}
   → Assignments: {best_overall['assignments']}

📊 OPTIMAL SETTINGS (averaged across all periods):
   • Best Delta Range: {best_delta}
   • Best RSI Threshold: {best_rsi}

⚖️ BEST RISK-ADJUSTED (Sharpe):
   Delta: {best_sharpe['delta_config']}, RSI={best_sharpe['rsi_threshold']}
   → Sharpe: {best_sharpe['sharpe_ratio']:.2f}
   → Return: {best_sharpe['total_return']:+.1%}

💡 KEY INSIGHTS:
""")
    
    # Delta insight
    delta_returns = df.groupby('delta_config')['total_return'].mean()
    if delta_returns['Aggressive'] > delta_returns['Conservative']:
        print("   • Higher delta (Aggressive/Moderate) outperforms - extra premium")
        print("     compensates for assignment risk in these market conditions.")
    else:
        print("   • Lower delta (Conservative) provides better protection against")
        print("     assignments during volatile periods.")
    
    # RSI insight
    rsi_returns = df.groupby('rsi_threshold')['total_return'].mean()
    if best_rsi >= 40:
        print(f"   • RSI threshold of {best_rsi} allows more frequent entries,")
        print("     capturing more premium in trending/sideways markets.")
    else:
        print(f"   • RSI threshold of {best_rsi} is selective, entering only")
        print("     on oversold conditions for better entry prices.")
    
    # Assignment insight
    avg_assignments = df['assignments'].mean()
    print(f"   • Average assignments per test: {avg_assignments:.1f}")
    print("     (Assignments aren't bad - they're part of the wheel cycle!)")
    
    print(f"""
{'='*70}
📋 RECOMMENDED CONFIG FOR $10K ACCOUNT:
{'='*70}

watchlist:
  - symbol: PLTR
    max_position_size: 0.70
    min_strike_delta: {0.25 if 'Conservative' in best_delta else 0.30}
    max_strike_delta: {0.35 if 'Conservative' in best_delta else 0.40}
    
  - symbol: SOFI
    max_position_size: 0.15
    min_strike_delta: {0.25 if 'Conservative' in best_delta else 0.30}
    max_strike_delta: {0.35 if 'Conservative' in best_delta else 0.40}
    
  - symbol: F
    max_position_size: 0.15
    min_strike_delta: {0.25 if 'Conservative' in best_delta else 0.30}
    max_strike_delta: {0.35 if 'Conservative' in best_delta else 0.40}

RSI Threshold: {best_rsi}

⚠️  CAVEATS:
   • Backtests use synthetic option pricing (Black-Scholes)
   • Real fills may differ due to liquidity/spreads
   • Past performance ≠ future results
   • Paper trade before going live!
""")
    
    # Save to CSV
    filename = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False)
    print(f"\n📁 Results saved to: {filename}")


if __name__ == "__main__":
    main()

