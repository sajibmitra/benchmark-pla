# Reviewer guide: benchmarks, Qiskit, and the other tools

This repository is enough to load the MCNC covers and run the four Qiskit cost models. You do not need mit-panel, an IBM Quantum account, or a GPU.

Start with the paper summary and checklist in [../README.md](../README.md) (Tables IX–XI, misex1 smoke tests, shipped CSVs). This page is the detailed Qiskit field reference.

The paper calls the transpiler `qiskit-transpile`. The code calls `qiskit.transpile`.

## System requirements

| Item | Requirement |
|---|---|
| OS | macOS or Linux. `scripts/setup_local.sh` is bash |
| Python | 3.10 or newer (`python3`) |
| Disk | The benchmark tree under `benchmarks/` |
| Qiskit | Installed by `pip install -e '.[qiskit]'`, which asks for `qiskit>=1.0,<3`. The paper numbers were produced with Qiskit 2.3.1 |
| CPU | One process per circuit. `--all` waits at most 600 s per name and appends finished rows, so a stopped export can be resumed |
| Memory | `misex1` (8 inputs, 20 products) is the running example and is small. Circuits past 96 qubits or 8000 gates are not fully transpiled |
| Not required | GPU, IBM cloud credentials, ABC, Yosys, OpenROAD, OpenSTA, ngspice |

Nangate45, Stanford CNTFET, and VTEAM milliwatts in the paper are a technology map of the same netlist. This package does not run those signoff tools.

## Install

From the repository root (the directory that contains `eda_hub/` and `benchmarks/`):

```bash
./scripts/setup_local.sh
source .venv/bin/activate
eda-qiskit-analysis --circuit misex1
```

Manual equivalent:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e '.[qiskit]'
```

If the console script is not on `PATH`:

```bash
python scripts/run_qiskit_analysis.py --circuit misex1
```

If `benchmarks/` is empty:

```bash
./scripts/download_data.sh
```

That script uses `gdown` and a Google Drive folder. The expected tree is `benchmarks/mcnc`, `benchmarks/classic`, and `benchmarks/epfl`.

## Benchmarks

The indexed MCNC category is `Combinational/pla/All_PLAs`. Files live at:

```text
benchmarks/mcnc/Combinational/pla/All_PLAs/<name>.esop
benchmarks/mcnc/Combinational/pla/All_PLAs/<name>.pla
```

The loader prefers `.esop`, then `.pla`. Do not use the copy under `benchmarks/classic/` when an `All_PLAs` file exists. `build_index()` in `eda_hub.pages.benchmarks.benchmark_index` is the index the CLI uses.

The paper reports 20 representative covers:

`alu4`, `apex1`, `apex3`, `apla`, `b2`, `b3`, `chkn`, `cordic`, `dk17`, `duke2`, `e64`, `f51m`, `ibm`, `misex1`, `misex3c`, `pdc`, `rd53`, `ryy6`, `table3`, `table5`.

`chkn`, `dk17`, `f51m`, `ibm`, `misex3c`, and `ryy6` are `.pla` only. The others have both `.esop` and `.pla`; the CLI selects `.esop`.

One cover:

```bash
eda-qiskit-analysis --circuit misex1
eda-qiskit-analysis --file benchmarks/mcnc/Combinational/pla/All_PLAs/rd53.esop
```

Every indexed circuit in that category, resumable:

```bash
eda-qiskit-analysis --all \
  --suite mcnc \
  --category Combinational/pla/All_PLAs \
  --csv qiskit-realization-comparison-mcnc.csv \
  --timeout 600
```

`--timeout 0` disables the per-circuit limit. A row already present in the CSV is skipped.

Python API, from the repository root:

```python
from eda_hub.pages.qiskit import compare_benchmark_circuit, compare_esop_file

