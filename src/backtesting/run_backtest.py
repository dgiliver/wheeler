import logging
from datetime import datetime
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

from src.backtesting.wheel_backtester import WheelBacktester
from src.config.settings import AlpacaConfig, StockConfig

# Configure logging at the start of the application
log_file_path = "wheel_bot_backtest.log"  # Specify the log file name
logging.basicConfig(
    level=logging.INFO,  # Default to INFO, set to DEBUG if needed
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, mode="w"),  # Log to file only, overwrite each time
    ],
)
logger = logging.getLogger(__name__)


def load_strategy_config(config_path: str) -> AlpacaConfig:
    """Load strategy configuration from YAML and environment"""
    try:
        # Load environment variables
        load_dotenv()

        # Load strategy config from YAML
        with open(config_path) as f:
            config_data = yaml.safe_load(f)

        # Convert watchlist items to StockConfig objects
        watchlist = [
            StockConfig(
                symbol=stock["symbol"],
                max_position_size=float(stock["max_position_size"]),
                min_strike_delta=float(stock["min_strike_delta"]),
                max_strike_delta=float(stock["max_strike_delta"]),
            )
            for stock in config_data["watchlist"]
        ]

        # Create AlpacaConfig with just environment and watchlist
        return AlpacaConfig(
            environment=config_data.get("environment", "paper"),
            watchlist=watchlist,
            default_position_size=config_data.get("default_position_size", 0.2),
            polling=config_data.get(
                "polling",
                {
                    "market_hours_interval": 60,
                    "after_hours_interval": 300,
                    "check_premarket": True,
                    "check_afterhours": True,
                },
            ),
        )

    except Exception as e:
        logger.error(f"Error loading config from {config_path}: {e}")
        raise


@click.command()
@click.option("--config", "-c", default="config/wheel_strategy.yml", help="Path to config file")
@click.option("--start-date", "-s", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end-date", "-e", required=True, help="End date (YYYY-MM-DD)")
@click.option("--capital", "-m", default=100000, help="Initial capital")
@click.option("--rsi", "-r", default=30, help="RSI oversold threshold")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
def run_backtest(config: str, start_date: str, end_date: str, capital: float, rsi: int, debug: bool):
    """Run the wheel strategy backtest"""
    try:
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)

        # Load config
        config_path = Path(config)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config}")

        strategy_config = load_strategy_config(config_path)

        # Parse dates
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        # Create and run backtester
        backtester = WheelBacktester(strategy_config, start, end, capital, rsi_oversold=rsi)
        results = backtester.run_backtest()

        # Print results (to console as well for visibility)
        print("Backtest Complete!")
        print(f"Total Return: {results['total_return']:.2%}")
        print(f"Annual Return: {results['annual_return']:.2%}")
        print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {results['max_drawdown']:.2%}")
        print(f"Win Rate: {results['win_rate']:.2%}")
        print(f"Total Trades: {results['total_trades']}")

        print("\nPer Stock Summary:")
        for symbol, data in results.get("stock_summary", {}).items():
            print(f"\n{symbol}:")
            print(f"  Status: {data['status']}")
            if data["status"] == "HOLDING":
                print(f"  Shares: {data['shares']}")
                print(f"  Adjusted Cost Basis: ${data['adjusted_cost_basis']:.2f}")
                print(f"  Total Premium: ${data['total_premium']:.2f}")
            else:
                print(f"  Total Premium Collected: ${data['total_premium']:.2f}")
                print(f"  Net PnL: ${data['net_pnl']:.2f}")

        # Log results
        logger.info("Backtest Complete!")
        logger.info(f"Total Return: {results['total_return']:.2%}")
        logger.info(f"Annual Return: {results['annual_return']:.2%}")
        logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        logger.info(f"Max Drawdown: {results['max_drawdown']:.2%}")
        logger.info(f"Win Rate: {results['win_rate']:.2%}")
        logger.info(f"Total Trades: {results['total_trades']}")

        logger.info("\nPer Stock Summary:")
        for symbol, data in results.get("stock_summary", {}).items():
            logger.info(f"\n{symbol}:")
            logger.info(f"  Status: {data['status']}")
            if data["status"] == "HOLDING":
                logger.info(f"  Shares: {data['shares']}")
                logger.info(f"  Adjusted Cost Basis: ${data['adjusted_cost_basis']:.2f}")
                logger.info(f"  Total Premium: ${data['total_premium']:.2f}")
            else:
                logger.info(f"  Total Premium Collected: ${data['total_premium']:.2f}")
                logger.info(f"  Net PnL: ${data['net_pnl']:.2f}")

    except Exception as e:
        logger.error(f"Error running backtest: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    run_backtest()
