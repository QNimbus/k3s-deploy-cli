# file: src/k3s_deploy_cli/logging_utils.py
"""Logging utilities with color support."""

import logging

class ColorFormatter(logging.Formatter):
    """
    A logging formatter that adds ANSI color codes to messages.
    """
    grey = "\x1b[90m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    red = "\x1b[31m"
    bold_red = "\x1b[31;1m"
    blue = "\x1b[34m" # Bash script used \033[97m (bright white) often
    light_blue = "\x1b[94m"
    white = "\x1b[97m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey + "%(message)s" + reset,
        logging.INFO: white + "%(message)s" + reset, # Default to white for general info
        logging.WARNING: yellow + "Warning: %(message)s" + reset,
        logging.ERROR: red + "Error: %(message)s" + reset,
        logging.CRITICAL: bold_red + "Critical: %(message)s" + reset,
        # Custom levels for more specific colors
        "INFO_GREEN": green + "%(message)s" + reset,
        "INFO_YELLOW": yellow + "%(message)s" + reset,
        "INFO_BLUE": blue + "%(message)s" + reset,
        "INFO_LIGHT_BLUE": light_blue + "%(message)s" + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record with appropriate color."""
        # Use custom format string if available (e.g., for INFO_GREEN)
        # Otherwise, fall back to standard level-based format
        log_fmt = self.FORMATS.get(
            getattr(record, "levelname_custom", record.levelno),
            self.FORMATS.get(record.levelno) # Fallback for standard levels
        )
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def get_logger(name: str) -> logging.Logger:
    """
    Configures and returns a logger with color support.
    """
    logger = logging.getLogger(name)
    if not logger.handlers: # Avoid adding multiple handlers
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(ColorFormatter())
        logger.addHandler(ch)
    return logger

# Helper functions to log with specific colors easily
def log_info_green(logger: logging.Logger, message: str, *args, **kwargs):
    """Logs a message with green color."""
    logger.info(message, *args, extra={"levelname_custom": "INFO_GREEN"}, **kwargs)

def log_info_yellow(logger: logging.Logger, message: str, *args, **kwargs):
    """Logs a message with yellow color."""
    logger.info(message, *args, extra={"levelname_custom": "INFO_YELLOW"}, **kwargs)

def log_info_blue(logger: logging.Logger, message: str, *args, **kwargs):
    """Logs a message with blue/white color (like \033[97m)."""
    logger.info(message, *args, extra={"levelname_custom": "INFO_BLUE"}, **kwargs)

def log_info_light_blue(logger: logging.Logger, message: str, *args, **kwargs):
    """Logs a message with light blue color."""
    logger.info(message, *args, extra={"levelname_custom": "INFO_LIGHT_BLUE"}, **kwargs)

# Initialize a default logger for convenience if modules want to use it directly
logger = get_logger("k3s_deploy_cli")