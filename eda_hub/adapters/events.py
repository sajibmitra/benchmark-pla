"""Tool event recorders.

When running under mit-panel (``app.services`` on ``sys.path``), delegate to the
real DB-backed event stores. Standalone calculate-rpla-cost runs use no-ops.
"""
from __future__ import annotations

from typing import Any


def _try_import(name: str, attr: str):
    try:
        mod = __import__(f"app.services.{name}", fromlist=[attr])
        return getattr(mod, attr)
    except Exception:
        return None


def _noop(*_a: Any, **_k: Any) -> None:
    return None


def _noop_list(_limit: int = 100) -> list:
    return []


record_abc_event = _try_import("eda_abc_events", "record_abc_event") or _noop
clear_abc_events = _try_import("eda_abc_events", "clear_abc_events") or _noop
list_abc_events = _try_import("eda_abc_events", "list_abc_events") or _noop_list

record_yosys_event = _try_import("eda_yosys_events", "record_yosys_event") or _noop
list_yosys_events = _try_import("eda_yosys_events", "list_yosys_events") or _noop_list

record_ngspice_event = _try_import("eda_ngspice_events", "record_ngspice_event") or _noop
list_ngspice_events = _try_import("eda_ngspice_events", "list_ngspice_events") or _noop_list

record_openroad_event = _try_import("eda_openroad_events", "record_openroad_event") or _noop
list_openroad_events = _try_import("eda_openroad_events", "list_openroad_events") or _noop_list

record_opensta_event = _try_import("eda_opensta_events", "record_opensta_event") or _noop
list_opensta_events = _try_import("eda_opensta_events", "list_opensta_events") or _noop_list
