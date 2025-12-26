import logging
from typing import Optional

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO", uvloop: bool = False) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT)
    if uvloop:
        try:
            import uvloop

            uvloop.install()
        except ImportError:
            logging.getLogger(__name__).debug("uvloop not installed; skipping")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or __name__)
