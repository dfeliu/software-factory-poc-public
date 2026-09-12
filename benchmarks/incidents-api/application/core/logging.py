import logging
from logging.config import dictConfig

from pythonjsonlogger.json import JsonFormatter

from application.core.config import Settings


class ContextFilter(logging.Filter):
    """Attach non-sensitive service context to every structured log record."""

    def __init__(self, service: str, environment: str) -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        record.environment = self.environment
        return True


def build_log_formatter() -> JsonFormatter:
    return JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(environment)s"
    )


def configure_logging(settings: Settings) -> None:
    """Configure JSON logs to standard output for application and Uvicorn logs."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "context": {
                    "()": ContextFilter,
                    "service": settings.app_name,
                    "environment": settings.app_env,
                }
            },
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.json.JsonFormatter",
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s "
                    "%(service)s %(environment)s",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["context"],
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"level": settings.log_level, "handlers": ["default"]},
            "loggers": {
                "uvicorn": {"level": settings.log_level, "handlers": ["default"]},
                "uvicorn.access": {
                    "level": settings.log_level,
                    "handlers": ["default"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": settings.log_level,
                    "handlers": ["default"],
                    "propagate": False,
                },
            },
        }
    )
