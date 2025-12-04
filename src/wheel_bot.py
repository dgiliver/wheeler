import logging
import time as time_module
from datetime import datetime, time, timedelta
from decimal import Decimal

import pytz
import yaml

from src.analysis import StrategyAnalyzer
from src.config import AlpacaConfig, PDTConfig, StockConfig
from src.managers import AccountManager
from src.models import PositionType
from src.services import AlpacaService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("wheel_bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class WheelBot:
    def __init__(self, config_path: str):
        logger.info(f"Initializing WheelBot with config from {config_path}")
        self.config = self._load_config(config_path)
        logger.debug(f"Loaded config: {self.config}")

        # Validate environment variables
        if not all([self.config.api_key, self.config.api_secret, self.config.base_url]):
            logger.error(f"Missing required environment variables for {self.config.environment} environment")
            raise ValueError(
                f"Missing required environment variables for {self.config.environment} environment. "
                "Please check your .env file."
            )

        logger.info(f"Connecting to Alpaca API ({self.config.environment} environment)")
        self.alpaca = AlpacaService(self.config)
        self.strategy = StrategyAnalyzer()

        account = self.alpaca.get_account()
        if not account:
            raise ValueError("Could not get account information from Alpaca")

        alpaca_balance = Decimal(str(account["portfolio_value"]))
        logger.info(f"Connected successfully. Alpaca balance: ${alpaca_balance}")

        # Use configured max_capital if set, otherwise use Alpaca balance
        trading_capital = self.config.max_capital if self.config.max_capital else alpaca_balance
        if self.config.max_capital:
            logger.info(f"Using configured max_capital: ${trading_capital} (Alpaca has ${alpaca_balance})")

        self.account_manager = AccountManager(
            total_balance=trading_capital,
            max_position_size=self.config.default_position_size,
            pdt_config=self.config.pdt,
        )

        # Initialize PDT status from account
        self._sync_pdt_status(account)

        self.et_timezone = pytz.timezone("US/Eastern")
        logger.info("WheelBot initialization complete")

    def _load_config(self, config_path: str) -> AlpacaConfig:
        """Load configuration from YAML file"""
        with open(config_path) as f:
            config_data = yaml.safe_load(f)

        watchlist = [
            StockConfig(**{**stock_config, "max_position_size": Decimal(str(stock_config["max_position_size"]))})
            for stock_config in config_data["watchlist"]
        ]

        # Parse PDT config if present
        pdt_data = config_data.get("pdt", {})
        pdt_config = PDTConfig(
            threshold=Decimal(str(pdt_data.get("threshold", 25000))),
            max_day_trades=pdt_data.get("max_day_trades", 3),
            warn_at=pdt_data.get("warn_at", 2),
        )

        # Parse max_capital if provided
        max_capital = config_data.get("max_capital")
        if max_capital:
            max_capital = Decimal(str(max_capital))

        return AlpacaConfig(
            environment=config_data.get("environment", "paper"),
            watchlist=watchlist,
            default_position_size=config_data.get("default_position_size", 0.2),
            max_capital=max_capital,
            max_contracts_per_symbol=config_data.get("max_contracts_per_symbol", 1),
            pdt=pdt_config,
        )

    def run(self):
        """Main bot loop"""
        logger.info("Starting main bot loop")
        while True:
            try:
                current_time = datetime.now(self.et_timezone)
                logger.debug(f"Current time (ET): {current_time}")

                if not self._is_trading_time(current_time):
                    logger.info("Outside trading hours, using extended interval")
                    time_module.sleep(self.config.polling.after_hours_interval)
                    continue

                logger.debug("Checking existing positions")
                sync_ok = self._check_positions()

                if sync_ok:
                    logger.debug("Looking for new entry opportunities")
                    self._look_for_entries()
                else:
                    logger.warning("Skipping entry check due to position sync failure")

                logger.debug(f"Sleeping for {self.config.polling.market_hours_interval} seconds")
                time_module.sleep(self.config.polling.market_hours_interval)

            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                time_module.sleep(self.config.polling.market_hours_interval)

    def _is_trading_time(self, current_time: datetime) -> bool:
        """Check if we should be trading based on current time"""
        current_time_et = current_time.time()
        logger.debug(f"Checking trading time for {current_time_et} ET")

        # Regular market hours (9:30 AM to 4:00 PM ET)
        if time(9, 30) <= current_time_et < time(16, 0):
            logger.debug(f"{current_time_et} is within regular market hours")
            return True

        # Pre-market (4:00 AM to 9:30 AM ET)
        if self.config.polling.check_premarket and time(4, 0) <= current_time_et < time(9, 30):
            logger.debug(f"{current_time_et} is within pre-market hours")
            return True

        # After-hours (4:00 PM to 8:00 PM ET)
        if self.config.polling.check_afterhours and time(16, 0) < current_time_et < time(
            20, 0
        ):  # Note: strict inequality for market close
            logger.debug(f"{current_time_et} is within after-hours")
            return True

        logger.debug(f"{current_time_et} is outside all trading hours")
        return False

    def _sync_pdt_status(self, account: dict = None):
        """Sync PDT status from Alpaca account"""
        try:
            if account is None:
                account = self.alpaca.get_account()

            if account:
                equity = Decimal(str(account.get("equity", account.get("portfolio_value", 0))))
                daytrade_count = account.get("daytrade_count", 0) or 0
                is_pdt = account.get("pattern_day_trader", False) or False

                self.account_manager.update_pdt_status(equity, daytrade_count, is_pdt)

                # Log PDT status on sync
                if equity < self.config.pdt.threshold:
                    logger.info(
                        f"PDT Status: {daytrade_count}/{self.config.pdt.max_day_trades} day trades, "
                        f"Equity: ${equity:.2f} (under ${self.config.pdt.threshold} threshold)"
                    )
        except Exception as e:
            logger.error(f"Error syncing PDT status: {e}")

    def _sync_positions(self) -> bool:
        """Sync local account manager positions with Alpaca. Returns True if successful."""
        try:
            alpaca_positions = self.alpaca.get_positions()
            self.account_manager.positions = alpaca_positions
            logger.info(f"Synced {len(self.account_manager.positions)} positions from Alpaca")

            # Also sync PDT status
            self._sync_pdt_status()
            return True
        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
            logger.warning("Position sync failed - skipping this cycle to avoid duplicate orders")
            return False

    def _check_positions(self) -> bool:
        """Check existing positions for rolling opportunities or covered calls.
        Returns True if sync was successful, False if we should skip entries."""
        sync_success = self._sync_positions()
        if not sync_success:
            return False  # Don't proceed if sync failed

        position_count = len(self.account_manager.positions)
        logger.info(f"Checking {position_count} positions")

        for position in self.account_manager.positions:
            # Handle Options (Rolling)
            if position.expiration:  # Options position
                logger.debug(
                    f"Checking option position: {position.symbol} "
                    f"Strike: {position.strike_price} "
                    f"Expiry: {position.expiration}"
                )

                price_data = self.alpaca.get_price_history(position.symbol, days=1)
                if price_data.empty:
                    continue

                logger.debug(f"Current price data for {position.symbol}: {price_data.iloc[-1]}")

                # Get option chain for rolling (look 21-45 days out)
                option_chain = self.alpaca.get_option_chain(
                    position.symbol, datetime.now() + timedelta(days=30), min_dte=21, max_dte=45
                )

                current_price = price_data["close"].iloc[-1]
                days_to_expiry = (position.expiration - datetime.now()).days

                logger.info(
                    f"Position check for {position.symbol}: DTE={days_to_expiry}, "
                    f"Strike={position.strike_price}, Current=${current_price:.2f}"
                )

                # Fetch current option chain for THIS expiration to get current quote
                current_chain = self.alpaca.get_option_chain(
                    position.symbol, position.expiration, min_dte=0, max_dte=days_to_expiry + 1
                )

                # Find our specific option in the chain
                option_type = "P" if position.position_type == PositionType.CASH_SECURED_PUT else "C"
                current_option = None

                # Build expected expiration string (YYMMDD format)
                exp_str = position.expiration.strftime("%y%m%d")
                logger.info(
                    f"Looking for option with exp={exp_str}, strike={position.strike_price}, type={option_type}"
                )

                for opt in current_chain:
                    opt_id = opt["id"]
                    # Match by strike, type, AND expiration date
                    # OCC format: SYMBOL + YYMMDD + C/P + STRIKE (8 digits)
                    if (
                        abs(Decimal(str(opt["strike"])) - position.strike_price) < Decimal("0.01")
                        and option_type in opt_id
                        and exp_str in opt_id
                    ):
                        current_option = opt
                        logger.info(f"Matched position to option: {opt_id}")
                        break

                if not current_option:
                    logger.warning(
                        f"Could not find current option quote for {position.symbol} "
                        f"strike {position.strike_price} exp {exp_str}"
                    )
                    continue

                logger.debug(f"Found matching option: {current_option['id']} for position exp {exp_str}")

                current_ask = Decimal(str(current_option["ask"]))
                logger.info(f"Current option quote: Bid={current_option['bid']}, Ask={current_option['ask']}")

                # ============================================================
                # TAKE PROFIT CHECK - Buy to close at 50%+ profit
                # ============================================================
                should_take_profit, profit_reason = self.strategy.should_take_profit(position, current_ask)

                if should_take_profit:
                    can_trade, pdt_reason = self.account_manager.can_day_trade()
                    if not can_trade:
                        logger.warning(f"Cannot take profit on {position.symbol}: {pdt_reason}")
                    else:
                        logger.info(f"Taking profit on {position.symbol}: {profit_reason}")
                        logger.info(f"Buying to close option: {current_option['id']}")
                        # Buy to close
                        self.alpaca.place_option_order(current_option["id"], "buy", abs(position.contracts))
                        continue  # Don't check rolling if we're closing

                # ============================================================
                # ROLL CHECK - Only roll near expiry, NOT for ITM
                # For wheel strategy, we WANT assignment on ITM puts
                # ============================================================
                is_put = position.position_type == PositionType.CASH_SECURED_PUT

                # Only consider rolling if near expiry (<=5 DTE) AND still OTM
                # If ITM, let it get assigned (that's the wheel!)
                should_roll = False
                roll_reason = ""

                if days_to_expiry <= 5:
                    logger.info(f"{position.symbol} near expiry ({days_to_expiry} DTE), checking roll conditions...")
                    if is_put and current_price > position.strike_price:
                        # OTM put near expiry - roll to collect more premium
                        should_roll = True
                        roll_reason = f"OTM put expiring in {days_to_expiry} days, rolling for more premium"
                    elif not is_put and current_price < position.strike_price:
                        # OTM call near expiry - roll to collect more premium
                        should_roll = True
                        roll_reason = f"OTM call expiring in {days_to_expiry} days, rolling for more premium"
                    elif is_put and current_price <= position.strike_price:
                        # ITM put - let it get assigned (wheel strategy)
                        logger.info(
                            f"{position.symbol} put is ITM (${current_price:.2f} <= ${position.strike_price}), "
                            f"allowing assignment per wheel strategy"
                        )
                    elif not is_put and current_price >= position.strike_price:
                        # ITM call - let shares get called away
                        logger.info(
                            f"{position.symbol} call is ITM (${current_price:.2f} >= ${position.strike_price}), "
                            f"allowing assignment per wheel strategy"
                        )
                else:
                    logger.info(f"{position.symbol}: {days_to_expiry} DTE remaining, no roll needed yet")

                if should_roll and option_chain:
                    can_trade, pdt_reason = self.account_manager.can_day_trade()
                    if not can_trade:
                        logger.warning(f"Cannot roll {position.symbol}: {pdt_reason}")
                        continue

                    logger.info(f"Rolling {position.symbol}: {roll_reason}")

                    # Find best new option to roll into
                    if is_put:
                        new_option = self.strategy.analyze_put_opportunity(position.symbol, price_data, option_chain)
                    else:
                        new_option = self.strategy.analyze_call_opportunity(
                            position.symbol, position.entry_price, option_chain
                        )

                    if new_option:
                        # Close current position
                        self.alpaca.place_option_order(current_option["id"], "buy", abs(position.contracts))
                        # Open new position
                        self.alpaca.place_option_order(new_option["id"], "sell", abs(position.contracts))
                        logger.info(
                            f"Rolled {position.symbol} from strike {position.strike_price} "
                            f"to strike {new_option['strike']}"
                        )
                    else:
                        logger.warning(f"No suitable option found to roll {position.symbol} into")

                elif not option_chain:
                    logger.warning(f"No option chain data available for rolling {position.symbol}")

            # Handle Stocks (Selling Covered Calls)
            elif position.position_type == PositionType.STOCK:
                if position.quantity < 100:
                    continue

                # Check if we already have a covered call for this symbol
                # Note: We check for any SHORT CALL on the same symbol
                has_cc = any(
                    p.symbol == position.symbol and p.position_type == PositionType.COVERED_CALL
                    for p in self.account_manager.positions
                )

                if has_cc:
                    logger.debug(f"Already have CC for {position.symbol}, skipping")
                    continue

                logger.info(f"Looking for Covered Call for {position.symbol}")

                # Use DTE range for covered calls (typically 30-45 days)
                expiration = datetime.now() + timedelta(days=45)
                chain = self.alpaca.get_option_chain(position.symbol, expiration, min_dte=14, max_dte=45)

                if not chain:
                    continue

                # Analyze for Call opportunity
                # Use entry_price as cost basis to ensure Strike >= Cost Basis
                call = self.strategy.analyze_call_opportunity(position.symbol, position.entry_price, chain)

                if call:
                    # Check PDT before selling CC
                    can_trade, pdt_reason = self.account_manager.can_day_trade()
                    if not can_trade:
                        logger.warning(f"Cannot sell CC for {position.symbol}: {pdt_reason}")
                        continue

                    num_contracts = position.quantity // 100
                    logger.info(
                        f"Selling {num_contracts} CC for {position.symbol} Strike={call['strike']} Premium={call['bid']}"
                    )
                    self.alpaca.place_option_order(call["id"], "sell", num_contracts)

        return True  # Sync and check completed successfully

    def _look_for_entries(self):
        """Look for new position entry opportunities"""
        logger.info(f"Looking for entry opportunities in {len(self.config.watchlist)} symbols")

        # Get pending orders to avoid duplicates
        try:
            pending_orders = self.alpaca.get_orders(status="open")
        except Exception as e:
            logger.error(f"Failed to fetch pending orders: {e}")
            logger.warning("Skipping entry loop - cannot verify pending orders")
            return

        pending_symbols = set()
        for order in pending_orders:
            symbol = order.get("symbol", "")
            # Extract underlying from option symbol (e.g., AMD260109P00210000 -> AMD)
            if len(symbol) > 15:
                underlying = symbol[:-15]
                pending_symbols.add(underlying)
            else:
                pending_symbols.add(symbol)

        for stock in self.config.watchlist:
            # Check for pending orders first
            if stock.symbol in pending_symbols:
                logger.info(f"Pending order exists for {stock.symbol}, skipping")
                continue

            # Check if we have a position in account manager
            existing_position = next((p for p in self.account_manager.positions if p.symbol == stock.symbol), None)
            if existing_position:
                logger.info(
                    f"Already have {existing_position.position_type.value} position in {stock.symbol}, skipping entry"
                )
                continue

            # Then check Alpaca API for positions (with error handling)
            try:
                alpaca_position = self.alpaca.get_position(stock.symbol)
                if alpaca_position:
                    logger.info(f"Found existing position in {stock.symbol} from Alpaca API, skipping entry")
                    continue
            except Exception as e:
                logger.error(f"Failed to check position for {stock.symbol}: {e}")
                logger.warning(f"Skipping {stock.symbol} - cannot verify position status")
                continue

            # Get price history (required for RSI calculation)
            try:
                price_data = self.alpaca.get_price_history(stock.symbol)
                if price_data.empty:
                    logger.warning(f"No price data available for {stock.symbol}")
                    continue
            except Exception as e:
                logger.error(f"Failed to fetch price data for {stock.symbol}: {e}")
                continue

            # Find suitable option contracts using DTE range from config
            min_dte = getattr(stock, "min_days_to_expiry", 14)
            max_dte = getattr(stock, "max_days_to_expiry", 45)
            expiration = datetime.now() + timedelta(days=max_dte)  # Use max as target

            logger.info(f"Fetching option chain for {stock.symbol} with DTE range {min_dte}-{max_dte}")

            try:
                chain = self.alpaca.get_option_chain(stock.symbol, expiration, min_dte=min_dte, max_dte=max_dte)
            except Exception as e:
                logger.error(f"Failed to fetch option chain for {stock.symbol}: {e}")
                continue

            logger.info(f"Got {len(chain) if chain else 0} options for {stock.symbol}")

            if not chain:
                logger.warning(f"No option chain data available for {stock.symbol}")
                continue

            # Use strategy analyzer to find best put
            best_put = self.strategy.analyze_put_opportunity(
                symbol=stock.symbol,
                price_data=price_data,
                options_chain=chain,
                min_delta=stock.min_strike_delta,
                max_delta=stock.max_strike_delta,
            )

            if not best_put:
                logger.info(f"No suitable put found for {stock.symbol} (RSI or liquidity filter)")

            if best_put:
                # Calculate maximum contracts we can open using per-stock position size
                max_contracts = self.account_manager.get_max_contracts(
                    strike_price=Decimal(str(best_put["strike"])),
                    existing_symbol=stock.symbol,
                    position_size_override=float(stock.max_position_size),
                )

                # Apply global safety limit
                max_contracts = min(max_contracts, self.config.max_contracts_per_symbol)

                contract_cost = Decimal(str(best_put["strike"])) * 100
                max_allowed = self.account_manager.total_balance * Decimal(str(stock.max_position_size))

                if max_contracts > 0:
                    reason = f"Selected strike {best_put['strike']} with premium {best_put['bid']}"
                    logger.info(f"Opening {max_contracts} CSP contract(s) for {stock.symbol}: {reason}")
                    # Place order for multiple contracts
                    try:
                        self.alpaca.place_option_order(best_put["id"], "sell", max_contracts)
                    except Exception as e:
                        logger.error(f"Failed to place order for {stock.symbol}: {e}")
                else:
                    logger.warning(
                        f"Cannot open {stock.symbol} CSP: contract cost ${contract_cost} > "
                        f"max position ${max_allowed} ({stock.max_position_size * 100:.0f}% of ${self.account_manager.total_balance})"
                    )
