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

### Complete Config Reference

#### Global Settings

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `environment` | string | `paper` or `live` | `paper` |
| `max_capital` | number | Max capital to use (ignores Alpaca balance above this) | `10000` |
| `max_contracts_per_symbol` | number | Safety limit per stock | `1` |
| `rsi_threshold` | number | RSI must be below this to enter | `45` |
| `take_profit_pct` | number | Close position when this % of max profit reached | `0.50` |
| `default_position_size` | number | Default % of capital per position | `0.25` |

#### Per-Symbol Settings (Watchlist)

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `symbol` | string | Stock ticker | `PLTR` |
| `max_position_size` | number | Max % of capital for this stock | `0.25` |
| `min_strike_delta` | number | Minimum delta for option selection | `0.25` |
| `max_strike_delta` | number | Maximum delta for option selection | `0.35` |
| `min_days_to_expiry` | number | Minimum days until expiration | `25` |
| `max_days_to_expiry` | number | Maximum days until expiration | `45` |
| `is_high_iv` | boolean | Flag for high volatility stocks | `true` |

#### Polling Settings

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `market_hours_interval` | number | Seconds between checks during market hours | `60` |
| `after_hours_interval` | number | Seconds between checks after hours | `300` |
| `check_premarket` | boolean | Monitor pre-market (4 AM - 9:30 AM ET) | `false` |
| `check_afterhours` | boolean | Monitor after-hours (4 PM - 8 PM ET) | `false` |

---

## 📈 Understanding the Strategy

### RSI (Relative Strength Index)

RSI measures whether a stock is **overbought** or **oversold** on a scale of 0-100.

```
RSI < 30  → Oversold (stock may be undervalued) ✅ Strong buy signal
RSI 30-45 → Moderately oversold ✅ Good entry zone
RSI 45-55 → Neutral ⚠️ Proceed with caution
RSI 55-70 → Moderately overbought ❌ Avoid new positions
RSI > 70  → Overbought (stock may be overvalued) ❌ Don't enter
```

**How Wheeler uses RSI:**
- Only sells puts when RSI < `rsi_threshold`
- Default threshold is 45 (moderate, more opportunities)
- Lower threshold (30-35) = fewer but higher-conviction entries
- Higher threshold (45-50) = more entries in trending markets

### Delta (Option Greek)

Delta measures how much an option's price moves relative to the stock.

```
Delta 0.50 = ATM (At The Money) - highest premium, 50% assignment chance
Delta 0.30 = OTM (Out of Money) - moderate premium, 30% assignment chance ✅
Delta 0.20 = Far OTM - lower premium, 20% assignment chance
Delta 0.10 = Very far OTM - minimal premium, 10% assignment chance
```

**For puts (negative delta):**
- `-0.30 delta` = 30% chance of assignment
- Strike is ~30% probability of being ITM at expiration

**Recommended ranges:**
| Strategy | Delta Range | Risk/Reward |
|----------|-------------|-------------|
| Conservative | 0.15-0.25 | Lower premium, lower assignment risk |
| **Balanced** | **0.25-0.35** | **Good premium, reasonable risk** ✅ |
| Aggressive | 0.35-0.45 | Higher premium, higher assignment risk |

### Days to Expiry (DTE)

Time until the option expires.

```
7-14 DTE  → High theta decay, but risky if stock moves against you
21-30 DTE → Sweet spot for theta decay ✅
30-45 DTE → Standard wheel timeframe ✅ (recommended)
45-60 DTE → Slower decay, more time for stock to move
```

**Why 30-45 DTE?**
- Options lose value fastest in the last 30 days (theta decay)
- Enough time to roll if needed
- Good premium collection

### Take Profit

Close positions early when a certain % of max profit is reached.

```
Option sold for $1.00 premium
At 50% take profit: Close when option worth $0.50
Profit: $0.50 per contract ($50 total)
```

**Why take profit early?**
- Lock in gains, don't risk reversal
- Free up capital for new trades
- 50% of max profit in 30% of time = good deal

---

## 🚀 Usage

### Paper Trading (Recommended First)

```bash
# Start the bot
python src/main.py --config config/wheel_10k_paper.yml

# Watch the logs
tail -f wheel_bot.log
```

---

## 🧪 Backtesting

Test how the strategy would have performed historically before risking real money.

### Quick Backtest

