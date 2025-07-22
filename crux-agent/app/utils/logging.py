"""
Logging configuration using loguru.
"""
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from app.settings import settings


def setup_logging() -> None:
    """Configure logging based on application settings."""
    # Remove default logger
    logger.remove()
    
    # Configure log format
    if settings.log_format == "json":
        log_format = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message} | {extra}"
        serialize = True
    else:
        log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        serialize = False
    
    # Add console handler
    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.log_level,
        serialize=serialize,
        backtrace=settings.debug,
        diagnose=settings.debug,
    )
    
    # Add file handler for production
    if settings.env == "production":
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logger.add(
            log_dir / "app.log",
            format=log_format,
            level=settings.log_level,
            serialize=serialize,
            rotation="500 MB",
            retention="10 days",
            compression="zip",
            backtrace=True,
            diagnose=False,
        )
        
        # Add error log file
        logger.add(
            log_dir / "errors.log",
            format=log_format,
            level="ERROR",
            serialize=serialize,
            rotation="100 MB",
            retention="30 days",
            compression="zip",
            backtrace=True,
            diagnose=True,
        )


def get_logger(name: str) -> Any:
    """Get a logger instance with a specific name."""
    return logger.bind(name=name)


# Initialize logging on import
setup_logging()

# Export logger instance
__all__ = ["logger", "get_logger", "setup_logging"] 