import logging
import os
from logging.handlers import RotatingFileHandler
from config import (
    LOG_TO_CONSOLE, LOG_MAX_BYTES, LOG_BACKUP_COUNT,
    NOISY_LOGGERS, DEBUG
)

THIRD_PARTY_LOG_PATH = "./data/logs/third_party.log"

def setup_logger(
    name: str,
    log_file: str,
    console: bool = LOG_TO_CONSOLE,
    max_bytes: int = LOG_MAX_BYTES,
    backup_count: int = LOG_BACKUP_COUNT
) -> logging.Logger:
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    os.makedirs(os.path.dirname(THIRD_PARTY_LOG_PATH), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    if not logger.handlers:
        # File handler (main log)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
        )
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

        # Optional console handler
        if console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(console_handler)

    # Setup shared handler for noisy logs (only once)
    if DEBUG:
        shared_noisy_logger = logging.getLogger("third_party")
        if not shared_noisy_logger.handlers:
            noisy_handler = RotatingFileHandler(
                THIRD_PARTY_LOG_PATH,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8"
            )
            noisy_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            shared_noisy_logger.addHandler(noisy_handler)
            shared_noisy_logger.setLevel(logging.DEBUG)

        for noisy_name in NOISY_LOGGERS:
            noisy = logging.getLogger(noisy_name)
            noisy.handlers = []
            noisy.setLevel(logging.DEBUG)
            noisy.propagate = True  # Forward to "third_party"

    else:
        for noisy_name in NOISY_LOGGERS:
            logging.getLogger(noisy_name).setLevel(logging.WARNING)

    return logger
