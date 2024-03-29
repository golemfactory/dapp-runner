"""Python logging configuration for the `dapp-runner`."""
import logging
import warnings
from typing import Optional

logger = logging.getLogger(__name__)

LOG_CRITICAL = "CRITICAL"
LOG_FATAL = "FATAL"
LOG_ERROR = "ERROR"
LOG_WARN = "WARN"
LOG_WARNING = "WARNING"
LOG_INFO = "INFO"
LOG_DEBUG = "DEBUG"

log_names = {
    LOG_CRITICAL: logging.CRITICAL,
    LOG_FATAL: logging.CRITICAL,
    LOG_ERROR: logging.ERROR,
    LOG_WARN: logging.WARNING,
    LOG_WARNING: logging.WARNING,
    LOG_INFO: logging.INFO,
    LOG_DEBUG: logging.DEBUG,
}

LOG_CHOICES = log_names.keys()


def log_name_to_level(log_name: str) -> int:
    """Return log level corresponding to the name."""
    return log_names[log_name]


def enable_logger(
    log_file: Optional[str] = None,
    enable_warnings=False,
    console_log_level=logging.INFO,
    file_log_level=logging.DEBUG,
    api_log_level=None,
    format_: str = "[%(asctime)s %(levelname)s %(name)s] %(message)s",
):
    """Enable the logger.

    By default, it outputs `INFO` level logs to stderr and `DEBUG` level logs
    for `yapapi` and the REST APIs to the specified log file.
    """
    from yapapi import __version__ as yapapi_version
    from yapapi.log import _YagnaDatetimeFormatter

    api_log_level = api_log_level or file_log_level

    if enable_warnings:
        # capture only warnings coming from yapapi
        warnings.filterwarnings("once", module="yapapi")
        warnings.filterwarnings("once", module="dapp_runner")
        logging.captureWarnings(True)

    formatter = _YagnaDatetimeFormatter(fmt=format_)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(console_log_level)
    root.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(filename=log_file, mode="w", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(file_log_level)

        for name, level in (
            ("dapp_runner", file_log_level),
            ("yapapi", file_log_level),
            ("ya_activity", api_log_level),
            ("ya_market", api_log_level),
            ("ya_payment", api_log_level),
            ("ya_net", api_log_level),
        ):
            file_logger = logging.getLogger(name)
            file_logger.setLevel(level)
            file_logger.addHandler(file_handler)

    logger.debug("Yapapi version: %s", yapapi_version)

    if log_file:
        logger.info("Using log file `%s`", log_file)
