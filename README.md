# calculate-rpla-cost (`eda_hub`)

Standalone calculation package for **Prefix-Cube Sharing for Reversible PLA Synthesis** ([Manuscript.pdf](Manuscript.pdf)) and for [eda.mitverse.com](https://eda.mitverse.com). A reviewer can reproduce the MCNC load, library RPLA costs (Table IX), and Qiskit transpile ledger (Table X) on a laptop or this Ubuntu host. Step-by-step Qiskit detail: [docs/LOCAL_QISKIT.md](docs/LOCAL_QISKIT.md).

## Verified on this host (Ubuntu)

Checked on the Data/eda Ubuntu system after syncing from macOS:

| Item | Value on this host |
|---|---|
| OS | Ubuntu Linux 6.8 (aarch64, Neoverse-N1, 2 CPUs) |
| Repo path | `/mnt/HC_Volume_105482360/Data/eda/calculate-rpla-cost` |
| Python | 3.12.3 |
| Qiskit in `.venv` | 2.5.2 (`qiskit>=1.0,<3`; manuscript numbers used 2.3.1) |
| Benchmarks | `benchmarks/mcnc/Combinational/pla/All_PLAs/` present (189 files) |
| Smoke tests | `eda-qiskit-analysis --circuit misex1` and `rd53` succeed |
| Table X spot-check | `misex1` / `rd53` / `dk17` match `scripts/qiskit-transpile-rep20.csv` |

Optional EDA binaries (ABC, Yosys, OpenROAD, ngspice, …) live under `$EDA_ROOT` (here: `/mnt/HC_Volume_105482360/Data/eda`). **They are not required** for manuscript Table IX / Table X Qiskit reproduction.

## Quick start (reviewer)

```bash
cd /mnt/HC_Volume_105482360/Data/eda/calculate-rpla-cost   # or your clone
./scripts/setup_local.sh
source .venv/bin/activate

# 1) Running example from the manuscript (misex1)
eda-qiskit-analysis --circuit misex1

# 2) Another full-transpile cover (Status = full in Table X)
eda-qiskit-analysis --circuit rd53

# 3) Optional: full All_PLAs export (resumable CSV)
eda-qiskit-analysis --all --csv /tmp/qiskit-all-plas.csv
```

Expected `misex1` CLI summary (CX/CCX tally and package `quantum_cost` fields — see mapping below):

```text
circuit: misex1  source: misex1.esop
  standard_quantum   quantum_cost=90
  umg_ung            quantum_cost=318
  gaur2024           quantum_cost=1558
  zhou2026           quantum_cost=266
```

If the console script is missing from `PATH`:

```bash
python scripts/run_qiskit_analysis.py --circuit misex1
```

## Manuscript.pdf → what to run

Paper: [Manuscript.pdf](Manuscript.pdf) (*Prefix-Cube Sharing for Reversible PLA Synthesis…*). Related prior art PDFs: `papers/Gaur2024.pdf`, `papers/Zhou2026.pdf`.

| Manuscript artifact | How to reproduce / check | Package entry |
|---|---|---|
| **20 representative covers** | Names listed below; files under `benchmarks/mcnc/Combinational/pla/All_PLAs/` | `build_index()` / CLI `--circuit` |
| **Table IX** (library GA, GB, AI, QC before transpile) | `ExistingCalculation` = NCT cascade; `OptimizedRPLACalculation` = Prefix Cube | `eda_hub.pages.benchmarks` (also `scripts/batch_all_plas_costs.py`, shipped `scripts/all_plas_table9_costs.csv`) |
| **Table X** (qiskit-transpile G, D, Q) | NCT row from `standard_quantum` after `qiskit.transpile`; Prefix Cube G / D∧ / Q stay **netlist** counts (not UMG circuit `.depth()`) | `eda-qiskit-analysis`; shipped `scripts/qiskit-transpile-rep20.csv` |
| **Table XI** (CX/CCX tally & macro cost) | Tally = `standard_quantum.quantum_cost` (= n_CX + n_CCX). Macro NCT QC = `n_CX + 5 n_CCX` from `gate_mix` | same CLI / API |
| **misex1 running example** | NCT after transpile: G=134, D=46, Q=38. Prefix Cube netlist: G=45, D∧ ≤ 7, Q=27, QC=113 | CLI + library calculators below |
| Nangate45 / CNTFET / VTEAM mW | Technology map of the same netlist; needs `$EDA_ROOT` tools + hub DB metrics — **out of scope for laptop Qiskit-only review** | optional `eda_hub.pages.cmos_ptl_tgl` / `post_cmos` |

### 20 representative circuits (Table IX / X)

`alu4`, `apex1`, `apex3`, `apla`, `b2`, `b3`, `chkn`, `cordic`, `dk17`, `duke2`, `e64`, `f51m`, `ibm`, `misex1`, `misex3c`, `pdc`, `rd53`, `ryy6`, `table3`, `table5`.

`chkn`, `dk17`, `f51m`, `ibm`, `misex3c`, and `ryy6` are `.pla` only. The others prefer `.esop`. Full transpile (Status=`full`) runs only when qubits ≤ 96 and gates ≤ 8000 — in the rep-20 set that includes **`dk17`, `misex1`, `rd53`**.

### Check Table IX library numbers (misex1)

```python
import copy
from types import SimpleNamespace
from eda_hub.pages.qiskit.comparison import load_rpla_from_esop_file
from eda_hub.pages.benchmarks.existing_calculation import ExistingCalculation
from eda_hub.pages.benchmarks.optimized_rpla_calculation import OptimizedRPLACalculation
from eda_hub.paths import benchmarks_root

rpla = load_rpla_from_esop_file(
    benchmarks_root() / "mcnc/Combinational/pla/All_PLAs/misex1.esop"
)
ex = ExistingCalculation(rpla, quiet=True)
ex.xorPlane(); ex.andPlane()
snap = SimpleNamespace(
    functions=copy.deepcopy(rpla.functions),
    products=copy.deepcopy(rpla.products),
)
opt = OptimizedRPLACalculation(snap, rpla.totalLiterals, quiet=True)
opt.andPlane(); opt.xorPlane()
print("NCT", ex.gates, ex.garbages, ex.ancilla_input_count, ex.quantumCost)
# -> 91 66 57 319   (Manuscript Table IX)
print("PrefixCube", opt.gates, opt.garbages, opt.ancilla_input_count, opt.quantumCost)
# -> 45 20 19 113
```

Batch / CSV: `python scripts/batch_all_plas_costs.py` (writes Mitra / Tara / Optimized columns). A prior export is `scripts/all_plas_table9_costs.csv`.

### Check Table X transpile ledger

```bash
eda-qiskit-analysis --circuit misex1
# NCT G,D,Q live in realizations['standard_quantum']:
#   gates=134, qiskit_circuit_depth=46, qiskit_num_qubits=38
```

Shipped reference for all 20: `scripts/qiskit-transpile-rep20.csv` (columns `std_gates`, `std_depth`, `std_qubits`, …). On this host, live `misex1` / `rd53` / `dk17` match that CSV.

**Do not** read Prefix Cube Table X G/D/Q from `umg_ung.gates` after transpile — that field is the CX/UMG circuit tally. Use the Optimized / Prefix Cube **netlist** counters (and the manuscript’s D∧ ≤ n−1 bound).

### Package `quantum_cost` vs manuscript columns

| CLI / API key | Package `quantum_cost` | Manuscript use |
|---|---|---|
| `standard_quantum` | n_CX + n_CCX (weight 1) | Table XI tally; **not** Table IX QC |
| `umg_ung` | n_CX + 5×(UMG+UNG) on Qiskit circuit | Prefix Cube **macro** style; netlist QC is Optimized `quantumCost` |
| `gaur2024` | FOM = width × Toffoli depth | Extra score; not the Table IX QC column |
| `zhou2026` | Zhou `C` (µs) | Extra score; Algorithm 1 gate ledger is separate |

NCT macro cost in the paper is `n_CX + 5 n_CCX`. Read `cnot_gates` and `toffoli_gates` from `standard_quantum.gate_mix`. Transpile settings: `optimization_level=2`, `seed_transpiler=42`, NCT basis `{x,cx,ccx,swap}`, Prefix Cube basis `{x,cx,umg,ung,swap}`.

Full field notes: [docs/LOCAL_QISKIT.md](docs/LOCAL_QISKIT.md).

## System requirements

| Item | Requirement |
|---|---|
| OS | macOS or Linux (bash setup script) |
| Python | 3.10 or newer |
| Qiskit | `qiskit>=1.0,<3` (manuscript: 2.3.1; this host: 2.5.2) |
| Hardware | No GPU, no IBM Quantum account. `misex1` / `rd53` finish in seconds. Full MCNC export is CPU time; 600 s timeout per circuit; CSV is resumable |
| EDA binaries | Not required for Qiskit / Table IX–XI. ABC, Yosys, OpenROAD, OpenSTA, ngspice, xschem resolve only under `EDA_ROOT` |

## Layout

```text
Manuscript.pdf      # paper under review
eda_hub/            # canonical calculation package
  paths.py          # repo_root, eda_root, benchmarks_root
  tools.py          # resolve_* only under EDA_ROOT
  shared/           # RPLA core
  pages/
    benchmarks/     # library Mitra / Tara / Optimized (Table IX)
    qiskit/         # four methodologies + CLI (Table X / XI)
    cost_metric/ post_cmos/ cmos_ptl_tgl/
Algorithms/         # legacy import shims (renamed from python/)
benchmarks/         # MCNC / classic / EPFL
docs/LOCAL_QISKIT.md
docs/PAGE_MAP.md
papers/             # Gaur2024.pdf, Zhou2026.pdf
scripts/
  setup_local.sh
  run_qiskit_analysis.py
  qiskit-transpile-rep20.csv          # Table X reference (20 circuits)
  all_plas_table9_costs.csv           # library cost export
  batch_all_plas_costs.py
```

Hub page map: [docs/PAGE_MAP.md](docs/PAGE_MAP.md). Shim notes: [Algorithms/README.md](Algorithms/README.md).

The FastAPI host remains **mit-panel**; this repo owns the calculation code. mit-panel services are thin wrappers that import `eda_hub` (via `EDA_CALCULATE_RPLA_COST_ROOT` / `_eda_hub_bootstrap`).

## Install

```bash
cd /path/to/calculate-rpla-cost
./scripts/setup_local.sh
source .venv/bin/activate
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e '.[qiskit]'
```

If `benchmarks/` is empty: `./scripts/download_data.sh` (Google Drive via `gdown`).

## Recommended reviewer checklist

1. Open [Manuscript.pdf](Manuscript.pdf); note Tables IX–XI and the misex1 example (G=134 / D=46 / Q=38 vs Prefix Cube G=45 / D∧ ≤ 7 / Q=27).
2. `./scripts/setup_local.sh` then `source .venv/bin/activate`.
3. `eda-qiskit-analysis --circuit misex1` — confirm `standard_quantum` gates/depth/qubits 134/46/38 and tally `quantum_cost=90`.
4. Run the short Python snippet above — confirm NCT 91/66/57/319 and Prefix Cube 45/20/19/113.
5. Spot-check `rd53` and compare to `scripts/qiskit-transpile-rep20.csv`.
6. Optional: `eda-qiskit-analysis --all --csv /tmp/out.csv` for the full indexed category.
7. Optional shim check: `cd Algorithms && python3 -c "import rpla; import qiskit_realization; print('OK')"`.

## Tool resolution

All CLI tools resolve **only** under `$EDA_ROOT` (default: parent of this repo):

- `$EDA_ROOT/bin/{abc,yosys,openroad,ngspice,sta,xschem}`
- known build trees under `$EDA_ROOT/{abc,yosys,OpenROAD,OpenSTA,ngspice,xschem,…}`

Env overrides (`EDA_ABC`, `EDA_YOSYS`, …) are honored **only** when the path is under `$EDA_ROOT`. Missing tools raise `ToolNotFoundError` (no `/usr/bin` fallback).

**Qiskit cost analysis does not need `EDA_ROOT`.**

## Env vars

| Variable | Purpose |
|---|---|
| `EDA_ROOT` | Data/eda tool tree (ABC/Yosys/… only) |
| `EDA_CALCULATE_RPLA_COST_ROOT` | This repository |
| `EDA_BENCHMARKS_ROOT` | Benchmark circuits (default: `<repo>/benchmarks`) |
| `EDA_QISKIT_SITE_PACKAGES` | Optional external Qiskit site-packages |
| `PYTHON` / `VENV_DIR` | Overrides for `setup_local.sh` |

## License

Proprietary — Mitverse EDA.
