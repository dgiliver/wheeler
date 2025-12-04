#!/usr/bin/env python3
"""
Comprehensive Wheel Strategy Backtester
Runs multiple backtests with varying deltas and RSI thresholds,
combines results, and provides analysis.
"""

import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv
import pandas as pd
from tabulate import tabulate

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.settings import AlpacaConfig, StockConfig
from src.backtesting.wheel_backtester import WheelBacktester

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# Good wheel candidates for $10k account (stocks $15-80)
WHEEL_CANDIDATES = [
    # Symbol, Max Position Size, Description
    ("PLTR", 0.70, "Palantir - High IV tech"),
    ("SOFI", 0.15, "SoFi - Fintech"),
    ("F", 0.15, "Ford - Auto"),
    ("INTC", 0.25, "Intel - Semiconductors"),
    ("BAC", 0.45, "Bank of America"),
    ("AAL", 0.20, "American Airlines"),
    ("HOOD", 0.40, "Robinhood - Fintech"),
]

# Delta ranges to test
DELTA_CONFIGS = [
    ("Ultra Conservative", 0.10, 0.20),
    ("Conservative", 0.20, 0.30),
    ("Moderate", 0.25, 0.35),
    ("Aggressive", 0.30, 0.40),
]

# RSI thresholds to test
RSI_THRESHOLDS = [25, 30, 35, 40, 45]

# Backtest periods
BACKTEST_PERIODS = [
    ("2023", "2023-01-01", "2024-01-01"),
    ("2024", "2024-01-01", "2024-12-01"),
    ("2023-2024", "2023-01-01", "2024-12-01"),
]

INITIAL_CAPITAL = 10000

# ============================================================================
# BACKTEST RUNNER
# ============================================================================

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


def create_config(delta_min: float, delta_max: float) -> AlpacaConfig:
    """Create AlpacaConfig with specified delta range"""
    watchlist = [
        StockConfig(
            symbol=symbol,
            max_position_size=max_pos,
            min_strike_delta=delta_min,
            max_strike_delta=delta_max
        )
        for symbol, max_pos, _ in WHEEL_CANDIDATES
    ]
    
    return AlpacaConfig(
        environment="paper",
        watchlist=watchlist,
        default_position_size=0.25,
        polling={
            'market_hours_interval': 60,
            'after_hours_interval': 300,
        }
    )


def run_single_backtest(
    period_name: str,
    start_date: str,
    end_date: str,
    delta_name: str,
    delta_min: float,
    delta_max: float,
    rsi: int
) -> BacktestResult:
    """Run a single backtest configuration"""
    
    config = create_config(delta_min, delta_max)
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    try:
        backtester = WheelBacktester(
            config=config,
            start_date=start,
            end_date=end,
            initial_capital=INITIAL_CAPITAL,
            rsi_oversold=rsi
        )
        results = backtester.run_backtest()
        
        return BacktestResult(
            period=period_name,
            delta_config=delta_name,
            rsi_threshold=rsi,
            total_return=results.get('total_return', 0),
            annual_return=results.get('annual_return', 0),
            sharpe_ratio=results.get('sharpe_ratio', 0),
            max_drawdown=results.get('max_drawdown', 0),
            win_rate=results.get('win_rate', 0),
            total_trades=results.get('total_trades', 0),
            final_value=results.get('final_portfolio_value', INITIAL_CAPITAL)
        )
    except Exception as e:
        print(f"  ERROR: {e}")
        return BacktestResult(
            period=period_name,
            delta_config=delta_name,
            rsi_threshold=rsi,
            total_return=0,
            annual_return=0,
            sharpe_ratio=0,
            max_drawdown=0,
            win_rate=0,
            total_trades=0,
            final_value=INITIAL_CAPITAL
        )


