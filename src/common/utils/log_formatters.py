import logging
import json
import os
from datetime import datetime, timezone
import traceback


class DatadogJsonFormatter(logging.Formatter):
    """
    Custom formatter to output logs in Datadog-compatible JSON format.
    """

    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger.name": record.name,
            "logger.thread_name": record.threadName,
            "service": os.getenv("SERVICE_NAME", "solace_agent_mesh"),
            "code.filepath": record.pathname,
            "code.lineno": record.lineno,
            "code.module": record.module,
            "code.funcName": record.funcName,
        }

        dd_trace_id = getattr(record, "dd.trace_id", None)
        if dd_trace_id:
            log_entry["dd.trace_id"] = dd_trace_id

        dd_span_id = getattr(record, "dd.span_id", None)
        if dd_span_id:
            log_entry["dd.span_id"] = dd_span_id

        if record.exc_info:
            log_entry["exception.type"] = record.exc_info[0].__name__
            log_entry["exception.message"] = str(record.exc_info[1])
            log_entry["exception.stacktrace"] = "".join(
                traceback.format_exception(*record.exc_info)
            )

        return json.dumps(log_entry)
