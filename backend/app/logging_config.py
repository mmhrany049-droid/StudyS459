"""Logging configuration (stdlib only — no extra dependency).

Two formats:
- text (default, human friendly for local dev)
- json (one JSON object per line, for production log collectors)
"""

import json
import logging
import logging.config
from datetime import datetime, timezone

from app.config import Settings


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    """Configure root logging once at application startup."""
    if settings.LOG_FORMAT == "json":
        formatter_cfg: dict = {
            "()": "app.logging_config._JsonFormatter",
        }
        fmt = None
    else:
        formatter_cfg = {
            "format": "%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
        fmt = None

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"app": formatter_cfg},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": settings.LOG_LEVEL,
                    "formatter": "app",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"level": settings.LOG_LEVEL, "handlers": ["console"]},
            "loggers": {
                # Keep third-party chatter down; our app loggers inherit root.
                "uvicorn.access": {"level": "WARNING"},
            },
        }
    )
    # Silence unused-var lint for the text branch without changing behavior.
    _ = fmt


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
