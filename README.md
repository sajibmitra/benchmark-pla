# calculate-rpla-cost (`eda_hub`)

Standalone calculation package for the Prefix Cube RPLA experiments and for [eda.mitverse.com](https://eda.mitverse.com). A reviewer can reproduce the benchmark load and the Qiskit cost model on a laptop. The step-by-step guide is [docs/LOCAL_QISKIT.md](docs/LOCAL_QISKIT.md).

## System requirements

| Item | Requirement |
|---|---|
| OS | macOS or Linux (the setup script is bash) |
| Python | 3.10 or newer |
| Qiskit | `qiskit>=1.0,<3`. The manuscript used Qiskit 2.3.1 |
| Hardware | No GPU and no IBM Quantum account. `misex1` and `rd53` finish quickly. A full MCNC export is CPU time; each circuit has a 600 s timeout and the CSV is resumable |
| EDA binaries | Not required for Qiskit. ABC, Yosys, OpenROAD, OpenSTA, ngspice, and xschem are resolved only under `EDA_ROOT` |

```bash
cd /path/to/benchmark-pla
./scripts/setup_local.sh
source .venv/bin/activate
eda-qiskit-analysis --circuit misex1
```

The manuscript's 20 covers live in `benchmarks/mcnc/Combinational/pla/All_PLAs/`. The loader prefers `.esop` and otherwise uses `.pla`.

The FastAPI host remains **mit-panel**; this repo owns the calculation code. mit-panel services are thin wrappers that import `eda_hub`.

## Layout

```text
eda_hub/
  paths.py          # repo_root, eda_root, benchmarks_root
  tools.py          # resolve_* only under EDA_ROOT (no /usr fallbacks)
  shared/           # RPLA core
  pages/
    benchmarks/     # /benchmarks
    cost_metric/    # /cost-metric
    post_cmos/      # /post-cmos-metric
    cmos_ptl_tgl/   # /cmos-ptl-tgl
    qiskit/         # /qiskit (four methodologies + local CLI)
    bibliometric/   # README only — not migrated
python/             # compat shims grouped by working principle (see python/README.md)
benchmarks/         # MCNC / classic / EPFL data
docs/PAGE_MAP.md    # hub page ↔ package map
docs/LOCAL_QISKIT.md
papers/             # Gaur2024.pdf, Zhou2026.pdf
```

See [docs/PAGE_MAP.md](docs/PAGE_MAP.md) for the full page mapping and [python/README.md](python/README.md) for principle folders.

## Install (any workstation)

```bash
cd /path/to/calculate-rpla-cost
./scripts/setup_local.sh
source .venv/bin/activate
```

Or manually:

```bash
pip install -e .
# optional Qiskit methodologies:
pip install -e '.[qiskit]'
```

Or set `EDA_CALCULATE_RPLA_COST_ROOT` and put this root on `PYTHONPATH` (mit-panel does this via `_eda_hub_bootstrap`).

## Local Qiskit analysis

No server path, IBM account, or mit-panel required. Full guide: [docs/LOCAL_QISKIT.md](docs/LOCAL_QISKIT.md).

```bash
# single circuit from the shipped MCNC index
eda-qiskit-analysis --circuit 5xp1

# any local ESOP/PLA
eda-qiskit-analysis --file benchmarks/mcnc/Combinational/pla/All_PLAs/rd53.esop

# full category CSV (resumable)
eda-qiskit-analysis --all --csv qiskit-all-plas.csv
```

## Tool resolution

All CLI tools resolve **only** under `$EDA_ROOT` (default: parent of this repo, e.g. `~/eda` → `Data/eda`):

- `$EDA_ROOT/bin/{abc,yosys,openroad,ngspice,sta,xschem}`
- known build trees under `$EDA_ROOT/{abc,yosys,OpenROAD,OpenSTA,ngspice,xschem,…}`

Env overrides (`EDA_ABC`, `EDA_YOSYS`, …) are honored **only** when the path is under `$EDA_ROOT`. Missing tools raise `ToolNotFoundError` (no `/usr/bin` fallback).

**Qiskit cost analysis does not need `EDA_ROOT`** — only Python + `pip install -e '.[qiskit]'`.

## Qiskit methodologies (`/qiskit`)

`eda-qiskit-analysis` prints `quantum_cost` from the package. That field is not the same number in every manuscript column. See [docs/LOCAL_QISKIT.md](docs/LOCAL_QISKIT.md).

| Key | Function | Package `quantum_cost` |
|---|---|---|
| `standard_quantum` | `calculate_standard_quantum_cost` | Σ(CNOT) + Σ(Toffoli), each weighted 1. This is the CX/CCX tally, not `n_CX + 5 n_CCX` |
| `umg_ung` | `calculate_umg_ung_cost` | Σ(CNOT) + 5×Σ(UMG+UNG) |
| `gaur2024` | `calculate_gaur2024_cost` | FOM = qubit width × Toffoli depth. The manuscript realization table does not use FOM |
| `zhou2026` | `calculate_zhou2026_cost` | `C = T/(1-E) + W_error×E` in microseconds. The manuscript realization table does not use `C` |

Full transpile (`optimization_level=2`, `seed_transpiler=42`) runs only when the circuit has at most 96 qubits and 8000 gates. Larger names keep the logical circuit. The NCT basis is `{x,cx,ccx,swap}`. The Prefix Cube basis is `{x,cx,umg,ung,swap}`.

Legacy imports `from qiskit_realization import …` still work via `python/qiskit_realization`.

## Benchmarks

Interactive / batch RPLA cost (Mitra, Tara, Optimized) and SOP→ESOP conversion live under `eda_hub.pages.benchmarks`. Compat shims under `python/` are grouped by working principle (`shared/`, `mitra2012/`, `mitra2016/`, `tara2016/`, `optimized_rpla/`, `qiskit_realization/`); flat stubs at `python/` root keep old import names working.

```bash
# after download_data.sh (or with benchmarks already present)
cd python
python3 -c "import rpla; import qiskit_realization; print('shim OK')"
```

## Env vars (ops)

| Variable | Purpose |
|---|---|
| `EDA_ROOT` | Data/eda tool tree (ABC/Yosys/… only) |
| `EDA_CALCULATE_RPLA_COST_ROOT` | This repository |
| `EDA_BENCHMARKS_ROOT` | Benchmark circuits (default: `<repo>/benchmarks`) |
| `EDA_QISKIT_SITE_PACKAGES` | Optional external Qiskit site-packages |

## License

Proprietary — Mitverse EDA.
