import logging
import math
import time  # Added import
from datetime import datetime, timedelta

import pandas as pd
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from scipy.stats import norm

logger = logging.getLogger(__name__)


class AlpacaHistoricalDataProvider:
    def __init__(self, api_key: str, api_secret: str):
        self.client = StockHistoricalDataClient(api_key, api_secret)

    def get_price_history(self, symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get historical price data for a symbol with retry logic"""
        request = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start_date, end=end_date)

        max_retries = 3
        retry_delay = 1

        for _attempt in range(max_retries):
            try:
                bars = self.client.get_stock_bars(request)

                if bars and hasattr(bars, "df"):
                    return bars.df
                return pd.DataFrame()

            except Exception as e:
                # Check for rate limit error in exception message
                error_msg = str(e).lower()
                if "429" in error_msg or "too many requests" in error_msg or "rate limit" in error_msg:
                    logger.warning(f"Rate limit hit for {symbol}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue

                logger.error(f"Error getting Alpaca price data for {symbol}: {e}")
                return pd.DataFrame()

        logger.error(f"Max retries exceeded for {symbol}")
        return pd.DataFrame()

    def get_historical_options(self, symbol: str, date: datetime, expiration: datetime) -> list[dict]:
        """Simulate historical options data since Alpaca doesn't provide historical options"""
        try:
            # Get current stock price
            price_df = self.get_price_history(symbol, date, date + timedelta(days=1))
            if price_df.empty:
                return []

            current_price = float(price_df["close"].iloc[-1])

            # Generate synthetic option chain
            strikes = [
                round(current_price * (1 + x / 100), 2)
                for x in range(-20, 21, 5)  # Strike prices from -20% to +20% in 5% increments
            ]

            options = []
            exp_str = expiration.strftime("%y%m%d")
            days_to_expiry = (expiration - date).days

            for strike in strikes:
                # Generate put option
                put_id = f"{symbol}{exp_str}P{int(strike * 1000):08d}"
                put_premium = self._calculate_option_premium(current_price, strike, days_to_expiry, True)
                put_delta = self._calculate_delta(current_price, strike, days_to_expiry, True)

                options.append(
                    {
                        "id": put_id,
                        "symbol": symbol,
                        "strike": strike,
                        "type": "put",
                        "expiration": expiration,
                        "bid": put_premium * 0.95,  # Simulate bid-ask spread
                        "ask": put_premium * 1.05,
                        "volume": 1000,  # Simulated volume
                        "open_interest": 5000,  # Simulated OI
                        "delta": put_delta,
                        "implied_volatility": 0.3,  # Simulated IV
                    }
                )

                # Generate call option
                call_id = f"{symbol}{exp_str}C{int(strike * 1000):08d}"
                call_premium = self._calculate_option_premium(current_price, strike, days_to_expiry, False)
                call_delta = self._calculate_delta(current_price, strike, days_to_expiry, False)

                options.append(
                    {
                        "id": call_id,
                        "symbol": symbol,
                        "strike": strike,
                        "type": "call",
                        "expiration": expiration,
                        "bid": call_premium * 0.95,
                        "ask": call_premium * 1.05,
                        "volume": 1000,
                        "open_interest": 5000,
                        "delta": call_delta,
                        "implied_volatility": 0.3,
                    }
                )

            return options

        except Exception as e:
            logger.error(f"Error getting Alpaca option data for {symbol}: {e}")
            return []

    def _calculate_d1(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d1 for Black-Scholes"""
        if T <= 0 or S <= 0 or K <= 0 or sigma <= 0:
            return 0
        return (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))

    def _calculate_delta(self, current_price: float, strike: float, days_to_expiry: int, is_put: bool) -> float:
        """Calculate option delta using Black-Scholes approximation"""
        T = max(1, days_to_expiry) / 365.0
        r = 0.04  # Risk-free rate assumption
        sigma = 0.3  # Implied volatility assumption

        d1 = self._calculate_d1(current_price, strike, T, r, sigma)

        if is_put:
            return norm.cdf(d1) - 1
        else:
            return norm.cdf(d1)

    def _calculate_option_premium(
        self, current_price: float, strike: float, days_to_expiry: int, is_put: bool
    ) -> float:
        """Calculate synthetic option premium using Black-Scholes"""
        T = max(1, days_to_expiry) / 365.0
        r = 0.04  # Risk-free rate
        sigma = 0.3  # Implied volatility

        d1 = self._calculate_d1(current_price, strike, T, r, sigma)
        d2 = d1 - sigma * math.sqrt(T)

        if is_put:
            price = strike * math.exp(-r * T) * norm.cdf(-d2) - current_price * norm.cdf(-d1)
        else:
            price = current_price * norm.cdf(d1) - strike * math.exp(-r * T) * norm.cdf(d2)

        return max(0.01, price)