```bash
# Basic backtest - 1 year
python -m src.backtesting.run_backtest \
  --start-date 2023-01-01 \
  --end-date 2024-01-01 \
  --capital 10000 \
  --rsi 45
```

### Backtest Options

| Flag | Description | Example |
|------|-------------|---------|
| `--start-date` | Start date (YYYY-MM-DD) | `2023-01-01` |
| `--end-date` | End date (YYYY-MM-DD) | `2024-01-01` |
| `--capital` | Starting capital | `10000` |
| `--rsi` | RSI threshold | `45` |
| `--symbols` | Stocks to test (comma-separated) | `PLTR,F,SOFI` |
| `--debug` | Verbose output | (flag) |

### Comprehensive Backtest

Run multiple configurations and compare results:

```bash
python run_fast_backtest.py
```

This tests various RSI thresholds and generates a comparison report.

### Interpreting Results

| Metric | Good | Excellent |
|--------|------|-----------|
| Annual Return | >10% | >20% |
| Win Rate | >60% | >75% |
| Max Drawdown | <15% | <10% |
| Sharpe Ratio | >1.0 | >1.5 |

### Sample Backtest Output

```
Backtest Results (2023-01-01 to 2024-01-01)
==========================================
Starting Capital: $10,000
Ending Capital:   $11,850
Total Return:     18.5%
Win Rate:         76%
Total Trades:     42
Max Drawdown:     8.2%
```

---

### Live Trading

⚠️ **Only after extensive paper trading!**

1. Change `environment: live` in your config
2. Ensure `ALPACA_LIVE_*` keys are set
3. Start with small position sizes
4. Monitor closely for the first few weeks

---

## ☁️ Deploy to AWS (Run 24/7)

Run the bot continuously on AWS EC2 for ~$0/month (free tier) with secure secrets management.

### Cost Estimate

| Component | Cost |
|-----------|------|
| EC2 t3.micro | **$0** (free tier 12 months) |
| Secrets Manager | ~$0.40/mo |
| **Total** | **~$0.40/mo** |

---

### Step 1: Store Secrets in AWS Secrets Manager

1. Go to **AWS Console** → **Secrets Manager** → **Store a new secret**
2. Choose **"Other type of secret"**
3. Add key/value pairs:

| Key | Value |
|-----|-------|
| `ALPACA_PAPER_API_KEY` | Your Alpaca paper API key |
| `ALPACA_PAPER_API_SECRET` | Your Alpaca paper API secret |
| `ALPACA_PAPER_BASE_URL` | `https://paper-api.alpaca.markets` |

4. Name it: `wheeler_paper`
5. Click **Store** and save the ARN (e.g., `arn:aws:secretsmanager:us-east-1:123456789:secret:wheeler_paper-AbCdEf`)

---

### Step 2: Create IAM Policy

1. Go to **IAM** → **Policies** → **Create policy**
2. Click **JSON** tab and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:wheeler_*"
    }
  ]
}
```

3. Name it: `WheelerSecretsAccess`
4. Click **Create policy**

---

### Step 3: Create IAM Role

1. Go to **IAM** → **Roles** → **Create role**
2. Select **AWS service** → **EC2**
3. Attach the policy: `WheelerSecretsAccess`
4. Name it: `wheeler-ec2-role`
5. Click **Create role**

---

### Step 4: Launch EC2 Instance

1. Go to **EC2** → **Launch Instance**
2. Configure:

| Setting | Value |
|---------|-------|
| Name | `wheeler-bot` |
| AMI | Amazon Linux 2023 |
| Instance type | `t3.micro` (free tier) |
| Key pair | Create new or use existing |
| Security group | Allow SSH (port 22) |
| IAM instance profile | `wheeler-ec2-role` |

3. Click **Launch instance**

---

### Step 5: Setup Wheeler on EC2

```bash
# SSH into your instance
ssh -i your-key.pem ec2-user@YOUR_EC2_PUBLIC_IP

# Update system and install dependencies
sudo dnf update -y
sudo dnf install python3.11 python3.11-pip git -y

# Clone the repo
git clone https://github.com/dgiliver/wheeler.git
cd wheeler

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install boto3
```

---

### Step 6: Create Startup Script

> **Note:** If you set up GitHub Actions auto-deploy (Step 9), the deploy workflow will automatically regenerate this script with the config specified in `.github/workflows/deploy.yml`. You only need to create it manually for the initial setup.

```bash
cat > ~/wheeler/start_bot.sh << 'EOF'
#!/bin/bash
cd /home/ec2-user/wheeler
source .venv/bin/activate
export PYTHONPATH="/home/ec2-user/wheeler:$PYTHONPATH"

