import logging
import os
from dotenv import load_dotenv
from src.config.settings import AlpacaConfig, PollingConfig
from src.services.alpaca_service import AlpacaService
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_paper_connection():
    load_dotenv()
    
    # Create paper config
    config = AlpacaConfig(
        environment='paper',
        watchlist=[],
        polling=PollingConfig()
    )
    
    if not config.api_key or not config.api_secret:
        logger.error("Missing API keys")
        return

    logger.info("Connecting to Alpaca Service (Paper)...")
    service = AlpacaService(config)
    
    # Test Account
    account = service.get_account()
    if account:
        logger.info(f"Connected! Account ID: {account.get('id')}")
        logger.info(f"Buying Power: ${account.get('buying_power')}")
    else:
        logger.error("Failed to fetch account")
        return

    # Test Option Chain (which was hitting limits)
    symbol = "SPY"
    expiration = datetime.now() + timedelta(days=25)
    logger.info(f"Fetching option chain for {symbol}...")
    
    chain = service.get_option_chain(symbol, expiration)
    logger.info(f"Successfully fetched {len(chain)} option contracts")
    
    if chain:
        logger.info(f"Sample contract: {chain[0]['symbol']} Bid: {chain[0]['bid']} Ask: {chain[0]['ask']}")

if __name__ == "__main__":
    test_paper_connection()

