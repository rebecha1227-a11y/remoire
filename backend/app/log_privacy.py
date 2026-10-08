"""Metadata-only production logs. Never format free-form payloads or exceptions.

Applied before importing services in both entrypoints. This intentionally trades
verbose SDK diagnostics for privacy; use source location and exception class to
diagnose failures. Request audit logs have a small, explicit safe-field allowlist.
"""
import logging
import re

_installed = False
_HTTP_TEMPLATE = "request_id=%s method=%s route=%s status=%s duration_ms=%.2f"
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def install_private_logging():
    global _installed
    if _installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        error_type = record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else "none"
        if error_type == "none" and isinstance(record.args, tuple):
            for value in record.args:
                if isinstance(value, BaseException):
                    error_type = type(value).__name__
                    break
        if record.name == "uvicorn.access":
            # Uvicorn's AccessFormatter requires its five positional arguments.
            values = record.args if isinstance(record.args, tuple) else ()
            status = values[4] if len(values) == 5 and type(values[4]) is int else 0
            method = values[1] if len(values) == 5 and values[1] in _METHODS else "OTHER"
            record.msg = '%s - "%s %s HTTP/%s" %d'
            record.args = ("redacted", method, "/redacted", "1.1", status)
        elif record.name == "remoire.http" and record.msg == _HTTP_TEMPLATE and isinstance(record.args, tuple) and len(record.args) == 5:
            request_id, method, route, status, duration = record.args
            request_id = request_id if isinstance(request_id, str) and re.fullmatch(r"[0-9a-f-]{36}", request_id) else "redacted"
            # route is the framework route template, never the requested URL.
            route = route if isinstance(route, str) and re.fullmatch(r"/[a-zA-Z0-9_/{}/-]*", route) else "unmatched"
            record.args = (request_id, method if method in _METHODS else "OTHER", route,
                           status if type(status) is int else 0,
                           duration if type(duration) in (int, float) else 0)
        else:
            record.msg = "event=%s.%s line=%s error_type=%s"
            record.args = (record.module, record.funcName, record.lineno, error_type)
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return record

    logging.setLogRecordFactory(factory)
    _installed = True
