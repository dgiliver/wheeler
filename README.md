# Wheeler - Automated Wheel Strategy Bot

Wheeler is an automated trading bot designed to execute the "Wheel Strategy" on the Alpaca brokerage platform. It supports historical backtesting and live/paper trading execution. The bot uses technical analysis (RSI) and liquidity checks to identify optimal entry and exit points for Cash Secured Puts (CSP) and Covered Calls (CC).

## 🎡 The Wheel Strategy

The Wheel Strategy is a systematic options trading method designed to generate income from premiums.

1.  **Sell Cash-Secured Puts (CSP)**:
    *   Identify a stock you wouldn't mind owning.
    *   Sell a Put option below the current price (Out-of-the-Money).
    *   **Outcome A**: The option expires worthless. You keep the premium. Repeat.
    *   **Outcome B**: The stock drops below the strike price. You are assigned the shares. You keep the premium and now own the stock.

2.  **Sell Covered Calls (CC)**:
    *   Now that you own the stock, sell a Call option above your cost basis.
    *   **Outcome A**: The option expires worthless. You keep the premium and the stock. Repeat.
    *   **Outcome B**: The stock rises above the strike price. Your shares are called away (sold). You keep the premium and the profit from the stock sale.

3.  **Repeat**: Go back to Step 1.

**Wheeler's Implementation:**
*   **Entry**: Sells CSPs on neutral/bullish stocks when RSI indicates oversold conditions (< 30-40) and premiums meet target Delta (0.20-0.45).
*   **Risk Management**: Checks option liquidity (Open Interest, Volume, Spread) before trading. Avoids selling Calls below cost basis to prevent realized losses on stock.
*   **Management**: automatically rolls positions or accepts assignment based on logic.

## 🚀 Setup & Installation

### Prerequisites
*   Python 3.10+
*   An [Alpaca Markets](https://alpaca.markets/) account (Paper or Live).
*   API Keys from Alpaca.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/wheeler.git
    cd wheeler
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    # OR if using pyproject.toml directly
    pip install .
    ```

4.  **Environment Configuration:**
    Create a `.env` file in the root directory:
    ```bash
    touch .env
    ```
    Add your Alpaca credentials:
    ```env
    # Paper Trading Credentials
    ALPACA_PAPER_API_KEY=PKxxxxxxxxxxxxxxxx
    ALPACA_PAPER_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets

    # Live Trading Credentials (Optional)
    ALPACA_LIVE_API_KEY=AKxxxxxxxxxxxxxxxx
    ALPACA_LIVE_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ALPACA_LIVE_BASE_URL=https://api.alpaca.markets
    ```

## ⚙️ Configuration

The bot behavior is controlled by `config/wheel_strategy.yml`.

```yaml
environment: paper  # 'paper' or 'live'

default_position_size: 0.2  # Max 20% of account per position

polling:
  market_hours_interval: 60  # Check every 60 seconds
  after_hours_interval: 300
  check_premarket: true
  check_afterhours: true

watchlist:
  - symbol: SPY
    max_position_size: 0.2
    min_strike_delta: 0.30  # Target Delta for CSP
    max_strike_delta: 0.15  # Tolerance
  
  - symbol: AAPL
    max_position_size: 0.1
    min_strike_delta: 0.25
    max_strike_delta: 0.15
    min_days_to_expiry: 30
    max_days_to_expiry: 45
```

## 🖥️ Usage

### 1. Backtesting
Run a historical simulation to test how the strategy would have performed.

```bash
python -m src.backtesting.run_backtest -s 2022-01-01 -e 2022-12-31 -m 100000 --rsi 30
```

**Options:**
*   `-s`, `--start-date`: Start date (YYYY-MM-DD).
*   `-e`, `--end-date`: End date (YYYY-MM-DD).
*   `-m`, `--capital`: Initial capital (default: 100,000).
*   `--rsi`: RSI threshold for entry (default: 30).
*   `--debug`: Enable verbose logging.

### 2. Live / Paper Trading
Start the bot to trade against your Alpaca account.

```bash
python src/main.py --config config/wheel_strategy.yml
```

The bot will:
1.  Connect to Alpaca.
2.  Sync existing positions.
3.  Monitor the market during trading hours.
4.  Execute trades (Sell Puts/Calls) based on your strategy config.
5.  Log activity to `wheel_bot.log`.

## 📂 Project Structure

```
wheeler/
├── config/                 # Configuration files
│   └── wheel_strategy.yml
├── src/
│   ├── analysis/           # Technical analysis & decision logic
│   │   └── strategy_analyzer.py
│   ├── backtesting/        # Backtesting engine
│   │   ├── historical_data.py
│   │   └── wheel_backtester.py
│   ├── managers/           # Portfolio & Risk management
│   │   └── account_manager.py
│   ├── models/             # Data models (Pydantic)
│   │   ├── alpaca_models.py
│   │   └── position.py
│   ├── services/           # External API services
│   │   └── alpaca_service.py
│   ├── main.py             # Entry point for Live Bot
│   └── wheel_bot.py        # Main Bot Class
├── tests/                  # Unit & Integration tests
├── .env                    # API Keys (gitignored)
├── README.md
└── requirements.txt
```

## ⚠️ Disclaimer

**Trading options involves significant risk and is not suitable for every investor.** This software is for educational and research purposes only. It is not financial advice. The authors and contributors are not responsible for any financial losses incurred while using this software. Always test thoroughly with Paper Trading before risking real capital.

