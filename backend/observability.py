"""Request-scoped logging context and lightweight metrics."""

from __future__ import annotations

import contextvars
import logging
from typing import Any

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)

_metrics: dict[str, int] = {
    "audit_post_total": 0,
    "audit_post_cache_hit": 0,
    "audit_post_cache_miss": 0,
    "audit_report_get_hit": 0,
    "audit_report_get_miss": 0,
    "compare_report_get_hit": 0,
    "compare_report_get_miss": 0,
}


def metrics_snapshot() -> dict[str, Any]:
    return dict(_metrics)


def inc_metric(key: str, n: int = 1) -> None:
    _metrics[key] = _metrics.get(key, 0) + n


class RequestIdLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_cd_audit_configured", False):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [request_id=%(request_id)s] %(name)s: %(message)s",
        ),
    )
    handler.addFilter(RequestIdLogFilter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root._cd_audit_configured = True  # type: ignore[attr-defined]
