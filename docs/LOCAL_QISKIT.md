# Local Qiskit analysis (any workstation)

This repository is self-contained for the four `/qiskit` methodologies. You do
**not** need mit-panel, a server volume path, or a shared `/home/mitpanel` venv.

## One-time setup

```bash
cd /path/to/calculate-rpla-cost
./scripts/setup_local.sh
source .venv/bin/activate
```

Equivalent manual install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[qiskit]'
```

Benchmarks ship under `benchmarks/` (MCNC / classic / EPFL). If missing:

```bash
./scripts/download_data.sh
```

## Run analysis

Single indexed circuit:

```bash
eda-qiskit-analysis --circuit 5xp1
# or without console entrypoint:
python scripts/run_qiskit_analysis.py --circuit 5xp1
```

Any local ESOP/PLA file:

```bash
eda-qiskit-analysis --file benchmarks/mcnc/Combinational/pla/All_PLAs/rd53.esop
```

Export a full category CSV (resumable; 600s per-circuit timeout by default):

```bash
eda-qiskit-analysis --all \
  --suite mcnc \
  --category Combinational/pla/All_PLAs \
  --csv qiskit-realization-comparison-mcnc-Combinational-pla-All_PLAs.csv
```

## Methodologies

| Key | Entry point | Cost |
|---|---|---|
| `standard_quantum` | `calculate_standard_quantum_cost` | Σ(CNOT) + Σ(Toffoli) |
| `umg_ung` | `calculate_umg_ung_cost` | Σ(CNOT) + 5×Σ(UMG+UNG) |
| `gaur2024` | `calculate_gaur2024_cost` | FOM = width × Toffoli_depth (Qiskit circuit) |
| `zhou2026` | `calculate_zhou2026_cost` | C = T_adj + W_error×E (LNN Qiskit) |

Python API:

```python
from eda_hub.pages.qiskit import compare_esop_file, compare_benchmark_circuit

print(compare_esop_file("benchmarks/mcnc/Combinational/pla/All_PLAs/5xp1.esop"))
print(compare_benchmark_circuit(
    suite="mcnc",
    category="Combinational/pla/All_PLAs",
    circuit="5xp1",
))
```

## Optional env vars

| Variable | Purpose |
|---|---|
| `EDA_BENCHMARKS_ROOT` | Override benchmark tree (default: `<repo>/benchmarks`) |
| `EDA_CALCULATE_RPLA_COST_ROOT` | Override repo root discovery |
| `EDA_QISKIT_SITE_PACKAGES` | Extra site-packages if Qiskit lives outside the active venv |
| `EDA_ROOT` | Only needed for ABC/Yosys/OpenROAD/ngspice tools — **not** for Qiskit cost |

## Requirements

- Python ≥ 3.10
- `qiskit>=1.0,<3` (installed via `.[qiskit]`)
- No GPU / IBM Quantum account required (circuits are built and measured locally)
