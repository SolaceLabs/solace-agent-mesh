"""LogRecord factory that stamps `x_request_id` on every record.

`install_log_record_factory()` patches `logging.setLogRecordFactory` so
every `LogRecord` carries `x_request_id` at construction time, regardless
of which logger emits it or how a handler is configured. Called once at
process boot from `cli/commands/run_cmd.py`.

The factory reads the active `RequestContext` and falls back to
`MISSING_VALUE` when no context is set. It never overwrites a value
already present on the record.
"""
from __future__ import annotations

import logging

from .request_context import LOG_FIELD, MISSING_VALUE, RequestContext

_INSTALLED_MARKER = "__sam_x_request_id_factory_installed__"


def install_log_record_factory() -> None:
    """Install (idempotently) the LogRecord factory that stamps x_request_id.

    Composes with any pre-installed custom factory: the prior factory runs
    first; we only stamp our field afterwards.
    """
    base = logging.getLogRecordFactory()
    if getattr(base, _INSTALLED_MARKER, False):
        return  # already installed

    def factory(*args, **kwargs):
        record = base(*args, **kwargs)
        if not hasattr(record, LOG_FIELD):
            setattr(record, LOG_FIELD, RequestContext.current() or MISSING_VALUE)
        return record

    setattr(factory, _INSTALLED_MARKER, True)
    logging.setLogRecordFactory(factory)