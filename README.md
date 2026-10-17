# calculate-rpla-cost

Python package (`eda_hub`) that scores **benchmark PLA/ESOP circuits** with several reversible-logic and Qiskit cost algorithms. External EDA binaries (ABC, Yosys, …) are **not shipped here** — this repo only resolves them under `$EDA_ROOT` on the host.

## Layout

| Path | Role |
|---|---|
| `benchmarks/` | Circuit data (`mcnc`, `classic`, `epfl`) |
| `eda_hub/` | Algorithm and tool-resolution code |
| `Algorithms/` | Optional legacy import shims (same logic as `eda_hub`) |
| `scripts/` | Setup and batch runners |
| `papers/` | Related PDFs (Gaur2024, Zhou2026) |

Default benchmark category for MCNC PLAs:

```text
benchmarks/mcnc/Combinational/pla/All_PLAs/<name>.esop   # preferred
benchmarks/mcnc/Combinational/pla/All_PLAs/<name>.pla
```

## System requirements

| Item | Need |
|---|---|
| OS | Linux or macOS |
| Python | 3.10+ |
| Disk | This repo + `benchmarks/` (run `./scripts/download_data.sh` if empty) |
| For library RPLA costs (Mitra / Tara / Optimized) | Python only |
| For Qiskit methodologies | Python + Qiskit (`pip install -e '.[qiskit]'`) |
| For SOP→ESOP / CMOS / PTL / post-CMOS flows | Host EDA tools under `$EDA_ROOT` (see below) |

No GPU and no IBM Quantum account are required for the Qiskit cost CLI.

## Install this package

```bash
cd /path/to/calculate-rpla-cost
./scripts/setup_local.sh
source .venv/bin/activate
```

Or:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e '.[qiskit]'
```

Useful env vars:

| Variable | Meaning |
|---|---|
| `EDA_ROOT` | Host EDA tree (default: parent of this repo) |
| `EDA_BENCHMARKS_ROOT` | Override benchmark root |
| `EDA_CALCULATE_RPLA_COST_ROOT` | This repo, if imported from elsewhere |
| `EDA_ABC` / `EDA_YOSYS` / `EDA_OPENROAD` / `EDA_NGSPICE` / `EDA_STA` / `EDA_XSCHEM` | Absolute paths; accepted only if under `$EDA_ROOT` |

## External EDA tools (on the host)

Declared in `eda_hub/tools.py`. Lookup is **only** under `$EDA_ROOT` (no `/usr` fallback). On a typical install, `$EDA_ROOT` is the parent of this repo (e.g. `…/Data/eda`) and binaries appear in `$EDA_ROOT/bin/` or the tool build trees.

| Tool | Resolved by | Used for |
|---|---|---|
| **ABC** | `resolve_abc_executable()` | SOP/ESOP front end (`&exorcism`), OpenROAD helper flows |
| **Yosys** | `resolve_yosys_executable()` | Netlist synthesis / map |
| **OpenROAD** | `resolve_openroad_executable()` | Place / route style metrics |
| **OpenSTA** (`sta`) | `resolve_sta_executable()` | Timing |
| **ngspice** | `resolve_ngspice_executable()` | PTL / CNTFET / memristor cell sim |
| **xschem** | `resolve_xschem_executable()` | Optional schematic capture |

Check that tools resolve from this repo:

```bash
source .venv/bin/activate
python - <<'PY'
from eda_hub.paths import eda_root
from eda_hub.tools import (
    resolve_abc_executable, resolve_yosys_executable,
    resolve_openroad_executable, resolve_ngspice_executable,
    resolve_sta_executable, resolve_xschem_executable,
)
print("EDA_ROOT", eda_root())
for name, fn in [
    ("abc", resolve_abc_executable),
    ("yosys", resolve_yosys_executable),
    ("openroad", resolve_openroad_executable),
    ("ngspice", resolve_ngspice_executable),
    ("sta", resolve_sta_executable),
    ("xschem", resolve_xschem_executable),
]:
    try:
        print(name, "->", fn())
    except Exception as e:
        print(name, "MISSING:", e)