print(compare_benchmark_circuit(
    suite="mcnc",
    category="Combinational/pla/All_PLAs",
    circuit="misex1",
))
print(compare_esop_file(
    "benchmarks/mcnc/Combinational/pla/All_PLAs/rd53.esop"
))
```

## What each methodology returns

`compare_*` builds one RPLA from the cover and scores four realizations. The printed `quantum_cost` is the package field below.

| Key | Code | `quantum_cost` |
|---|---|---|
| `standard_quantum` | `calculate_standard_quantum_cost` | CNOT count + Toffoli count, each with weight 1. Gates, garbage, and ancilla come from `ExistingCalculation` |
| `umg_ung` | `calculate_umg_ung_cost` | CNOT count + 5×(UMG count + UNG count) from the optimized RPLA mapper |
| `gaur2024` | `calculate_gaur2024_cost` | FOM = qubit width × Toffoli depth of the CX/CCX circuit. CNOT count, CNOT depth, Toffoli count, and Toffoli depth are also in `gate_mix`. NMED is not measured, and the modulo adder is not rebuilt |
| `zhou2026` | `calculate_zhou2026_cost` | `C = T/(1-E) + W_error×E` in microseconds, using Zhou Table I and `W_error=1`. `account_eddqc` scores the logical circuit. A linear nearest-neighbor transpile is attempted only for at most 48 qubits and 2000 gates |

Transpile settings for the NCT and Prefix Cube studies:

- `optimization_level=2`
- `seed_transpiler=42`
- NCT basis `{x, cx, ccx, swap}`
- Prefix Cube basis `{x, cx, umg, ung, swap}` via `qiskit.transpiler.Target`
- Full transpile only when qubits ≤ 96 and gates ≤ 8000. `dk17`, `misex1`, and `rd53` are in that set. Larger covers keep the logical circuit

`misex1` after the NCT transpile is `G=134`, `D=46`, `Q=38`. The Prefix Cube ledger stays the netlist count `G=45`, AND-plane depth bound `D_∧ ≤ 7`, and `Q=27`. It is not `QuantumCircuit.depth()` of the transpiled UMG circuit.

## Paper tables versus `quantum_cost`

Use the package field that matches the column.

- The CX/CCX tally is `standard_quantum` `quantum_cost` (CNOT + Toffoli, weight 1).
- The NCT macro cost in the paper is `n_CX + 5 n_CCX`. Read `cnot_gates` and `toffoli_gates` from `standard_quantum` `gate_mix` and apply that weight. Do not read it from `quantum_cost`.
- Prefix Cube macro cost is the `umg_ung` formula: one UMG or UNG has cost 5, one CNOT has cost 1.
- Gaur FOM and Zhou `C` are what `gaur2024` and `zhou2026` store in `quantum_cost`. The realization table in the paper does not put those quantities in the QC column.

The paper realization columns apply two further rules on the NCT cascade from `ExistingCalculation`:

- Gaur QMA3 keeps the CNOT and Toffoli counts. Garbage and ancilla each drop by `n+1`, where `n` is `RPLA.totalLiterals`. Gate count and macro QC stay with NCT.
- Zhou Algorithm 1 is `account_eddqc` on the logical CX/CCX circuit from `build_esop_cnot_toffoli_circuit`, not the microsecond `C`. Each selected switch, SWAP, or teleportation adds one gate of cost 1 and adds no rail. Garbage and ancilla stay with NCT.

`circuit_builder` layout garbage and ancilla are not the NCT garbage and ancilla in that table. Those two counts come from `ExistingCalculation`.

## Other tools

Qiskit analysis never calls them. They are used only when a CMOS, PTL, or post-CMOS page asks for a binary.

`eda_hub.tools` looks only under `EDA_ROOT` (default: the parent of this repository). A tool on `/usr/bin` is ignored. Overrides `EDA_ABC`, `EDA_YOSYS`, `EDA_OPENROAD`, `EDA_NGSPICE`, `EDA_STA`, and `EDA_XSCHEM` are accepted only when the file is inside `EDA_ROOT`. A missing binary raises `ToolNotFoundError`.

| Binary | Role |
|---|---|
| `abc` | ESOP/SOP front end when a published `.esop` is absent |
| `yosys` | Map a gate netlist |
| `openroad`, `sta` | Placement and timing under Nangate45 |
| `ngspice` | PTL, CNTFET, and VTEAM cell simulation |
| `xschem` | Optional schematic capture |

## Environment variables

| Variable | Purpose |
|---|---|
| `EDA_BENCHMARKS_ROOT` | Benchmark tree. Default: `<repo>/benchmarks` |
| `EDA_CALCULATE_RPLA_COST_ROOT` | This repository, if it is not the working tree |
| `EDA_QISKIT_SITE_PACKAGES` | Extra `site-packages` when Qiskit is outside the active venv |
| `EDA_ROOT` | Tool tree for ABC, Yosys, OpenROAD, ngspice, OpenSTA, and xschem. Unused by the Qiskit CLI |
| `PYTHON` | Interpreter for `setup_local.sh` (default `python3`) |
| `VENV_DIR` | Virtualenv path (default `<repo>/.venv`) |
