"""
Logging utilities
"""

import logging
import sys
from typing import Optional
import json


class JsonFormatter(logging.Formatter):
    """Format log records as JSON for easy machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # record may contain extra attributes – include those that are not defaults
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in (
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
                'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 'process',
                'processName', 'time'
            )
        }
        if extras:
            log_record.update(extras)
        return json.dumps(log_record, ensure_ascii=False)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
    json_logs: bool = False
):
    """Setup logging configuration"""
    
    # Choose formatter
    if json_logs:
        formatter = JsonFormatter()
    else:
        if format_string is None:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        formatter = logging.Formatter(format_string)
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    for h in handlers:
        h.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True  # override any existing config
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name) 