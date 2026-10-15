# Page map — eda.mitverse.com ↔ `eda_hub`

Calculation code for the EDA hub lives in this repository (`eda_hub`).  
**mit-panel** hosts FastAPI routes, DB caches, event logging, auth, and bibliometric tools as thin wrappers that `import eda_hub`.

Reviewers reproducing the manuscript should start at [LOCAL_QISKIT.md](LOCAL_QISKIT.md). Qiskit cost analysis needs Python ≥ 3.10 and `pip install -e '.[qiskit]'`. ABC, Yosys, OpenROAD, OpenSTA, ngspice, and xschem are optional and are resolved only under `EDA_ROOT`.

| Hub page / route | Package | Notes |
|---|---|---|
| `/benchmarks` | `eda_hub.pages.benchmarks` | Mitra / Tara / Optimized RPLA, SOP→ESOP, ESOP cost, index |
| `/cost-metric` | `eda_hub.pages.cost_metric` | Gate cost tables across technologies |
| `/post-cmos-metric` | `eda_hub.pages.post_cmos` | Memristor / CNTFET characterization & architecture cost |
| `/cmos-ptl-tgl` | `eda_hub.pages.cmos_ptl_tgl` | ngspice, Yosys, OpenROAD, reversible helpers |
| `/qiskit` | `eda_hub.pages.qiskit` | Standard / UMG-UNG / Gaur2024 / Zhou2026; local CLI `eda-qiskit-analysis` (see `docs/LOCAL_QISKIT.md`) |
| (bibliometric) | *not in this repo* | Remains in mit-panel; see `pages/bibliometric/README.md` |

## Shared / tools

| Module | Role |
|---|---|
| `eda_hub.shared` | RPLA core (`rpla`, `function`, `product`, `literal`, `blif_parser`) |
| `eda_hub.paths` | `repo_root`, `eda_root`, `benchmarks_root` |
| `eda_hub.tools` | Resolve `abc` / `yosys` / `openroad` / `ngspice` / `sta` / `xschem` **only under `EDA_ROOT`** |
| `eda_hub.adapters.events` | No-op standalone; delegates to mit-panel event stores when available |
| `python/` | Compat shims by working principle (`shared/`, `mitra2012/`, `mitra2016/`, `tara2016/`, `optimized_rpla/`, `qiskit_realization/`); flat stubs keep legacy import names — see `python/README.md` |

## Ops env

- `EDA_ROOT` — Data/eda tree (default: parent of this repo)
- `EDA_CALCULATE_RPLA_COST_ROOT` — this repository root
- `EDA_BENCHMARKS_ROOT` — benchmark circuit tree
- `EDA_QISKIT_SITE_PACKAGES` — optional Qiskit site-packages if not installed in the active venv

Local workstation Qiskit setup: [LOCAL_QISKIT.md](LOCAL_QISKIT.md).
