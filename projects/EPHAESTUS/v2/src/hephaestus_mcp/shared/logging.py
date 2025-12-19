from __future__ import annotations

import logging
import sys
from typing import Optional

from .config import LoggingConfig


def configure_logging(config: LoggingConfig) -> None:
    handlers: list[logging.Handler] = []
    if config.file:
        handlers.append(logging.FileHandler(config.file, encoding="utf-8"))
    else:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=getattr(logging, config.level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=handlers,
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name if name else "hephaestus_mcp")