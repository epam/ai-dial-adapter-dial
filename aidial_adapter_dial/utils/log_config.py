import logging
import os
import re
from logging import Filter, LogRecord

from aidial_sdk import configure_root_logger

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class HealthCheckFilter(Filter):
    def filter(self, record: LogRecord):
        return not re.search(r"(\s+)/health(\s+)", record.getMessage())


def configure_loggers():
    configure_root_logger()

    # Filter out health check requests from uvicorn logs
    logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())

    # Setting up log levels
    for name in ["aidial_adapter_dial", "uvicorn"]:
        logging.getLogger(name).setLevel(LOG_LEVEL)
