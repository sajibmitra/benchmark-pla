"""Compatibility shim — eda_hub.pages.qiskit.zhou2026."""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from eda_hub.pages.qiskit.zhou2026 import *  # noqa: F403
