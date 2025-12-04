# 🎡 Wheeler - Automated Wheel Strategy Options Bot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

An automated options trading bot that implements the **Wheel Strategy** on [Alpaca Markets](https://alpaca.markets/). Features include backtesting, paper trading, live trading, RSI-based entries, and intelligent position management.

![Wheeler Bot Demo](https://img.shields.io/badge/status-active-success.svg)

---

## ⚡ Quick Start (5 minutes)

```bash
# Clone
git clone https://github.com/dgiliver/wheeler.git
cd wheeler

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Alpaca API keys

# Run (paper trading)
python src/main.py --config config/wheel_10k_paper.yml
```

---

## 🎡 What is the Wheel Strategy?

The Wheel is a systematic, income-generating options strategy:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   1. SELL CASH-SECURED PUT (CSP)                               │
│      ↓                                                          │
│   ┌─────────────────┐         ┌─────────────────┐              │
│   │ Expires OTM     │         │ Assigned Stock  │              │
│   │ Keep Premium 💰 │         │ Keep Premium 💰 │              │
│   └────────┬────────┘         └────────┬────────┘              │
│            │                           │                        │
│            ↓                           ↓                        │
│   [Repeat Step 1]            2. SELL COVERED CALL (CC)         │
│                                        ↓                        │
│                              ┌─────────────────┐               │
│                              │ Expires OTM     │               │
│                              │ Keep Premium 💰 │               │
│                              │ Keep Stock      │               │
│                              └────────┬────────┘               │
│                                       │                         │
│                              [Repeat Step 2]                    │
│                                       OR                        │
│                              ┌─────────────────┐               │
│                              │ Called Away     │               │
│                              │ Keep Premium 💰 │               │
│                              │ Profit on Stock │               │
│                              └────────┬────────┘               │
│                                       │                         │
│                              [Back to Step 1]                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why it works:**
- Collect premium consistently
- Buy stocks at a discount (via put assignment)
- Sell stocks at a profit (via call assignment)
- Works best on stable, dividend-paying stocks you want to own

---

## 📋 Requirements

- **Python 3.11+**
- **Alpaca Markets account** (free) - [Sign up here](https://alpaca.markets/)
- **Options trading enabled** on your Alpaca account
- **$2,000+ account balance** (Alpaca minimum for options)

---

## 🛠️ Installation

### Option 1: Local Development

```bash
# Clone the repository
git clone https://github.com/dgiliver/wheeler.git
cd wheeler

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example environment file
cp .env.example .env
```

### Option 2: Docker (Coming Soon)

```bash
docker pull dgiliver/wheeler
docker run -e ALPACA_PAPER_API_KEY=xxx wheeler
```

---

## 🔑 Configuration

### 1. API Keys (`.env`)

```bash
# Paper Trading (recommended to start)
ALPACA_PAPER_API_KEY=PKxxxxxxxxxxxxxxxxxx
ALPACA_PAPER_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets

# Live Trading (when ready)
ALPACA_LIVE_API_KEY=AKxxxxxxxxxxxxxxxxxx
ALPACA_LIVE_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ALPACA_LIVE_BASE_URL=https://api.alpaca.markets
```

### 2. Strategy Config (`config/wheel_10k_paper.yml`)

```yaml
environment: paper  # 'paper' or 'live'

# Account limits
max_capital: 10000            # Max capital to use (even if account has more)
max_contracts_per_symbol: 1   # Limit contracts per stock

# Entry conditions
rsi_period: 14
rsi_threshold: 45             # Only sell puts when RSI < 45 (oversold)

# Take profit
take_profit_pct: 0.50         # Close at 50% profit

# Your watchlist
watchlist:
  - symbol: PLTR              # Palantir
    max_position_size: 0.25   # 25% of capital max
    min_strike_delta: 0.25    # Target delta range
    max_strike_delta: 0.35
    min_days_to_expiry: 30    # DTE range
    max_days_to_expiry: 45

  - symbol: F                 # Ford
    max_position_size: 0.20
    min_strike_delta: 0.25
    max_strike_delta: 0.35
```

### Key Parameters Explained

| Parameter | Description | Recommended |
|-----------|-------------|-------------|
| `rsi_threshold` | Only enter when RSI below this | 40-50 |
| `min_strike_delta` | Minimum option delta | 0.20-0.30 |
| `max_strike_delta` | Maximum option delta | 0.30-0.40 |
| `min_days_to_expiry` | Minimum DTE | 25-35 |
| `max_days_to_expiry` | Maximum DTE | 45-60 |
| `take_profit_pct` | Close position at X% profit | 0.50-0.65 |

---

## 🚀 Usage

### Paper Trading (Recommended First)

```bash
# Start the bot
python src/main.py --config config/wheel_10k_paper.yml

# Watch the logs
tail -f wheel_bot.log
```

### Backtesting

Test how the strategy would have performed historically:

```bash
# Basic backtest
python -m src.backtesting.run_backtest \
  --start-date 2023-01-01 \
  --end-date 2024-01-01 \
  --capital 10000 \
  --rsi 45

# Comprehensive backtest with multiple configurations
python run_fast_backtest.py
```

### Live Trading

⚠️ **Only after extensive paper trading!**

1. Change `environment: live` in your config
2. Ensure `ALPACA_LIVE_*` keys are set
3. Start with small position sizes
4. Monitor closely for the first few weeks

---

## ☁️ Deploy to AWS (Run 24/7)

Run the bot continuously on AWS EC2 for ~$0/month (free tier).

### Quick Deploy

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ec2-user@your-ec2-ip

# Setup
sudo dnf update -y
sudo dnf install python3.11 python3.11-pip git -y
git clone https://github.com/dgiliver/wheeler.git
cd wheeler
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create startup script
cat > start_bot.sh << 'EOF'
#!/bin/bash
cd /home/ec2-user/wheeler
source .venv/bin/activate
export ALPACA_PAPER_API_KEY="your_key"
export ALPACA_PAPER_API_SECRET="your_secret"
export ALPACA_PAPER_BASE_URL="https://paper-api.alpaca.markets"
exec python3 src/main.py --config config/wheel_10k_paper.yml
EOF
chmod +x start_bot.sh

# Create systemd service
sudo tee /etc/systemd/system/wheeler.service << 'EOF'
[Unit]
Description=Wheeler Bot
After=network.target

[Service]
Type=simple
User=ec2-user
ExecStart=/home/ec2-user/wheeler/start_bot.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Start
sudo systemctl daemon-reload
sudo systemctl enable wheeler
sudo systemctl start wheeler

# Check status
sudo systemctl status wheeler
journalctl -u wheeler -f
```

For secure secrets management with AWS Secrets Manager, see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## 📊 How It Works

### Entry Logic (Selling Puts)

```python
def should_enter():
    return (
        RSI < threshold          # Stock is oversold
        and delta in range       # Option has target delta
        and DTE in range         # 30-45 days to expiry
        and liquidity_ok         # Good volume/spread
        and within_position_limit # Not overexposed
    )
```

### Exit Logic (Covered Calls)

```python
def should_sell_call():
    return (
        own_100_shares           # Assigned from put
        and strike > cost_basis  # Ensure profit if called
        and delta in range       # Target delta
    )
```

### Position Management

- **Take Profit**: Closes positions at 50-65% profit
- **Rolling**: Automatically rolls options near expiry if profitable
- **Assignment**: Gracefully handles stock assignment

---

## 📁 Project Structure

```
wheeler/
├── config/                     # Strategy configurations
│   ├── wheel_10k_paper.yml  # Paper trading config ($10k)
│   └── wheel_strategy_OLD.yml  # Legacy config
├── src/
│   ├── analysis/               # Strategy logic
│   │   └── strategy_analyzer.py
│   ├── backtesting/            # Historical testing
│   │   ├── historical_data.py
│   │   ├── wheel_backtester.py
│   │   └── run_backtest.py
│   ├── config/                 # Settings models
│   │   └── settings.py
│   ├── managers/               # Account management
│   │   └── account_manager.py
│   ├── models/                 # Data models
│   │   ├── alpaca_models.py    # API models
│   │   └── position.py
│   ├── services/               # External APIs
│   │   └── alpaca_service.py
│   ├── main.py                 # Entry point
│   └── wheel_bot.py            # Main bot logic
├── tests/                      # Test suite
├── .env.example                # Example environment
├── .pre-commit-config.yaml     # Code quality hooks
├── requirements.txt            # Dependencies
└── README.md
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test
pytest tests/test_strategy_analyzer.py -v
```

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Install pre-commit hooks (`pre-commit install`)
4. Make your changes
5. Run tests (`pytest tests/ -v`)
6. Commit (`git commit -m 'Add amazing feature'`)
7. Push (`git push origin feature/amazing-feature`)
8. Open a Pull Request

---

## 📈 Performance

Backtesting results on select stocks (2022-2024):

| Stock | Annual Return | Max Drawdown | Win Rate |
|-------|--------------|--------------|----------|
| PLTR  | ~15-25%      | ~12%         | ~75%     |
| F     | ~10-18%      | ~8%          | ~80%     |
| SOFI  | ~12-22%      | ~15%         | ~72%     |

*Past performance does not guarantee future results.*

---

## ❓ FAQ

**Q: How much money do I need?**
A: Alpaca requires $2,000 minimum for options. The bot works best with $5,000-$25,000.

**Q: Is this safe?**
A: All trading involves risk. The wheel strategy is considered relatively conservative for options, but you can still lose money. Always paper trade first.

**Q: What stocks work best?**
A: Stable stocks with good premiums: PLTR, F, SOFI, INTC, BAC, AMD. Avoid meme stocks and highly volatile names.

**Q: How often does it trade?**
A: Depends on market conditions. Typically 1-5 trades per week during volatile periods, fewer in calm markets.

**Q: Can I run multiple configs?**
A: Yes, run separate instances with different config files.

---

## ⚠️ Disclaimer

**IMPORTANT: This software is for educational purposes only.**

- Trading options involves substantial risk of loss
- Past performance does not guarantee future results
- The authors are NOT financial advisors
- You are solely responsible for your trading decisions
- Always paper trade extensively before using real money
- Never trade money you can't afford to lose

By using this software, you acknowledge these risks and agree that the authors bear no responsibility for any financial losses.

---

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

---

## ⭐ Star History

If you find this useful, please give it a star! ⭐

---

<p align="center">
  Made with ❤️ for the options trading community
</p>
