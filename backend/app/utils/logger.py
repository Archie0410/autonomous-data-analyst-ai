"""
Centralized loguru-based logger.

All modules should use:
    from app.utils.logger import logger
"""

from __future__ import annotations

import sys

from loguru import logger as _logger

from app.config import settings


def _configure() -> None:
    _logger.remove()
    _logger.add(
        sys.stdout,
        level=settings.log_level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    _logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        level=settings.log_level,
        rotation="10 MB",
        retention="7 days",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )


_configure()
logger = _logger
