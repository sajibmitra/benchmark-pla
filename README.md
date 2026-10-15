# calculate-rpla-cost (`eda_hub`)

Standalone, page-aligned calculation package for [eda.mitverse.com](https://eda.mitverse.com).

The FastAPI host remains **mit-panel**; this repo owns the pure calculation code. mit-panel services are thin wrappers that import `eda_hub`.

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

| Key | Function | Formula |
|---|---|---|
| `standard_quantum` | `calculate_standard_quantum_cost` | Σ(CNOT) + Σ(Toffoli) |
| `umg_ung` | `calculate_umg_ung_cost` | Σ(CNOT) + 5×Σ(UMG+UNG) |
| `gaur2024` | `calculate_gaur2024_cost` | FOM = width × Toffoli_depth |
| `zhou2026` | `calculate_zhou2026_cost` | C = T_adj + W_error×E (EDDQC) |

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
