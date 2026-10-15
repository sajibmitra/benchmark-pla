"""Compatibility shim — implementation lives in eda_hub.pages.qiskit."""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from eda_hub.pages.qiskit import *  # noqa: F403
from eda_hub.pages.qiskit import QUANTUM_COST_FORMULA  # noqa: F401
