from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Optional, Union
import logging
import requests
import json
import yfinance as yf
import time

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import AssetClass
from alpaca.trading.models import Position as AlpacaPosition

from src.config.settings import AlpacaConfig
from src.models.position import Position, PositionType
from src.models.alpaca_models import (
    OptionOrderRequest, OrderSide, OrderType, TimeInForce, 
    OptionChainResponse, OptionSnapshot
)

logger = logging.getLogger(__name__)

class AlpacaService:
    def __init__(self, config: AlpacaConfig):
        self.config = config
        self.base_url = "https://data.alpaca.markets"
        
        # Initialize Official SDK Clients for Trading
        self.trading_client = TradingClient(config.api_key, config.api_secret, paper=(config.environment == 'paper'))
        
        self.headers = {
            "APCA-API-KEY-ID": config.api_key,
            "APCA-API-SECRET-KEY": config.api_secret,
            "Content-Type": "application/json"
        }
        
        self.trading_url = config.base_url
    
    def _make_request(self, method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
        """Make a request to the Alpaca API with retry logic"""
        base_url = self.trading_url if endpoint.startswith('/v2') else self.base_url
        url = f"{base_url}{endpoint}"
        
        logger.debug(f"Making request: {method} {url}")
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=data
                )
                
                if response.status_code == 429:
                    logger.warning(f"Rate limited (429). Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                
                if response.status_code == 404:
                    if '/positions/' in endpoint or '/bars' in endpoint:
                        logger.debug(f"No data found for {endpoint}")
                        return None
                    else:
                        logger.error(f"API error: {response.status_code} - {response.text}")
                        return None
                
                if not response.ok:
                    logger.error(f"API error: {response.status_code} - {response.text}")
                    return None
                    
                return response.json() if response.content else None
                
            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
        
        return None
    
    def get_account(self) -> Dict:
        """Get account information"""
        try:
            account = self.trading_client.get_account()
            # Convert to dict structure expected by bot
            return {
                'id': str(account.id),
                'portfolio_value': account.portfolio_value,
                'buying_power': account.buying_power,
                'cash': account.cash,
                'currency': account.currency,
                'equity': account.equity,
                'daytrade_count': account.daytrade_count,
                'pattern_day_trader': account.pattern_day_trader
            }
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return None
    
    def get_positions(self) -> List[Position]:
        """Get all open positions"""
        try:
            alpaca_positions = self.trading_client.get_all_positions()
            
            result = []
            for pos in alpaca_positions:
                asset_class = pos.asset_class
                symbol = pos.symbol
                qty = int(float(pos.qty))
                avg_entry_price = Decimal(str(pos.avg_entry_price))
                
                if asset_class == AssetClass.US_OPTION:
                    try:
                        # Parse option symbol to extract details
                        if len(symbol) < 15:
                            logger.warning(f"Option symbol too short: {symbol}")
                            continue
                            
                        suffix = symbol[-15:]
                        underlying = symbol[:-15]
                        
                        date_str = suffix[:6]
                        expiration = datetime.strptime(date_str, "%y%m%d")
                        type_char = suffix[6]
                        strike = Decimal(suffix[7:]) / 1000
                        
                        pos_type = PositionType.OPTION
                        if qty < 0:
                            if type_char == 'P':
                                pos_type = PositionType.CASH_SECURED_PUT
                            elif type_char == 'C':
                                pos_type = PositionType.COVERED_CALL
                        
                        # Create position with explicit datetime.now() - no SDK attribute access
                        entry_dt = datetime.now()
                        
                        new_position = Position(
                            symbol=underlying,
                            entry_price=avg_entry_price,
                            quantity=qty,
                            position_type=pos_type,
                            expiration=expiration,
                            strike_price=strike,
                            premium_received=avg_entry_price * abs(qty) * 100,
                            entry_date=entry_dt,
                            contracts=abs(qty)
                        )
                        result.append(new_position)
                        logger.debug(f"Parsed option: {underlying} {pos_type} strike={strike}")
                    except Exception as e:
                        logger.error(f"Error parsing option {symbol}: {e}", exc_info=True)
                        continue
                else:
                    result.append(Position(
                        symbol=symbol,
                        entry_price=avg_entry_price,
                        quantity=qty,
                        position_type=PositionType.STOCK,
                        expiration=None,
                        strike_price=None,
                        premium_received=Decimal('0'),
                        entry_date=datetime.now()  # Alpaca SDK doesn't provide created_at for positions
                    ))
                    
            return result
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol"""
        try:
            try:
                pos = self.trading_client.get_open_position(symbol)
            except Exception:
                return None
                
            qty = int(float(pos.qty))
            avg_entry_price = Decimal(str(pos.avg_entry_price))
            
            return Position(
                symbol=pos.symbol,
                entry_price=avg_entry_price,
                quantity=qty,
                position_type=PositionType.STOCK,
                expiration=None,
                strike_price=None,
                premium_received=Decimal('0'),
                entry_date=datetime.now()  # Alpaca SDK doesn't provide created_at
            )
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    def close_position(self, symbol: str) -> bool:
        """Close a position"""
        try:
            self.trading_client.close_position(symbol)
            return True
        except Exception as e:
            logger.error(f"Error closing position {symbol}: {e}")
            return False
    
    def get_price_history(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Get historical price data using Yahoo Finance"""
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end)
            
            if df.empty:
                logger.warning(f"No price data found for {symbol} on Yahoo Finance")
                return pd.DataFrame()
                
            df.columns = [col.lower() for col in df.columns]
            return df[['open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            logger.error(f"Error getting Yahoo Finance data for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_option_chain(self, symbol: str, expiration: datetime, min_dte: int = None, max_dte: int = None) -> list:
        """
        Get option chain using Pydantic models for validation/unpacking.
        
        If min_dte/max_dte are provided, returns options within that DTE range.
        Otherwise, tries to match the exact expiration date.
        
        Note: Alpaca's snapshots endpoint doesn't filter by expiration server-side,
        so we must paginate and filter client-side.
        """
        try:
            target_date = expiration.strftime("%Y-%m-%d")
            today = datetime.now()
            
            # Calculate acceptable date range
            if min_dte is not None and max_dte is not None:
                min_exp = (today + timedelta(days=min_dte)).strftime("%Y-%m-%d")
                max_exp = (today + timedelta(days=max_dte)).strftime("%Y-%m-%d")
                logger.debug(f"Fetching option chain for {symbol} with DTE {min_dte}-{max_dte} ({min_exp} to {max_exp})")
            else:
                min_exp = target_date
                max_exp = target_date
                logger.debug(f"Fetching option chain for {symbol} expiring {target_date}")
            
            quotes = []
            next_page_token = None
            endpoint = f"/v1beta1/options/snapshots/{symbol}"
            pages_fetched = 0
            max_pages = 20  # Limit pagination to avoid excessive API calls
            
            while pages_fetched < max_pages:
                params = {"limit": 1000}
                if next_page_token:
                    params["page_token"] = next_page_token
                    time.sleep(0.2)
                
                response_data = self._make_request("GET", endpoint, params=params)
                if not response_data:
                    break
                
                pages_fetched += 1
                
                # Unpack using Pydantic model
                try:
                    chain_response = OptionChainResponse(**response_data)
                except Exception as e:
                    logger.error(f"Failed to parse API response with Pydantic: {e}")
                    break
                    
                snapshots = chain_response.snapshots
                if not snapshots:
                    break
                
                # Track if we've gone past our target date range
                earliest_exp_in_page = None
                
                for contract_symbol, snapshot in snapshots.items():
                    try:
                        # Parse expiration from symbol
                        if len(contract_symbol) < 15: continue
                        suffix = contract_symbol[-15:]
                        date_str = suffix[:6]
                        contract_date = datetime.strptime(date_str, "%y%m%d").strftime("%Y-%m-%d")
                        
                        # Track earliest expiration in this page
                        if earliest_exp_in_page is None or contract_date < earliest_exp_in_page:
                            earliest_exp_in_page = contract_date
                        
                        # Filter by date range
                        if contract_date < min_exp:
                            continue  # Too soon
                        if contract_date > max_exp:
                            continue  # Too far out
                        
                        type_char = suffix[6]
                        option_type = 'call' if type_char == 'C' else 'put'
                        strike_price = float(suffix[7:]) / 1000.0
                        
                        # Extract data from Pydantic model
                        if not snapshot.latestQuote: continue
                        
                        quote = snapshot.latestQuote
                        greeks = snapshot.greeks
                        
                        quotes.append({
                            'id': contract_symbol,
                            'symbol': contract_symbol,
                            'type': option_type,
                            'strike': strike_price,
                            'bid': quote.bid_price,
                            'ask': quote.ask_price,
                            'volume': snapshot.dailyBar.volume if snapshot.dailyBar else 0,
                            'open_interest': snapshot.openInterest or 0,
                            'implied_volatility': greeks.implied_volatility if greeks else 0.0,
                            'delta': greeks.delta if greeks else 0.0
                        })
                    except Exception:
                        continue
                
                next_page_token = chain_response.next_page_token
                if not next_page_token:
                    break
                    
                # Optimization: If we've found enough quotes and the page's earliest
                # expiration is past our target range, we can stop early
                if len(quotes) > 0 and earliest_exp_in_page and earliest_exp_in_page > max_exp:
                    logger.debug(f"Stopping pagination - past target date range (page earliest: {earliest_exp_in_page})")
                    break
            
            logger.debug(f"Found {len(quotes)} valid quotes for {symbol} (fetched {pages_fetched} pages)")
            return quotes
            
        except Exception as e:
            logger.error(f"Error getting option chain for {symbol}: {e}", exc_info=True)
            return []
    
    def place_option_order(self, contract_id: str, side: str, quantity: int, limit_price: Optional[Decimal] = None) -> Dict:
        """Place an option order via the standard /v2/orders endpoint"""
        try:
            side_enum = OrderSide.SELL if side.lower() == 'sell' else OrderSide.BUY
            
            # Use limit order if price provided, otherwise market
            order_type = OrderType.LIMIT if limit_price else OrderType.MARKET
            
            # Build payload for Alpaca API
            payload = {
                "symbol": contract_id,  # Option contract symbol (e.g., SPY251219P00670000)
                "qty": str(quantity),
                "side": side_enum.value,
                "type": order_type.value,
                "time_in_force": TimeInForce.DAY.value,
            }
            
            if limit_price:
                payload["limit_price"] = str(limit_price)
            
            logger.info(f"Placing option order: {payload}")
            
            response = self._make_request("POST", "/v2/orders", data=payload)
            if response:
                logger.info(f"Order placed successfully: {response.get('id', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"Error placing option order: {e}", exc_info=True)
            return None

    def get_option_positions(self) -> List[Dict]:
        return self._make_request("GET", "/v2/options/positions") or []
    
    def exercise_option(self, position_id: str) -> bool:
        response = self._make_request("POST", f"/v2/options/positions/{position_id}/exercise")
        return response is not None
    
    def get_orders(self, status: str = "open") -> List[Dict]:
        try:
            req = GetOrdersRequest(status=status)
            orders = self.trading_client.get_orders(req)
            return [o.dict() if hasattr(o, 'dict') else o for o in orders]
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    def cancel_order(self, order_id: str) -> bool:
        try:
            self.trading_client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_account_history(self, start: datetime = None, end: datetime = None) -> List[Dict]:
        params = {}
        if start: params["start"] = start.isoformat() + 'Z'
        if end: params["end"] = end.isoformat() + 'Z'
        return self._make_request("GET", "/v2/account/activities", params=params) or []
