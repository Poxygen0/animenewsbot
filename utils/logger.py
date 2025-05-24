import logging
import os

def setup_logger(name: str, log_file: str) -> logging.Logger:
    """Creates and returns a logger with the specified name and log file."""

    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers
    if not logger.handlers:
        # Create file handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
        file_handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        # Add handler
        logger.addHandler(file_handler)

    return logger
