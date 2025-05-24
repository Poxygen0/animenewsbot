import logging
import os
from logging.handlers import RotatingFileHandler
from config import (LOG_TO_CONSOLE, LOG_MAX_BYTES, LOG_BACKUP_COUNT, NOISY_LOGGERS, DEBUG)

def setup_logger(
    name: str,
    log_file: str,
    console: bool = LOG_TO_CONSOLE,
    max_bytes: int = LOG_MAX_BYTES,
    backup_count: int = LOG_BACKUP_COUNT
) -> logging.Logger:
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    if not logger.handlers:
        # File handler
        file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

        # Optional console handler
        if console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_format)
            logger.addHandler(console_handler)

    # Silence or redirect noisy libraries
    for noisy in NOISY_LOGGERS:
        noisy_logger = logging.getLogger(noisy)
        if DEBUG:
            # Log noisy libraries to separate file
            noisy_handler = RotatingFileHandler(
                "./data/logs/third_party.log", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
            noisy_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            noisy_handler.setFormatter(noisy_format)
            noisy_logger.addHandler(noisy_handler)
            noisy_logger.setLevel(logging.DEBUG)
        else:
            # Silence them in production
            noisy_logger.setLevel(logging.WARNING)

    return logger
