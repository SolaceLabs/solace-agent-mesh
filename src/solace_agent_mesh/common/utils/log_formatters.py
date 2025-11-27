import logging
import json
import os
import warnings
from datetime import datetime, timezone
import traceback


class DatadogJsonFormatter(logging.Formatter):
    """
    Custom formatter to output logs in Datadog-compatible JSON format.
    
    . deprecated::
        This formatter is deprecated. Please use pythonjsonlogger.json.JsonFormatter instead.
        For details, consult https://solacelabs.github.io/solace-agent-mesh/docs/documentation/deploying/logging#structured-logging

        Example:
            formatters:
              jsonFormatter:
                "()": pythonjsonlogger.json.JsonFormatter
                format: "%(timestamp)s %(levelname)s %(threadName)s %(name)s %(message)s"
    """

    def format(self, record):
        # Emit deprecation warning once
        if not hasattr(self.__class__, '_deprecation_warned'):
            warnings.warn(
                "DatadogJsonFormatter is deprecated and will be removed in a future version. "
                "Please use pythonjsonlogger.json.JsonFormatter instead. For details, consult https://solacelabs.github.io/solace-agent-mesh/docs/documentation/deploying/logging#structured-logging",
                DeprecationWarning,
                stacklevel=2
            )
            self.__class__._deprecation_warned = True
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