PY
```

### Installing the host tools

Build or install each tool into `$EDA_ROOT` (sibling of this repo), then symlink or place executables under `$EDA_ROOT/bin/` if needed. Upstream projects:

| Tool | Upstream |
|---|---|
| ABC | https://github.com/berkeley-abc/abc |
| Yosys | https://github.com/YosysHQ/yosys |
| OpenROAD | https://github.com/The-OpenROAD-Project/OpenROAD |
| OpenSTA | https://github.com/The-OpenROAD-Project/OpenSTA |
| ngspice | https://ngspice.sourceforge.io / https://github.com/imr/ngspice |
| xschem | https://github.com/StefanSchippers/xschem |

Exact build flags depend on the host OS; follow each project’s install docs and keep the resulting binaries under `$EDA_ROOT`. EXORCISM-4 is used via ABC’s `&exorcism` (see `third_party/exorcism` for reference sources only).

## Algorithms and how to run them

### 1. Library RPLA costs — Mitra2016 / Tara2016 / Optimized (Prefix Cube)

Python-only. Metrics: gates (GA), garbage (GB), ancilla (AI), quantum cost (QC).

**Batch over named covers:**

```bash
source .venv/bin/activate
python scripts/batch_all_plas_costs.py
```

**Single circuit (API):**

```python
import copy
from types import SimpleNamespace
from eda_hub.pages.qiskit.comparison import load_rpla_from_esop_file
from eda_hub.pages.benchmarks.existing_calculation import ExistingCalculation
from eda_hub.pages.benchmarks.mitra2016_calculation import Mitra2016Calculation
from eda_hub.pages.benchmarks.tara2016_calculation import Tara2016Calculation
from eda_hub.pages.benchmarks.optimized_rpla_calculation import OptimizedRPLACalculation
from eda_hub.paths import benchmarks_root

path = benchmarks_root() / "mcnc/Combinational/pla/All_PLAs/misex1.esop"
rpla = load_rpla_from_esop_file(path)

# Existing NCT cascade
ex = ExistingCalculation(rpla, quiet=True)
ex.xorPlane(); ex.andPlane()
print("Existing", ex.gates, ex.garbages, ex.ancilla_input_count, ex.quantumCost)

def snap():
    return SimpleNamespace(
        functions=copy.deepcopy(rpla.functions),
        products=copy.deepcopy(rpla.products),
    )

m = Mitra2016Calculation(snap(), rpla.totalLiterals, quiet=True)
m.andPlane(); m.xorPlane()
print("Mitra2016", m.gates, m.garbages, m.ancilla_input_count, m.quantumCost)

t = Tara2016Calculation(snap(), rpla.totalLiterals, quiet=True)
t.andPlane(); t.xorPlane()
print("Tara2016", t.gates, t.garbages, t.ancilla_input_count, t.quantumCost)

o = OptimizedRPLACalculation(snap(), rpla.totalLiterals, quiet=True)
o.andPlane(); o.xorPlane()
print("Optimized", o.gates, o.garbages, o.ancilla_input_count, o.quantumCost)
```

Code: `eda_hub/pages/benchmarks/`.

### 2. Qiskit methodologies — standard / UMG-UNG / Gaur2024 / Zhou2026

Needs Qiskit. Runs on an ESOP/PLA file or an indexed benchmark name.

```bash
source .venv/bin/activate

# one circuit by name (suite/category defaults: mcnc + Combinational/pla/All_PLAs)
eda-qiskit-analysis --circuit misex1

# any local file
eda-qiskit-analysis --file benchmarks/mcnc/Combinational/pla/All_PLAs/rd53.esop

# whole category → CSV (resumable; 600 s timeout per circuit)
eda-qiskit-analysis --all --csv /tmp/qiskit-all-plas.csv
```

If the entry point is missing:

```bash
python scripts/run_qiskit_analysis.py --circuit misex1
```

| Key | Module | Cost meaning |
|---|---|---|
| `standard_quantum` | `eda_hub.pages.qiskit.standard_quantum` | CX + CCX count (weight 1) after transpile |
| `umg_ung` | `…umg_ung` | CX + 5×(UMG+UNG) |
| `gaur2024` | `…gaur2024` | FOM = qubit width × Toffoli depth |
| `zhou2026` | `…zhou2026` | Zhou `C` (µs) / LNN routing model |

Transpile (when circuit ≤ 96 qubits and ≤ 8000 gates): `optimization_level=2`, `seed_transpiler=42`.

### 3. SOP → ESOP (needs ABC / Yosys)

```python
# used internally by benchmark conversion paths
from eda_hub.tools import resolve_abc_executable, resolve_yosys_executable
print(resolve_abc_executable(), resolve_yosys_executable())
```

Scripts: `scripts/convert_to_esop.py`, `scripts/generate_esop_accurate.py`, `scripts/batch_convert_arithmetic_smart.py`. Code: `eda_hub/pages/benchmarks/sop_esop.py`.

### 4. CMOS / PTL / post-CMOS (need Yosys, OpenROAD, ngspice, …)

Python under `eda_hub/pages/cmos_ptl_tgl/` and `eda_hub/pages/post_cmos/` calls the resolvers above. Typical uses: Yosys synthesis, OpenROAD metrics, ngspice cell simulation. Run from the FastAPI host (mit-panel) or import the modules after tools resolve.

## License

Proprietary — Mitverse EDA.
