# benchmark-pla

Tools for working with **ESOP / PLA** representations of logic circuits, including **MCNC**, **EPFL**, and **classic** benchmarks in BLIF and ESOP form. BLIF processing relies on [**Berkeley ABC**](https://github.com/berkeley-abc/abc).

## Prerequisites

- **Python 3** (3.10+ recommended)
- [**ABC**](https://github.com/berkeley-abc/abc): build the `abc` binary and point the tools at it (see below)
- **`gdown`** (installed automatically by the download script if missing) for fetching the dataset from Google Drive

Optional:

- **`ABC_GIA_EXORCISM_TIMEOUT`**: for very large circuits, seconds for ABC’s GIA `&exorcism` step (e.g. `export ABC_GIA_EXORCISM_TIMEOUT=3600`). See `third_party/README.md`.
- **Java**: only if you use the Java implementation under `javacode/`.

## Download the benchmarks

From the repository root:

```bash
chmod +x download_data.sh   # once, if needed
./download_data.sh
```

This creates `benchmarks/eda/` and fills it from the shared Drive folder (EPFL, MCNC, classic, etc.). The `benchmarks/` directory is gitignored.

If `gdown` is not installed, the script runs `pip install gdown` for the current environment.

## Configure ABC

The code defaults to an ABC binary at `/tmp/abc-berkeley/abc`. Override with:

```bash
export ABC_BIN=/path/to/your/abc
```

Build ABC from source: clone [berkeley-abc/abc](https://github.com/berkeley-abc/abc), run `make`, then set `ABC_BIN` to the produced `abc` executable.

## Run the main Python tool (interactive RPLA)

The menu-driven driver lives in `python/rpla.py`. Run it **from the `python` directory** so local imports resolve:

```bash
cd python
python3 rpla.py
```

Use the prompts to:

- Compute costs for ESOP PLAs (classic / MCNC / EPFL)
- Convert expressions or BLIF to PLA / ESOP
- Batch-convert BLIF under `benchmarks/eda/` (with or without EXORCISM-4 via ABC)

Batch conversion options **(7)** and **(8)** expect the benchmark tree at `benchmarks/eda/epfl` and `benchmarks/eda/mcnc` after you run `download_data.sh`.

## Batch convert from the repo root (non-interactive)

```bash
export ABC_BIN=/path/to/abc
python3 convert_to_esop.py --source both
```

Use `--source epfl` or `--source mcnc` to limit the set. Add `--no-exorcism` to skip ABC `&exorcism`. See `python3 convert_to_esop.py --help`.

Other root-level helpers (also use `benchmarks/eda/` and `ABC_BIN`):

- `python3 batch_convert_arithmetic_smart.py` — EPFL arithmetic BLIF subset with timeouts
- `python3 verify_esop_accuracy.py` — format checks on `*.esop` (expects data under `eda/` at repo root; see below)

## Legacy scripts that expect `eda/` at the project root

Some scripts use `PROJECT_ROOT / "eda"` instead of `benchmarks/eda/`:

- `generate_esop_accurate.py`
- `fast_esop_generator.py`
- `verify_esop_accuracy.py`

After downloading, you can link the dataset once:

```bash
ln -sfn benchmarks/eda eda
```

Then those scripts will see the same files as the download layout.

## Java (optional)

Prebuilt output is described in `javacode/dist/README.TXT`. From `javacode/dist/`:

```bash
java -jar BenchmarkPLA.jar
```

Alternatively, compile the `benchmarkpla` package from `javacode/` with your IDE or `javac` and run `benchmarkpla.RPLA`.

## Submodule

`third_party/exorcism` is a reference checkout of EXORCISM-4 sources; conversion uses ABC’s `&exorcism`, not a separate binary from this tree. Initialize with:

```bash
git submodule update --init --recursive
```
