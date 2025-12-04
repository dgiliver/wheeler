import logging
from decimal import Decimal

import pandas as pd

from src.models.position import OptionQuote, Position, PositionType

logger = logging.getLogger(__name__)


class StrategyAnalyzer:
    def __init__(
        self,
        rsi_oversold: int = 45,  # Moderate threshold - enter when slightly oversold
        rsi_overbought: int = 70,
        max_spread_percentage: float = 15.0,
        min_volume: int = 10,
        min_open_interest: int = 0,  # Alpaca snapshots don't include OI reliably
        max_loss_percentage: float = 25.0,
        take_profit_percentage: float = 60.0,
    ):  # Take profit at 60% max profit
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.max_spread_percentage = max_spread_percentage
        self.min_volume = min_volume
        self.min_open_interest = min_open_interest
        self.max_loss_percentage = max_loss_percentage
        self.take_profit_percentage = take_profit_percentage

    def _is_liquid(self, option_quote: OptionQuote) -> tuple[bool, str]:
        """Check if option meets liquidity requirements based on config"""
        if option_quote.volume < self.min_volume:
            return False, f"Low volume: {option_quote.volume} < {self.min_volume}"

        if option_quote.open_interest < self.min_open_interest:
            return False, f"Low OI: {option_quote.open_interest} < {self.min_open_interest}"

        if option_quote.spread_percentage > self.max_spread_percentage:
            return False, f"Wide spread: {option_quote.spread_percentage:.1f}% > {self.max_spread_percentage}%"

        return True, "Liquid"

    def should_enter_csp(self, price_data: pd.DataFrame, option_quote: OptionQuote) -> tuple[bool, str]:
        """
        Determine if we should enter a CSP position based on technical analysis
        and option liquidity
        """
        is_liquid, reason = self._is_liquid(option_quote)
        if not is_liquid:
            return False, f"Insufficient liquidity: {reason}"

        rsi = self._calculate_rsi(price_data)

        if rsi <= self.rsi_oversold:
            return True, "RSI oversold condition met"

        return False, f"RSI {rsi:.2f} > {self.rsi_oversold}"

    def should_take_profit(self, position: Position, current_option_price: Decimal) -> tuple[bool, str]:
        """Determine if we should buy to close the option for a profit"""
        if position.position_type not in [PositionType.CASH_SECURED_PUT, PositionType.COVERED_CALL]:
            return False, "Not an option position"

        if position.premium_received <= 0:
            return False, "No premium recorded"

        # Calculate total cost to close (Current Price * Contracts * 100)
        cost_to_close = current_option_price * Decimal(str(position.contracts)) * 100

        # Calculate profit percentage
        # Profit = Premium Received - Cost to Close
        # Pct = Profit / Premium Received
        profit = position.premium_received - cost_to_close
        profit_pct = (profit / position.premium_received) * 100

        if profit_pct >= self.take_profit_percentage:
            return True, f"Profit target reached: {profit_pct:.1f}% >= {self.take_profit_percentage}%"

        # Also close if price is very low (e.g. 0.05) to free capital, even if % not met?
        # Standard "velocity of money" optimization
        if current_option_price <= Decimal("0.05"):
            return True, f"Option price negligible (${current_option_price}), closing to free capital"

        return False, f"Profit {profit_pct:.1f}% below target {self.take_profit_percentage}%"

    def should_force_exit(
        self, position: Position, current_price: Decimal, option_quote: OptionQuote | None = None
    ) -> tuple[bool, str]:
        """Determine if position should be forcefully exited due to risk"""
        if position.max_loss is None:
            return False, "No max loss set"

        unrealized_loss = (current_price - position.entry_price) * Decimal(position.quantity)
        if position.total_cost == 0:
            return False, "Total cost is 0"

        loss_percentage = abs(float(unrealized_loss / position.total_cost * 100))

        # Force exit if loss exceeds threshold
        if loss_percentage >= self.max_loss_percentage:
            return True, f"Loss threshold exceeded: {loss_percentage:.1f}%"

        # For options, check if spread has widened significantly
        if option_quote and option_quote.spread_percentage > self.max_spread_percentage:
            return True, f"Spread too wide: {option_quote.spread_percentage:.1f}%"

        return False, "No forced exit needed"

    def should_roll_option(
        self,
        days_to_expiry: int,
        current_strike: Decimal,
        current_price: Decimal,
        is_put: bool,
        option_quote: OptionQuote,
    ) -> tuple[bool, str]:
        """
        Determine if an option position should be rolled.

        For wheel strategy: We WANT ITM assignment, so only roll OTM options near expiry.
        - ITM puts = get assigned shares (start selling CCs)
        - ITM calls = shares called away (collect premium + gains)
        """
        # Only consider rolling near expiry
        if days_to_expiry > 5:
            return False, "Not near expiry yet"

        # Near expiry - check if OTM (worth rolling for more premium)
        if is_put and current_price > current_strike:
            # OTM put - roll to collect more premium
            return True, f"OTM put expiring in {days_to_expiry} days, roll for more premium"

        if not is_put and current_price < current_strike:
            # OTM call - roll to collect more premium
            return True, f"OTM call expiring in {days_to_expiry} days, roll for more premium"

        # ITM - let assignment happen (wheel strategy)
        return False, "ITM option near expiry - allowing assignment per wheel strategy"

    def get_optimal_exit_price(self, option_quote: OptionQuote, position: Position) -> Decimal:
        """Calculate optimal exit price based on spread and risk"""
        # If spread is wide, we might need to be more aggressive
        if option_quote.spread_percentage > self.max_spread_percentage:
            # Use bid price if we need to exit quickly
            return Decimal(str(option_quote.bid))

        # For normal conditions, aim for midpoint
        return Decimal(str((option_quote.bid + option_quote.ask) / 2))

    def accept_assignment(
        self, cost_basis: Decimal, current_price: Decimal, implied_volatility: float
    ) -> tuple[bool, str]:
        """Determine if we should accept assignment on a CSP"""
        if implied_volatility > 50 and current_price >= cost_basis * Decimal("0.9"):
            return True, "High IV and price near cost basis, accept assignment"
        return False, "Avoid assignment, consider rolling"

    def _calculate_rsi(self, price_data: pd.DataFrame, periods: int = 14) -> float:
        """Calculate RSI technical indicator"""
        if len(price_data) < periods + 1:
            return 50.0  # Default neutral RSI if not enough data

        delta = price_data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Handle potential NaN
        if pd.isna(rsi.iloc[-1]):
            return 50.0

        return rsi.iloc[-1]

    def analyze_put_opportunity(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        options_chain: list[dict],
        min_delta: float = 0.20,
        max_delta: float = 0.45,
    ) -> dict | None:
        """Analyze and find the optimal put selling opportunity."""
        logger.info(f"Analyzing put opportunity for {symbol} (delta range: {min_delta}-{max_delta})")

        if price_data.empty or not options_chain:
            logger.info(f"No data available for {symbol}")
            return None

        # Calculate RSI once
        rsi = self._calculate_rsi(price_data)
        logger.info(f"{symbol} RSI: {rsi:.2f} (threshold: {self.rsi_oversold})")

        # Check if RSI indicates oversold
        if rsi > self.rsi_oversold:
            logger.info(f"{symbol} RSI {rsi:.2f} > {self.rsi_oversold} (not oversold, skipping)")
            return None

        logger.info(f"{symbol} passed RSI check, analyzing {len(options_chain)} options...")

        best_option = None
        best_score = -1

        for option in options_chain:
            # Check type explicitly if available (it is in our synthetic data)
            if option.get("type") == "call":
                continue
            if option.get("type") != "put" and "P" not in option["id"]:
                continue

            # Safely construct OptionQuote
            try:
                quote = OptionQuote(
                    bid=Decimal(str(option.get("bid", 0))),
                    ask=Decimal(str(option.get("ask", 0))),
                    volume=int(option.get("volume", 0)),
                    open_interest=int(option.get("open_interest", 0)),
                    implied_volatility=float(option.get("implied_volatility", 0)),
                    delta=float(option.get("delta", 0)),
                )
            except Exception as e:
                logger.warning(f"Failed to parse option {option.get('id')}: {e}")
                continue

            is_liquid, reason = self._is_liquid(quote)
            if not is_liquid:
                continue

            # Configurable delta check
            abs_delta = abs(quote.delta)
            if not (min_delta <= abs_delta <= max_delta):
                continue

            logger.debug(f"  Candidate: Strike={option['strike']}, Delta={abs_delta:.3f}, Bid={quote.bid}")

            # Scoring: higher premium is better
            score = float(quote.bid)

            if score > best_score:
                best_score = score
                best_option = option
                logger.debug(f"New best option found: Strike={option['strike']}, Premium={score}, Delta={quote.delta}")

        if best_option:
            logger.info(
                f"Selected put option for {symbol}: Strike={best_option['strike']}, Premium={best_option.get('bid')}"
            )

        return best_option

    def analyze_call_opportunity(
        self,
        symbol: str,
        cost_basis: Decimal,
        options_chain: list[dict],
        min_delta: float = 0.15,
        max_delta: float = 0.40,
    ) -> dict | None:
        """Analyze and find the optimal covered call selling opportunity."""
        logger.debug(f"Analyzing call opportunity for {symbol} with cost basis {cost_basis}")

        if not options_chain:
            logger.debug(f"No options chain available for {symbol}")
            return None

        best_option = None
        best_score = -1

        for option in options_chain:
            # Check type explicitly
            if option.get("type") == "put":
                continue
            if option.get("type") != "call" and "C" not in option["id"]:
                continue

            # Safely construct OptionQuote
            try:
                quote = OptionQuote(
                    bid=Decimal(str(option.get("bid", 0))),
                    ask=Decimal(str(option.get("ask", 0))),
                    volume=int(option.get("volume", 0)),
                    open_interest=int(option.get("open_interest", 0)),
                    implied_volatility=float(option.get("implied_volatility", 0)),
                    delta=float(option.get("delta", 0)),
                )
            except Exception:  # noqa: BLE001
                continue  # nosec B112 - intentionally skip malformed options

            is_liquid, reason = self._is_liquid(quote)
            if not is_liquid:
                continue

            # Strike must be above cost basis to avoid loss assignment
            strike = Decimal(str(option["strike"]))
            if strike < cost_basis:
                # logger.debug(f"Skipping strike {strike} below cost basis {cost_basis}")
                continue

            # Configurable Delta check for Calls
            if not (min_delta <= quote.delta <= max_delta):
                continue

            # Scoring: Premium
            score = float(quote.bid)

            if score > best_score:
                best_score = score
                best_option = option
                logger.debug(f"New best call found: Strike={strike}, Premium={score}, Delta={quote.delta}")

        if best_option:
            logger.info(
                f"Selected call option for {symbol}: Strike={best_option['strike']}, Premium={best_option.get('bid')}"
            )

        return best_option
