#!/usr/bin/env bash
# Create a portable local venv with Qiskit for any workstation.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "error: $PYTHON not found" >&2
  exit 1
fi

"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "error: Python >= 3.10 required" >&2
  exit 1
}

echo "[INFO] Creating venv at $VENV_DIR"
"$PYTHON" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install -U pip setuptools wheel
python -m pip install -e '.[qiskit]'

echo "[INFO] Verifying imports…"
python - <<'PY'
import qiskit
import eda_hub
from eda_hub.paths import benchmarks_root, repo_root
from eda_hub.pages.qiskit import (
    calculate_gaur2024_cost,
    calculate_standard_quantum_cost,
    calculate_umg_ung_cost,
    calculate_zhou2026_cost,
    compare_esop_file,
)

print("qiskit", qiskit.__version__)
print("eda_hub", eda_hub.__version__)
print("repo_root", repo_root())
print("benchmarks_root", benchmarks_root(), "exists=", benchmarks_root().is_dir())
print("calculators OK:", ", ".join([
    calculate_standard_quantum_cost.__name__,
    calculate_umg_ung_cost.__name__,
    calculate_gaur2024_cost.__name__,
    calculate_zhou2026_cost.__name__,
    compare_esop_file.__name__,
]))
PY

echo
echo "Done. Activate and run analysis:"
echo "  source $VENV_DIR/bin/activate"
echo "  eda-qiskit-analysis --circuit 5xp1"
echo "  eda-qiskit-analysis --file benchmarks/mcnc/Combinational/pla/All_PLAs/5xp1.esop"
echo "  eda-qiskit-analysis --all --csv /tmp/qiskit-all-plas.csv"
