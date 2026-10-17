# `Algorithms/` — compatibility shims by working principle

Reviewers should follow the repository [README](../README.md) and [docs/LOCAL_QISKIT.md](../docs/LOCAL_QISKIT.md), starting from [Manuscript.pdf](../Manuscript.pdf). New runs should import `eda_hub`, not these shims.

Canonical calculation code lives in **`eda_hub`**. This tree (formerly `python/`) keeps legacy import names and groups them by working principle.

| Folder | Principle | Canonical package |
|--------|-----------|-------------------|
| `shared/` | RPLA data model & parsers | `eda_hub.shared` |
| `mitra2012/` | Mitra2012 ESOP cost | `eda_hub.pages.benchmarks` (`cost_calculation`, `existing_calculation`) |
| `mitra2016/` | Mitra2016 UMG/UNG templates | `eda_hub.pages.benchmarks.mitra2016_calculation` |
| `tara2016/` | Tara2016 TB/F2G templates | `eda_hub.pages.benchmarks.tara2016_calculation` |
| `optimized_rpla/` | Proposed optimized RPLA (Prefix Cube) | `eda_hub.pages.benchmarks.optimized_rpla_calculation` |
| `qiskit_realization/` | Qiskit methodologies (4) | `eda_hub.pages.qiskit` |
| `viz/pypainter/` | Plotting helpers | (local scripts) |
| `_archive/` | Old copies / macOS junk | — |

**Flat stubs** at this directory root (`rpla.py`, `cost_calculation.py`, …)
re-export the same symbols so `sys.path` + `importlib.import_module("rpla")`
keeps working. New code should import `eda_hub` directly.

```bash
cd Algorithms
python3 -c "import rpla; import qiskit_realization; print('OK')"
```