def run_all_backtests() -> List[BacktestResult]:
    """Run all backtest combinations"""
    results = []
    total_tests = len(BACKTEST_PERIODS) * len(DELTA_CONFIGS) * len(RSI_THRESHOLDS)
    current_test = 0
    
    print(f"\n{'='*70}")
    print(f"COMPREHENSIVE WHEEL STRATEGY BACKTEST")
    print(f"{'='*70}")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,}")
    print(f"Symbols: {', '.join([s[0] for s in WHEEL_CANDIDATES])}")
    print(f"Delta Configs: {len(DELTA_CONFIGS)}")
    print(f"RSI Thresholds: {RSI_THRESHOLDS}")
    print(f"Periods: {[p[0] for p in BACKTEST_PERIODS]}")
    print(f"Total Tests: {total_tests}")
    print(f"{'='*70}\n")
    
    for period_name, start, end in BACKTEST_PERIODS:
        print(f"\n--- Period: {period_name} ({start} to {end}) ---")
        
        for delta_name, delta_min, delta_max in DELTA_CONFIGS:
            for rsi in RSI_THRESHOLDS:
                current_test += 1
                print(f"[{current_test}/{total_tests}] {delta_name} | RSI={rsi}...", end=" ", flush=True)
                
                result = run_single_backtest(
                    period_name, start, end,
                    delta_name, delta_min, delta_max, rsi
                )
                results.append(result)
                
                if result.total_trades > 0:
                    print(f"Return: {result.total_return:.1%}, Trades: {result.total_trades}")
                else:
                    print("No trades")
    
    return results


