import logging

from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest
from dotenv import load_dotenv

from src.config.settings import AlpacaConfig, PollingConfig

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def main():
    load_dotenv()

    config = AlpacaConfig(environment="paper", watchlist=[], polling=PollingConfig())

    if not config.api_key:
        return

    logger.info("--- Testing with Official alpaca-py SDK ---")
    try:
        client = OptionHistoricalDataClient(config.api_key, config.api_secret)

        # Try OptionChainRequest if it exists?
        # Check dir
        # logger.info(f"Client methods: {dir(client)}")

        # It seems get_option_chain is NOT a method on client usually.
        # But let's check if we can list contracts.
        # client.get_option_contracts?

        # Let's try to get snapshots for the underlying directly?
        # Some versions of SDK support get_option_chain.

        try:
            # This is a guess based on common SDK patterns
            req = OptionChainRequest(underlying_symbol="SPY")
            chain = client.get_option_chain(req)
            logger.info(f"SDK get_option_chain found {len(chain)} items")
            if chain:
                logger.info(f"First item: {chain.keys()[0] if isinstance(chain, dict) else chain[0]}")
        except Exception as e:
            logger.info(f"SDK get_option_chain failed or not found: {e}")

    except Exception as e:
        logger.error(f"SDK Error: {e}")


if __name__ == "__main__":
    main()
