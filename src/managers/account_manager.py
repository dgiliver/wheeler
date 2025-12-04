import logging
from decimal import Decimal

from src.config.settings import PDTConfig
from src.models.position import Position, PositionType

logger = logging.getLogger(__name__)


class AccountManager:
    def __init__(self, total_balance: Decimal, max_position_size: float = 0.2, pdt_config: PDTConfig | None = None):
        self.total_balance = total_balance
        self.max_position_size = Decimal(str(max_position_size))
        self.positions: list[Position] = []

        # PDT tracking - sourced from Alpaca
        self.pdt_config = pdt_config or PDTConfig()
        self.equity: Decimal = total_balance  # Updated from Alpaca
        self.daytrade_count: int = 0  # Updated from Alpaca
        self.is_pattern_day_trader: bool = False  # If flagged by broker

    def can_open_position(self, position_cost: Decimal, existing_symbol: str = None) -> bool:
        """Check if we can open a position of given size"""
        # If adding to existing position, only check total position size
        if existing_symbol:
            existing_position = next((p for p in self.positions if p.symbol == existing_symbol), None)
            if existing_position:
                total_cost = existing_position.total_cost + position_cost
                return total_cost <= self.total_balance * self.max_position_size

        return position_cost <= self.total_balance * self.max_position_size

    def update_pdt_status(self, equity: Decimal, daytrade_count: int, is_pattern_day_trader: bool) -> None:
        """Update PDT tracking info from Alpaca account data"""
        self.equity = equity
        self.daytrade_count = daytrade_count
        self.is_pattern_day_trader = is_pattern_day_trader

        # Log warnings if approaching PDT limit
        if self._is_pdt_restricted() and daytrade_count >= self.pdt_config.warn_at:
            remaining = self.pdt_config.max_day_trades - daytrade_count
            logger.warning(
                f"PDT Warning: {daytrade_count}/{self.pdt_config.max_day_trades} day trades used. "
                f"{remaining} remaining. Equity: ${self.equity}"
            )

    def _is_pdt_restricted(self) -> bool:
        """Check if account is subject to PDT restrictions"""
        # If already flagged as PDT, no restrictions (but more scrutiny from broker)
        if self.is_pattern_day_trader:
            return False
        # PDT rules apply to accounts under threshold
        return self.equity < self.pdt_config.threshold

    def would_exceed_day_trades(self) -> bool:
        """Check if a new day trade would exceed PDT rules (3 day trades in 5 trading days)"""
        # If not subject to PDT restrictions, allow trade
        if not self._is_pdt_restricted():
            return False

        # Check if we've already used all allowed day trades
        return self.daytrade_count >= self.pdt_config.max_day_trades

    def can_day_trade(self) -> tuple[bool, str]:
        """Check if we can safely make a day trade. Returns (can_trade, reason)"""
        if not self._is_pdt_restricted():
            return True, "Account not subject to PDT restrictions"

        if self.daytrade_count >= self.pdt_config.max_day_trades:
            return False, (
                f"PDT limit reached: {self.daytrade_count}/{self.pdt_config.max_day_trades} "
                f"day trades used. Equity ${self.equity} < ${self.pdt_config.threshold}"
            )

        remaining = self.pdt_config.max_day_trades - self.daytrade_count
        return True, f"Day trade allowed. {remaining} remaining in rolling 5-day window"

    def get_position_cost_basis(self, symbol: str) -> Decimal:
        """Calculate the cost basis for a given symbol including premiums received"""
        total_cost = Decimal(0)
        total_premium = Decimal(0)

        for position in self.positions:
            if position.symbol == symbol:
                if position.position_type == PositionType.STOCK:
                    total_cost += position.total_cost
                total_premium += position.premium_received

        return total_cost - total_premium if total_cost > 0 else Decimal(0)

    def get_max_contracts(
        self, strike_price: Decimal, existing_symbol: str = None, position_size_override: float = None
    ) -> int:
        """Calculate maximum number of contracts we can open"""
        contract_cost = strike_price * Decimal("100")  # Cost per contract

        # Use override if provided (per-stock config), otherwise use default
        size_pct = Decimal(str(position_size_override)) if position_size_override else self.max_position_size
        max_position_cost = self.total_balance * size_pct

        # If adding to existing position, subtract existing cost
        if existing_symbol:
            existing_position = next((p for p in self.positions if p.symbol == existing_symbol), None)
            if existing_position:
                max_position_cost -= existing_position.total_cost

        max_contracts = int(max_position_cost / contract_cost)
        return max(0, max_contracts)  # Ensure non-negative
