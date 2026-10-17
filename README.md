# calculate-rpla-cost

Python package (`eda_hub`) that scores **benchmark PLA/ESOP circuits** with reversible-logic and Qiskit cost algorithms. External EDA programs (ABC, Yosys, OpenROAD, and others) are **not inside this repository**. They must be installed on the same machine, in the **parent folder of this repository** (the folder that contains `calculate-rpla-cost`).

## Layout

| Path | Role |
|---|---|
| `benchmarks/` | Circuit data (`mcnc`, `classic`, `epfl`) |
| `eda_hub/` | Algorithm code and tool lookup |
| `Algorithms/` | Optional legacy import shims (same logic as `eda_hub`) |
| `scripts/` | Setup and batch runners |

Default MCNC PLA/ESOP files:

```text
benchmarks/mcnc/Combinational/pla/All_PLAs/<name>.esop   # preferred when present
benchmarks/mcnc/Combinational/pla/All_PLAs/<name>.pla
```

## System requirements

| Item | Need |
|---|---|
| OS | Linux or macOS |
| Python | 3.10 or newer |
| Benchmarks | Folder `benchmarks/` in this repository (run `./scripts/download_data.sh` if it is empty) |
| Library RPLA costs (Mitra / Tara / Optimized) | Python only |
| Qiskit methodologies | Python and Qiskit (`pip install -e '.[qiskit]'`) |
| SOP→ESOP, CMOS, PTL, post-CMOS flows | Host EDA programs in the parent folder of this repository (see below) |

No GPU and no IBM Quantum account are required for the Qiskit cost commands.

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

## External EDA tools (on the host)

Lookup code lives in `eda_hub/tools.py`. Programs are found **only** under the **parent folder of this repository** (for example, if this repo is `…/eda/calculate-rpla-cost`, tools live under `…/eda/`). System paths such as `/usr/bin` are not used.

| Tool | Typical location under the parent folder | Used for |
|---|---|---|
| **ABC** | `bin/abc` or `abc/abc` | SOP/ESOP front end (`&exorcism`), helper flows |
| **Yosys** | `bin/yosys` or `yosys/yosys` | Netlist synthesis / map |
| **OpenROAD** | `bin/openroad` or `OpenROAD/…/openroad` | Place / route style metrics |
| **OpenSTA** (`sta`) | `bin/sta` or `OpenSTA/…/sta` | Timing |
| **ngspice** | `bin/ngspice` or `ngspice/…/ngspice` | PTL / CNTFET / memristor cell simulation |
| **xschem** | `bin/xschem` or `xschem/…/xschem` | Optional schematic capture |

Check that tools are visible from this repository:

```bash
source .venv/bin/activate
python - <<'PY'
from eda_hub.paths import eda_root
from eda_hub.tools import (
    resolve_abc_executable, resolve_yosys_executable,
    resolve_openroad_executable, resolve_ngspice_executable,
    resolve_sta_executable, resolve_xschem_executable,
)
print("Host EDA folder (parent of this repo):", eda_root())
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

Build or install each program into the **parent folder of this repository**, then place or symlink executables under that folder’s `bin/` directory if needed. Upstream projects:

| Tool | Upstream |
|---|---|
| ABC | https://github.com/berkeley-abc/abc |
| Yosys | https://github.com/YosysHQ/yosys |
| OpenROAD | https://github.com/The-OpenROAD-Project/OpenROAD |
| OpenSTA | https://github.com/The-OpenROAD-Project/OpenSTA |
| ngspice | https://ngspice.sourceforge.io / https://github.com/imr/ngspice |
| xschem | https://github.com/StefanSchippers/xschem |

Follow each project’s own install docs. Keep the resulting binaries inside the parent folder of this repository. EXORCISM-4 is used through ABC’s `&exorcism` command (`third_party/exorcism` holds reference sources only).

## Algorithms and how to run them

### 1. Library RPLA costs — Mitra2016 / Tara2016 / Optimized (Prefix Cube)

Python only. Metrics: gates (GA), garbage (GB), ancilla (AI), quantum cost (QC).

**Batch:**

```bash
source .venv/bin/activate
python scripts/batch_all_plas_costs.py
```

**Single circuit:**

```python
import copy
from types import SimpleNamespace
from eda_hub.pages.qiskit.comparison import load_rpla_from_esop_file
from eda_hub.pages.benchmarks.existing_calculation import ExistingCalculation
from eda_hub.pages.benchmarks.mitra2016_calculation import Mitra2016Calculation
from eda_hub.pages.benchmarks.tara2016_calculation import Tara2016Calculation
from eda_hub.pages.benchmarks.optimized_rpla_calculation import OptimizedRPLACalculation

path = "benchmarks/mcnc/Combinational/pla/All_PLAs/misex1.esop"
rpla = load_rpla_from_esop_file(path)

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

Needs Qiskit.

```bash
source .venv/bin/activate

# one circuit by name (defaults: suite mcnc, category Combinational/pla/All_PLAs)
eda-qiskit-analysis --circuit misex1

# any local file
eda-qiskit-analysis --file benchmarks/mcnc/Combinational/pla/All_PLAs/rd53.esop

# whole category to CSV (resumable; 600 s timeout per circuit)
eda-qiskit-analysis --all --csv /tmp/qiskit-all-plas.csv
```

If the command is not on your PATH:

```bash
python scripts/run_qiskit_analysis.py --circuit misex1
```

| Key | What it measures |
|---|---|
| `standard_quantum` | CX + CCX count (weight 1) after transpile |
| `umg_ung` | CX + 5×(UMG + UNG) |
| `gaur2024` | FOM = qubit width × Toffoli depth |
| `zhou2026` | Zhou cost model `C` (microseconds) / LNN routing |

Transpile (when the circuit has at most 96 qubits and 8000 gates): optimization level 2, transpiler seed 42. Code: `eda_hub/pages/qiskit/`.

### 3. SOP → ESOP (needs ABC and/or Yosys)

```bash
source .venv/bin/activate
python scripts/convert_to_esop.py
# also: scripts/generate_esop_accurate.py, scripts/batch_convert_arithmetic_smart.py
```

Code: `eda_hub/pages/benchmarks/sop_esop.py`.

### 4. CMOS / PTL / post-CMOS (need Yosys, OpenROAD, ngspice, …)

Code under `eda_hub/pages/cmos_ptl_tgl/` and `eda_hub/pages/post_cmos/`. Import those modules after the host tools above are installed and resolve correctly.

## License

Proprietary — Mitverse EDA.
