import logging
from unittest.mock import Mock, patch

from src.main import main


def test_main_successful_run(caplog):
    """Test main function with successful bot run"""
    caplog.set_level(logging.INFO)

    with patch("sys.argv", ["main.py"]), patch("src.main.WheelBot") as mock_bot:
        # Setup mock
        mock_bot_instance = Mock()
        mock_bot.return_value = mock_bot_instance

        # Simulate KeyboardInterrupt after one iteration
        mock_bot_instance.run.side_effect = KeyboardInterrupt()

        # Run main
        main()

        # Verify logs and calls
        assert "Starting Wheel Strategy Bot" in caplog.text
        assert "Bot stopped by user" in caplog.text
        mock_bot.assert_called_once()
        mock_bot_instance.run.assert_called_once()


def test_main_error_handling(caplog):
    """Test main function error handling"""
    caplog.set_level(logging.INFO)

    with patch("sys.argv", ["main.py"]), patch("src.main.WheelBot") as mock_bot:
        # Setup mock
        mock_bot_instance = Mock()
        mock_bot.return_value = mock_bot_instance

        # Simulate an error
        mock_bot_instance.run.side_effect = Exception("Test error")

        # Run main
        main()

        # Verify logs and calls
        assert "Starting Wheel Strategy Bot" in caplog.text
        assert "Bot stopped due to error: Test error" in caplog.text
        mock_bot.assert_called_once()
        mock_bot_instance.run.assert_called_once()


def test_main_with_custom_config(caplog):
    """Test main function with custom config path"""
    with patch("src.main.WheelBot") as mock_bot, patch("sys.argv", ["main.py", "--config", "custom_config.yml"]):
        # Setup mock
        mock_bot_instance = Mock()
        mock_bot.return_value = mock_bot_instance
        mock_bot_instance.run.side_effect = KeyboardInterrupt()

        # Run main
        main()

        # Verify bot was created with custom config
        mock_bot.assert_called_once_with("custom_config.yml")
