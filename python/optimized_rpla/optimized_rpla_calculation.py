"""Compatibility shim — implementation lives in eda_hub.pages.benchmarks.optimized_rpla_calculation."""
from __future__ import annotations

import sys
from pathlib import Path

_PYTHON = Path(__file__).resolve().parents[1]
_REPO = _PYTHON.parent
for _p in (_REPO, _PYTHON):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from eda_hub.pages.benchmarks.optimized_rpla_calculation import *  # noqa: E402, F403
