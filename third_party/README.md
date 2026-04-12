# Third-party reference sources

## exorcism (EXORCISM-4)

Submodule: [lsils/exorcism](https://github.com/lsils/exorcism) — C++ sources extracted from [Berkeley ABC](https://github.com/berkeley-abc/abc). This is the standard public mirror of the EXORCISM-4 heuristic ESOP minimizer.

**Runtime:** This repository does not build a standalone `exorcism` binary. Conversion uses your **ABC** installation’s `&exorcism` command (same algorithm). Rebuild ABC from a current `berkeley-abc/abc` checkout to pick up upstream fixes.

For very large benchmarks, the Python driver may run `&exorcism` on the GIA after `read; strash; &get` (see `python/blif_parser.py`). If that step times out, set **`ABC_GIA_EXORCISM_TIMEOUT`** (seconds), e.g. `3600`.

**Optional CMake library:** To compile `libabcesop` from this tree, create a build directory and run CMake with `exorcism` as a subdirectory (see `exorcism/README.md`).
