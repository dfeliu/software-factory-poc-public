import json
import logging

from application.core.logging import ContextFilter, build_log_formatter


def test_structured_log_formatter_includes_service_context() -> None:
    record = logging.LogRecord(
        name="application.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="service started",
        args=(),
        exc_info=None,
    )
    ContextFilter(service="incidents-api", environment="test").filter(record)

    payload = json.loads(build_log_formatter().format(record))

    assert payload["message"] == "service started"
    assert payload["service"] == "incidents-api"
    assert payload["environment"] == "test"
