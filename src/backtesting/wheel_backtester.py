from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
import logging
from typing import List, Dict, Optional
import pandas_market_calendars as mcal

from src.models.position import Position, PositionType
from src.config.settings import AlpacaConfig, StockConfig
from src.backtesting.historical_data import AlpacaHistoricalDataProvider
from src.analysis.strategy_analyzer import StrategyAnalyzer

logger = logging.getLogger(__name__)

class WheelBacktester:
    def __init__(self, config: AlpacaConfig, start_date: datetime, end_date: datetime, initial_capital: float = 100000, rsi_oversold: int = 30):
        self.config = config
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = Decimal(str(initial_capital))
        self.current_capital = self.initial_capital
        self.positions: List[Position] = []
        self.trades: List[Dict] = []
        self.daily_portfolio_value: List[Dict] = []
        
        # Initialize data provider with config credentials
        self.data_provider = AlpacaHistoricalDataProvider(
            api_key=config.api_key,
            api_secret=config.api_secret
        )
        
        # Initialize market calendar
        self.calendar = mcal.get_calendar('NYSE')
        
        # Initialize strategy analyzer with configurable RSI
        self.strategy_analyzer = StrategyAnalyzer(
            rsi_oversold=rsi_oversold,
            min_volume=10,  # Relaxed for backtesting
            min_open_interest=50
        )
        
    def _is_trading_day(self, date: datetime) -> bool:
        """Check if date is a trading day"""
        schedule = self.calendar.schedule(
            start_date=date.date(),
            end_date=date.date()
        )
        is_trading_day = not schedule.empty
        logger.debug(f"Date {date} is trading day: {is_trading_day}")
        return is_trading_day
        
    def _get_historical_prices(self, symbol: str, date: datetime) -> pd.DataFrame:
        """Get historical price data for analysis"""
        logger.debug(f"Fetching historical prices for {symbol} on {date}")
        start_date = date - timedelta(days=30)
        prices = self.data_provider.get_price_history(symbol, start_date, date)
        logger.debug(f"Prices fetched for {symbol}: {len(prices)} records")
        return prices
        
    def _can_enter_new_position(self, stock: StockConfig) -> bool:
        """Check if we can enter a new position based on capital requirements"""
        symbol_positions_value = sum(
            float(pos.quantity * pos.entry_price)
            for pos in self.positions 
            if pos.symbol == stock.symbol
        )
        
        max_position_value = float(self.initial_capital) * float(stock.max_position_size)
        can_enter = symbol_positions_value < max_position_value
        logger.debug(f"Can enter new position for {stock.symbol}: {can_enter}")
        return can_enter
        
    def _sell_put(self, date: datetime, put: Dict, stock: StockConfig):
        """Sell a put option"""
        logger.debug(f"Selling put for {stock.symbol} on {date}: {put}")
        premium = Decimal(str(put['bid']))
        quantity = Decimal('1')  # Start with 1 contract (100 shares)
        
        self.trades.append({
            'date': date,
            'symbol': stock.symbol,
            'action': 'SELL_PUT',
            'quantity': int(quantity),
            'price': float(premium),
            'option_id': put['id']
        })
        
        position = Position(
            symbol=stock.symbol,
            entry_price=Decimal(str(put['strike'])),
            quantity=int(quantity * Decimal('100')),  # Each contract is 100 shares
            position_type=PositionType.CASH_SECURED_PUT, # Corrected type
            expiration=self._extract_expiration(put['id']),
            strike_price=Decimal(str(put['strike'])),
            premium_received=premium
        )
        self.positions.append(position)
        
        self.current_capital += premium * Decimal('100')  # Premium per share * 100 shares
        logger.info(f"SELL PUT: {stock.symbol} Strike={put['strike']} Exp={put['expiration']} Premium={premium}")
        logger.debug(f"Updated capital: {self.current_capital}")
        
    def _handle_option_expiration(self, date: datetime, position: Position):
        """Handle option expiration"""
        logger.debug(f"Handling option expiration for {position.symbol} on {date}")
        current_price = self._get_current_price(position.symbol, date)
        if current_price is None:
            logger.debug(f"No current price available for {position.symbol} on {date}")
            return
            
        if position.position_type == PositionType.CASH_SECURED_PUT:
            if current_price < float(position.strike_price):
                # Assignment (PUT)
                self.trades.append({
                    'date': date,
                    'symbol': position.symbol,
                    'action': 'PUT_ASSIGNED',
                    'quantity': position.quantity,
                    'price': float(position.strike_price)
                })
                
                stock_position = Position(
                    symbol=position.symbol,
                    entry_price=position.strike_price,
                    quantity=position.quantity,
                    position_type=PositionType.STOCK,
                    expiration=None,
                    strike_price=None,
                    premium_received=position.premium_received
                )
                
                self.positions.remove(position)
                self.positions.append(stock_position)
                
                self.current_capital -= position.strike_price * Decimal(str(position.quantity))
                logger.info(f"ASSIGNED (PUT): {position.symbol} at {position.strike_price}. Capital: {self.current_capital}")
            else:
                # Expiration (PUT)
                self.trades.append({
                    'date': date,
                    'symbol': position.symbol,
                    'action': 'PUT_EXPIRED',
                    'quantity': position.quantity,
                    'price': 0
                })
                self.positions.remove(position)
                logger.info(f"EXPIRED (PUT): {position.symbol}. Full profit on premium.")
        
        elif position.position_type == PositionType.COVERED_CALL:
            if current_price > float(position.strike_price):
                # Assignment (CALL) - Stock called away
                self.trades.append({
                    'date': date,
                    'symbol': position.symbol,
                    'action': 'CALL_ASSIGNED',
                    'quantity': position.quantity,
                    'price': float(position.strike_price)
                })
                
                # Find and remove underlying stock position
                stock_to_remove = None
                for p in self.positions:
                    if p.symbol == position.symbol and p.position_type == PositionType.STOCK:
                        if p.quantity >= position.quantity: # Assuming sufficient coverage
                            stock_to_remove = p
                            break
                
                if stock_to_remove:
                    self.positions.remove(stock_to_remove)
                    # If partial assignment logic needed, we'd reduce quantity instead of removing
                    # For simplicity, assuming 1:1 matching for now
                
                self.positions.remove(position)
                self.current_capital += position.strike_price * Decimal(str(position.quantity))
                logger.info(f"ASSIGNED (CALL): {position.symbol} at {position.strike_price}. Stocks sold. Capital: {self.current_capital}")
            else:
                # Expiration (CALL)
                self.trades.append({
                    'date': date,
                    'symbol': position.symbol,
                    'action': 'CALL_EXPIRED',
                    'quantity': position.quantity,
                    'price': 0
                })
                self.positions.remove(position)
                logger.info(f"EXPIRED (CALL): {position.symbol}. Kept shares, full profit on premium.")

    def _try_sell_covered_call(self, date: datetime, position: Position):
        """Try to sell a covered call against stock position"""
        # Check if we already have a covered call for this position
        # Simplified check: if any CC exists for this symbol
        existing_cc = any(p.symbol == position.symbol and p.position_type == PositionType.COVERED_CALL for p in self.positions)
        if existing_cc:
            return

        # logger.debug(f"Trying to sell covered call for {position.symbol} on {date}")
        chain = self.data_provider.get_historical_options(
            position.symbol, 
            date,
            self._get_next_monthly_expiration(date)
        )
        
        current_price = self._get_current_price(position.symbol, date)
        if current_price is None:
            return
            
        suitable_call = None
        # Simple logic for CC: Sell 5-10% OTM
        for option in chain:
            if 'C' not in option['id']:  # Skip puts
                continue
                
            strike = float(option['strike'])
            strike_ratio = strike / current_price
            
            if 1.05 <= strike_ratio <= 1.10:
                suitable_call = option
                break
                
        if suitable_call:
            self._sell_call(date, suitable_call, position)
            
    def _sell_call(self, date: datetime, call: Dict, stock_position: Position):
        """Sell a covered call"""
        logger.debug(f"Selling call for {stock_position.symbol} on {date}: {call}")
        premium = Decimal(str(call['bid']))
        quantity = Decimal(str(stock_position.quantity)) // Decimal('100')  # Number of contracts
        
        if quantity == 0:
            return

        self.trades.append({
            'date': date,
            'symbol': stock_position.symbol,
            'action': 'SELL_CALL',
            'quantity': int(quantity),
            'price': float(premium),
            'option_id': call['id']
        })
        
        position = Position(
            symbol=stock_position.symbol,
            entry_price=Decimal(str(call['strike'])),
            quantity=int(quantity * Decimal('100')),
            position_type=PositionType.COVERED_CALL, # Corrected type
            expiration=self._extract_expiration(call['id']),
            strike_price=Decimal(str(call['strike'])),
            premium_received=premium
        )
        self.positions.append(position)
        
        self.current_capital += premium * quantity * Decimal('100')
        logger.info(f"SELL CC: {stock_position.symbol} Strike={call['strike']} Exp={call['expiration']} Premium={premium}")
        
    def _get_current_price(self, symbol: str, date: datetime) -> float:
        """Get the current price for a symbol"""
        # logger.debug(f"Fetching current price for {symbol} on {date}")
        df = self.data_provider.get_price_history(symbol, date, date + timedelta(days=1))
        if df.empty:
            # logger.debug(f"No price data available for {symbol} on {date}")
            return None
        return float(df['close'].iloc[-1])
        
    def _extract_expiration(self, option_id: str) -> datetime:
        """Extract expiration date from option ID"""
        try:
             # Regex or strict parsing:
             import re
             match = re.search(r'(\d{6})[CP]', option_id)
             if match:
                 date_str = match.group(1)
                 return datetime.strptime(f"20{date_str}", "%Y%m%d")
        except Exception:
            pass
            
        logger.warning(f"Could not parse expiration from {option_id}")
        return datetime.now() + timedelta(days=30) # Fallback
        
    def _get_next_monthly_expiration(self, date: datetime) -> datetime:
        """Get next monthly option expiration"""
        # Simple logic: 3rd Friday of next month
        next_month = date.replace(day=1) + timedelta(days=32)
        next_month = next_month.replace(day=1)
        
        friday_count = 0
        current = next_month
        while friday_count < 3:
            if current.weekday() == 4:  # Friday
                friday_count += 1
            if friday_count < 3:
                current += timedelta(days=1)
        
        return current
        
    def _record_portfolio_value(self, date: datetime):
        """Record daily portfolio value"""
        total_value = float(self.current_capital)
        
        for position in self.positions:
            if position.position_type == PositionType.STOCK:
                current_price = self._get_current_price(position.symbol, date)
                if current_price:
                    total_value += current_price * float(position.quantity)
                    
        self.daily_portfolio_value.append({
            'date': date,
            'portfolio_value': total_value
        })
        # logger.debug(f"Recorded portfolio value on {date}: {total_value}")
        
    def _generate_per_stock_summary(self) -> Dict:
        """Generate summary metrics per stock"""
        summary = {}
        
        # Initialize for all watchlist symbols
        for stock_config in self.config.watchlist:
            summary[stock_config.symbol] = {
                'total_premium': Decimal('0'),
                'stock_cost': Decimal('0'),
                'stock_revenue': Decimal('0'),
                'current_shares': 0,
                'status': 'EXITED'
            }
            
        # Process trades
        for trade in self.trades:
            symbol = trade['symbol']
            if symbol not in summary:
                continue
                
            action = trade['action']
            price = Decimal(str(trade['price']))
            quantity = Decimal(str(trade['quantity']))
            
            if action in ['SELL_PUT', 'SELL_CALL']:
                # Premium received (per share * 100 shares per contract * number of contracts)
                # Note: trade['quantity'] for options seems to be number of contracts in _sell_put/call
                # But let's double check.
                # In _sell_put: quantity = Decimal('1') (contract). self.current_capital += premium * Decimal('100').
                # So premium is per share.
                # Trade dict stores: 'quantity': int(quantity) (contracts), 'price': float(premium) (per share).
                total_premium = price * quantity * Decimal('100')
                summary[symbol]['total_premium'] += total_premium
                
            elif action == 'PUT_ASSIGNED':
                # Stock bought
                # quantity is shares
                cost = price * quantity
                summary[symbol]['stock_cost'] += cost
                summary[symbol]['current_shares'] += int(quantity)
                summary[symbol]['status'] = 'HOLDING'
                
            elif action == 'CALL_ASSIGNED':
                # Stock sold
                revenue = price * quantity
                summary[symbol]['stock_revenue'] += revenue
                summary[symbol]['current_shares'] -= int(quantity)
                if summary[symbol]['current_shares'] <= 0:
                    summary[symbol]['status'] = 'EXITED'
                    summary[symbol]['current_shares'] = 0 # Safety
                    
        # Calculate final metrics
        final_summary = {}
        for symbol, data in summary.items():
            shares = data['current_shares']
            premium = data['total_premium']
            cost = data['stock_cost']
            revenue = data['stock_revenue']
            
            if shares > 0:
                # Holding
                # Cost Basis = (Total Cost - Premiums - Realized Stock Profit?) 
                # Simplified: Adjusted Cost Basis = Total Cost - Total Premiums.
                # (Purchase Price - Premium Collected) from user prompt.
                # If we traded multiple times, 'Purchase Price' is ambiguous. 
                # Let's use (Net Spend / Shares). Net Spend = Stock Cost - Stock Revenue - Premiums.
                # Wait, if we sold some stock, we realized some profit/loss.
                # Standard Adjusted Cost Basis usually applies to currently held shares.
                # Let's use: (Stock Cost - Stock Revenue - Premium) / Shares
                # If negative, we have a negative cost basis (free shares + profit).
                net_cost = cost - revenue - premium
                cost_basis_per_share = net_cost / Decimal(str(shares))
                
                final_summary[symbol] = {
                    'status': 'HOLDING',
                    'shares': shares,
                    'adjusted_cost_basis': float(cost_basis_per_share),
                    'total_premium': float(premium)
                }
            else:
                # Exited
                # Premium Collected (Total Profit)
                # User asked: "if exited. give me the premium collected".
                # Interpreting as Total Realized PnL because "premium collected" alone is just `premium`.
                # I will provide both.
                net_pnl = (revenue - cost) + premium
                
                final_summary[symbol] = {
                    'status': 'EXITED',
                    'total_premium': float(premium),
                    'net_pnl': float(net_pnl)
                }
                
        return final_summary

    def _generate_backtest_results(self) -> Dict:
        """Generate final backtest results"""
        if not self.daily_portfolio_value:
            return {}
            
        df = pd.DataFrame(self.daily_portfolio_value)
        df['returns'] = df['portfolio_value'].pct_change()
        
        total_return = (df['portfolio_value'].iloc[-1] - float(self.initial_capital)) / float(self.initial_capital)
        
        days = (self.end_date - self.start_date).days
        if days > 0:
            annual_return = (1 + total_return) ** (365/days) - 1
        else:
            annual_return = 0
        
        excess_returns = df['returns'] - 0.02/252
        if excess_returns.std() != 0:
            sharpe_ratio = excess_returns.mean() / excess_returns.std() * (252 ** 0.5)
        else:
            sharpe_ratio = 0
        
        rolling_max = df['portfolio_value'].cummax()
        drawdowns = (df['portfolio_value'] - rolling_max) / rolling_max
        max_drawdown = drawdowns.min()
        
        # Calculate win rate based on trade outcomes
        # We consider a 'win' if we kept the premium (expired) or sold stock (call assigned)
        # Note: Call assigned could technically be a loss if stock dropped below net cost, 
        # but in standard Wheel, it's the target exit.
        completed_trades = [t for t in self.trades if t['action'] in ['PUT_EXPIRED', 'CALL_EXPIRED', 'CALL_ASSIGNED']]
        winning_trades = len(completed_trades) # For now, assume all these are "wins" in terms of strategy execution
        
        total_closed_actions = len([t for t in self.trades if t['action'] in ['PUT_EXPIRED', 'CALL_EXPIRED', 'CALL_ASSIGNED', 'PUT_ASSIGNED']])
        
        win_rate = 0.0
        if total_closed_actions > 0:
            # Note: PUT_ASSIGNED is not a 'loss', it's a continuation. But for win rate stats, 
            # we often only count the "premium capture" events as wins.
            # If we treat PUT_ASSIGNED as "neutral" or "open", we should exclude it from denominator?
            # No, usually people want to know how often they keep the premium.
            win_rate = winning_trades / total_closed_actions
            
        total_trades = len(self.trades)
        
        # Generate per stock summary
        stock_summary = self._generate_per_stock_summary()
        
        results = {
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'final_capital': float(self.current_capital),
            'stock_summary': stock_summary
        }
        # Final portfolio value
        results['final_portfolio_value'] = df['portfolio_value'].iloc[-1]
        
        logger.info(f"Backtest Results: {results}")
        return results

    def run_backtest(self):
        """Run the wheel strategy backtest"""
        logger.info(f"Starting backtest from {self.start_date} to {self.end_date}")
        logger.info(f"Initial capital: ${self.initial_capital:,.2f}")
        
        current_date = self.start_date
        while current_date <= self.end_date:
            if self._is_trading_day(current_date):
                self._process_trading_day(current_date)
            current_date += timedelta(days=1)
            
        return self._generate_backtest_results()
    
    def _process_trading_day(self, date: datetime):
        """Process a single trading day"""
        self._manage_existing_positions(date)
        
        for stock in self.config.watchlist:
            if self._can_enter_new_position(stock):
                self._find_entry_opportunity(date, stock)
                
        self._record_portfolio_value(date)
    
    def _manage_existing_positions(self, date: datetime):
        """Manage existing positions (roll options, handle assignments)"""
        for position in self.positions[:]:
            if position.position_type in [PositionType.CASH_SECURED_PUT, PositionType.COVERED_CALL]:
                if position.expiration and date >= position.expiration:
                    self._handle_option_expiration(date, position)
            elif position.position_type == PositionType.STOCK:
                self._try_sell_covered_call(date, position)
    
    def _find_entry_opportunity(self, date: datetime, stock: StockConfig):
        """Look for new put-selling opportunities"""
        price_data = self._get_historical_prices(stock.symbol, date)
        if price_data.empty:
            return
            
        chain = self.data_provider.get_historical_options(
            symbol=stock.symbol,
            date=date,
            expiration=self._get_next_monthly_expiration(date)
        )
        
        put = self.strategy_analyzer.analyze_put_opportunity(
            symbol=stock.symbol,
            price_data=price_data,
            options_chain=chain
        )
        
        if put:
            self._sell_put(date, put, stock)