def analyze_results(results: List[BacktestResult]):
    """Analyze and display results"""
    
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame([vars(r) for r in results])
    
    print(f"\n{'='*70}")
    print("RESULTS SUMMARY")
    print(f"{'='*70}\n")
    
    # -------------------------------------------------------------------------
    # 1. Best Overall Configurations
    # -------------------------------------------------------------------------
    print("\n📊 TOP 10 CONFIGURATIONS BY TOTAL RETURN:")
    print("-" * 60)
    
    top_configs = df.nlargest(10, 'total_return')[
        ['period', 'delta_config', 'rsi_threshold', 'total_return', 'annual_return', 
         'sharpe_ratio', 'max_drawdown', 'win_rate', 'total_trades']
    ].copy()
    top_configs['total_return'] = top_configs['total_return'].apply(lambda x: f"{x:.1%}")
    top_configs['annual_return'] = top_configs['annual_return'].apply(lambda x: f"{x:.1%}")
    top_configs['max_drawdown'] = top_configs['max_drawdown'].apply(lambda x: f"{x:.1%}")
    top_configs['win_rate'] = top_configs['win_rate'].apply(lambda x: f"{x:.0%}")
    top_configs['sharpe_ratio'] = top_configs['sharpe_ratio'].apply(lambda x: f"{x:.2f}")
    
    print(tabulate(top_configs, headers='keys', tablefmt='simple', showindex=False))
    
    # -------------------------------------------------------------------------
    # 2. Best Configuration by Risk-Adjusted Return (Sharpe)
    # -------------------------------------------------------------------------
    print("\n\n📈 TOP 10 BY RISK-ADJUSTED RETURN (SHARPE RATIO):")
    print("-" * 60)
    
    valid_sharpe = df[df['sharpe_ratio'] > 0].nlargest(10, 'sharpe_ratio')[
        ['period', 'delta_config', 'rsi_threshold', 'sharpe_ratio', 'total_return', 
         'max_drawdown', 'win_rate']
    ].copy()
    valid_sharpe['total_return'] = valid_sharpe['total_return'].apply(lambda x: f"{x:.1%}")
    valid_sharpe['max_drawdown'] = valid_sharpe['max_drawdown'].apply(lambda x: f"{x:.1%}")
    valid_sharpe['win_rate'] = valid_sharpe['win_rate'].apply(lambda x: f"{x:.0%}")
    valid_sharpe['sharpe_ratio'] = valid_sharpe['sharpe_ratio'].apply(lambda x: f"{x:.2f}")
    
    print(tabulate(valid_sharpe, headers='keys', tablefmt='simple', showindex=False))
    
    # -------------------------------------------------------------------------
    # 3. Delta Analysis
    # -------------------------------------------------------------------------
    print("\n\n📉 PERFORMANCE BY DELTA CONFIGURATION:")
    print("-" * 60)
    
    delta_summary = df.groupby('delta_config').agg({
        'total_return': 'mean',
        'annual_return': 'mean',
        'sharpe_ratio': 'mean',
        'max_drawdown': 'mean',
        'win_rate': 'mean',
        'total_trades': 'sum'
    }).round(4)
    
    delta_summary['total_return'] = delta_summary['total_return'].apply(lambda x: f"{x:.1%}")
    delta_summary['annual_return'] = delta_summary['annual_return'].apply(lambda x: f"{x:.1%}")
    delta_summary['max_drawdown'] = delta_summary['max_drawdown'].apply(lambda x: f"{x:.1%}")
    delta_summary['win_rate'] = delta_summary['win_rate'].apply(lambda x: f"{x:.0%}")
    delta_summary['sharpe_ratio'] = delta_summary['sharpe_ratio'].apply(lambda x: f"{x:.2f}")
    
    print(tabulate(delta_summary, headers='keys', tablefmt='simple'))
    
    # -------------------------------------------------------------------------
    # 4. RSI Analysis
    # -------------------------------------------------------------------------
    print("\n\n📊 PERFORMANCE BY RSI THRESHOLD:")
    print("-" * 60)
    
    rsi_summary = df.groupby('rsi_threshold').agg({
        'total_return': 'mean',
        'annual_return': 'mean',
        'sharpe_ratio': 'mean',
        'max_drawdown': 'mean',
        'win_rate': 'mean',
        'total_trades': 'sum'
    }).round(4)
    
    rsi_summary['total_return'] = rsi_summary['total_return'].apply(lambda x: f"{x:.1%}")
    rsi_summary['annual_return'] = rsi_summary['annual_return'].apply(lambda x: f"{x:.1%}")
    rsi_summary['max_drawdown'] = rsi_summary['max_drawdown'].apply(lambda x: f"{x:.1%}")
    rsi_summary['win_rate'] = rsi_summary['win_rate'].apply(lambda x: f"{x:.0%}")
    rsi_summary['sharpe_ratio'] = rsi_summary['sharpe_ratio'].apply(lambda x: f"{x:.2f}")
    
    print(tabulate(rsi_summary, headers='keys', tablefmt='simple'))
    
    # -------------------------------------------------------------------------
    # 5. Period Analysis
    # -------------------------------------------------------------------------
    print("\n\n📅 PERFORMANCE BY PERIOD:")
    print("-" * 60)
    
    period_summary = df.groupby('period').agg({
        'total_return': 'mean',
        'annual_return': 'mean',
        'sharpe_ratio': 'mean',
        'max_drawdown': 'mean',
        'win_rate': 'mean',
        'total_trades': 'sum'
    }).round(4)
    
    period_summary['total_return'] = period_summary['total_return'].apply(lambda x: f"{x:.1%}")
    period_summary['annual_return'] = period_summary['annual_return'].apply(lambda x: f"{x:.1%}")
    period_summary['max_drawdown'] = period_summary['max_drawdown'].apply(lambda x: f"{x:.1%}")
    period_summary['win_rate'] = period_summary['win_rate'].apply(lambda x: f"{x:.0%}")
    period_summary['sharpe_ratio'] = period_summary['sharpe_ratio'].apply(lambda x: f"{x:.2f}")
    
    print(tabulate(period_summary, headers='keys', tablefmt='simple'))
    
    # -------------------------------------------------------------------------
    # 6. Conclusions
    # -------------------------------------------------------------------------
    print(f"\n{'='*70}")
    print("📋 CONCLUSIONS & RECOMMENDATIONS")
    print(f"{'='*70}\n")
    
    # Find optimal settings
    best_overall = df.loc[df['total_return'].idxmax()]
    best_sharpe = df.loc[df['sharpe_ratio'].idxmax()]
    best_conservative = df[df['max_drawdown'] > -0.15].nlargest(1, 'total_return').iloc[0] if len(df[df['max_drawdown'] > -0.15]) > 0 else None
    
    # Average by delta
    delta_avg = df.groupby('delta_config')['total_return'].mean()
    best_delta = delta_avg.idxmax()
    
    # Average by RSI
    rsi_avg = df.groupby('rsi_threshold')['total_return'].mean()
    best_rsi = rsi_avg.idxmax()
    
    print("🏆 BEST CONFIGURATIONS:")
    print(f"   • Highest Return: {best_overall['delta_config']} delta, RSI={best_overall['rsi_threshold']}")
    print(f"     → {best_overall['total_return']:.1%} return, {best_overall['sharpe_ratio']:.2f} Sharpe")
    print()
    print(f"   • Best Risk-Adjusted: {best_sharpe['delta_config']} delta, RSI={best_sharpe['rsi_threshold']}")
    print(f"     → {best_sharpe['total_return']:.1%} return, {best_sharpe['sharpe_ratio']:.2f} Sharpe")
    
    if best_conservative is not None:
        print()
        print(f"   • Best Conservative (<15% drawdown): {best_conservative['delta_config']} delta, RSI={best_conservative['rsi_threshold']}")
        print(f"     → {best_conservative['total_return']:.1%} return, {best_conservative['max_drawdown']:.1%} max drawdown")
    
    print()
    print("📊 OPTIMAL SETTINGS (averaged across all periods):")
    print(f"   • Best Delta Range: {best_delta}")
    print(f"   • Best RSI Threshold: {best_rsi}")
    
    print()
    print("💡 KEY INSIGHTS:")
    
    # Delta insights
    if 'Aggressive' in best_delta or 'Moderate' in best_delta:
        print("   • Higher delta (0.30-0.40) tends to outperform - the extra premium")
        print("     compensates for higher assignment risk in these market conditions.")
    else:
        print("   • Lower delta (0.20-0.30) provides better risk-adjusted returns,")
        print("     avoiding costly assignments during market downturns.")
    
    # RSI insights
    if best_rsi >= 40:
        print(f"   • RSI threshold of {best_rsi} allows more frequent entries, capturing")
        print("     more premium in trending markets.")
    else:
        print(f"   • RSI threshold of {best_rsi} is more selective, only entering")
        print("     when stocks are oversold for better entry prices.")
    
    # Trade frequency
    avg_trades = df['total_trades'].mean()
    print(f"   • Average trades per configuration: {avg_trades:.0f}")
    
    print()
    print("⚠️  CAVEATS:")
    print("   • Backtests use historical option pricing which may not reflect")
    print("     actual fill prices (slippage, bid-ask spreads)")
    print("   • Past performance does not guarantee future results")
    print("   • Results depend heavily on the specific time period tested")
    print("   • Consider paper trading before live deployment")
    
    print()
    print(f"{'='*70}")
    print("RECOMMENDED STARTING CONFIGURATION FOR $10K ACCOUNT:")
    print(f"{'='*70}")
    print(f"""
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
        
      - symbol: INTC
        max_position_size: 0.25
        min_strike_delta: {0.25 if 'Conservative' in best_delta else 0.30}
        max_strike_delta: {0.35 if 'Conservative' in best_delta else 0.40}
        
      - symbol: BAC
        max_position_size: 0.45
        min_strike_delta: {0.25 if 'Conservative' in best_delta else 0.30}
        max_strike_delta: {0.35 if 'Conservative' in best_delta else 0.40}
    
    RSI Threshold: {best_rsi}
    """)
    
    return df


def main():
    """Main entry point"""
    import warnings
    warnings.filterwarnings('ignore')
    
    # Suppress logging during backtests
    import logging
    logging.getLogger().setLevel(logging.WARNING)
    
    print("\n" + "="*70)
    print("WHEEL STRATEGY COMPREHENSIVE BACKTEST")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all backtests
    results = run_all_backtests()
    
    # Analyze and display
    df = analyze_results(results)
    
    # Save results to CSV
    output_file = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df_export = pd.DataFrame([vars(r) for r in results])
    df_export.to_csv(output_file, index=False)
    print(f"\n📁 Results saved to: {output_file}")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

