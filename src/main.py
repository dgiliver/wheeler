import argparse
import logging

from src.wheel_bot import WheelBot

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("wheel_bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run the Wheel Strategy Bot")
    parser.add_argument("--config", default="config/wheel_strategy.yml", help="Path to configuration file")

    args = parser.parse_args()

    try:
        logger.info("Starting Wheel Strategy Bot")
        bot = WheelBot(args.config)
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()
