#!/usr/bin/env python3
"""Thin wrapper so ``python scripts/run_qiskit_analysis.py …`` works without PATH install."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eda_hub.pages.qiskit.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
