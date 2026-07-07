"""极简结构化日志配置。"""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"keeplix.{name}")