# Load secrets from AWS Secrets Manager
eval $(python3 -c "
import boto3, json
client = boto3.client('secretsmanager', region_name='us-east-1')
secret = json.loads(client.get_secret_value(SecretId='wheeler_paper')['SecretString'])
for k,v in secret.items(): print(f'export {k}=\"{v}\"')
")

exec python3 src/main.py --config config/wheel_10k_paper.yml
EOF
chmod +x ~/wheeler/start_bot.sh
```

**To change the config later:** Edit `WHEELER_CONFIG` in `.github/workflows/deploy.yml` and merge to main. The next deploy will update the startup script automatically.

---

### Step 7: Create Systemd Service

```bash
sudo tee /etc/systemd/system/wheeler.service << 'EOF'
[Unit]
Description=Wheeler Options Trading Bot
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/wheeler
ExecStart=/home/ec2-user/wheeler/start_bot.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable wheeler
sudo systemctl start wheeler
```

---

### Step 8: Verify It's Running

```bash
# Check status
sudo systemctl status wheeler

# View live logs
journalctl -u wheeler -f

# Quick commands
sudo systemctl stop wheeler    # Stop
sudo systemctl restart wheeler # Restart
```

---

### Step 9: Setup GitHub Auto-Deploy (Optional)

For automatic deployments when you push to main:

1. Go to **GitHub** → **Your repo** → **Settings** → **Secrets and variables** → **Actions**
2. Add these secrets:

| Secret | Value |
|--------|-------|
| `EC2_HOST` | Your EC2 public IP |
| `EC2_SSH_KEY` | Contents of your `.pem` file |

3. Update EC2 Security Group to allow SSH from `0.0.0.0/0` (for GitHub Actions)

Now every merge to `main` will automatically deploy to your EC2!

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

## 🎓 Getting Started Guide (Newcomers)

If you're new to options or the wheel strategy, follow this path:

### Week 1-2: Learn & Backtest

1. **Read this README** - Understand RSI, delta, and the wheel strategy
2. **Run backtests** on different stocks and RSI settings:
   ```bash
   python run_fast_backtest.py
   ```
3. **Study the results** - Which stocks perform best? What RSI works?

### Week 3-4: Paper Trade

1. **Set up Alpaca paper account** - [Sign up free](https://alpaca.markets/)
2. **Configure your watchlist** - Start with 2-3 stocks you understand
3. **Run the bot locally:**
   ```bash
   python src/main.py --config config/wheel_10k_paper.yml
   ```
4. **Monitor daily** - Check logs, understand why trades happen

### Month 2: Refine

1. **Adjust RSI threshold** - Too many trades? Lower it. Too few? Raise it.
2. **Tune delta range** - More conservative? Lower delta. More aggressive? Higher.
3. **Add/remove stocks** - Keep winners, drop losers

### Month 3+: Consider Live (Optional)

1. **Deploy to AWS** - Run 24/7 without your laptop
2. **Start with small capital** - Even if you have more
3. **Monitor closely** - First few weeks are critical

---

## 💡 Tips & Best Practices

### Stock Selection

✅ **Good wheel candidates:**
- Stocks you'd happily own at lower prices
- $5-50 price range (affordable for small accounts)
- Decent options volume (>1000 daily)
- Moderate volatility (not meme stocks)

❌ **Avoid:**
- Stocks in downtrends (you'll get assigned and stuck)
- Low volume options (wide spreads eat profits)
- Earnings week (IV crush after announcement)
- Meme stocks (unpredictable)

### Position Sizing

| Account Size | Max Per Position | Example |
|--------------|------------------|---------|
| $5,000 | 20-25% | $1,000-1,250 |
| $10,000 | 15-20% | $1,500-2,000 |
| $25,000 | 10-15% | $2,500-3,750 |
| $50,000+ | 5-10% | $2,500-5,000 |

**Rule:** Never put more than 25% in one position.

### When NOT to Trade

- 🚫 Earnings announcements (within 1 week)
- 🚫 Major Fed meetings
- 🚫 Stock in strong downtrend
- 🚫 RSI already high (>50)
- 🚫 Wide bid-ask spreads (>$0.20)

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
