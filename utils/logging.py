import logging
import logging.handlers
import json
import os
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def configure_logging(log_path=None, log_level="INFO"):
    """
    Configure structured logging with console and optional file handlers.

    Args:
        log_path: Optional file path for logs (if None, console only)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = StructuredFormatter()

    # Console handler (always)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if path provided)
    if log_path:
        try:
            log_dir = os.path.dirname(log_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            root_logger.warning(f"Failed to configure file logging: {e}")

    return root_logger


def get_logger(name):
    return logging.getLogger(name)
