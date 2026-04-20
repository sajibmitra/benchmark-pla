# Benchmarks and cost comparison (web)

The **[MITVerse EDA benchmarks](https://eda.mitverse.com/benchmarks)** site hosts runnable flows where you can **try circuits and compare** the **Mitra2012** cost model with the **Proposed** (template-driven) optimized RPLA implementation in this repo (`python/optimized_rpla_calculation.py`). Use that site to explore benchmark results side-by-side with the metrics produced locally by this project.

# How to install and test (local)

Tools for working with **ESOP / PLA** representations of logic circuits, including **MCNC** and **classic** benchmarks in BLIF and ESOP form.

## Quick start

1. **Clone** this repository and `cd` into the repo root.
2. **Download benchmarks** (Google Drive folder into `benchmarks/`):

   ```bash
   chmod +x download_data.sh   # once, if needed
   ./download_data.sh
   ```

3. **Run the tool** from `python/` (see [Run the main Python tool](#run-the-main-python-tool-interactive-rpla)):

   ```bash
   cd python
   python3 rpla.py
   ```

## Prerequisites

- **Python 3** (3.10+ recommended)
- **`gdown`** (installed automatically by the download script if missing) for fetching the dataset from Google Drive

Optional:

- **Java**: only if you use the Java implementation under `javacode/`.

## Download the benchmarks (script)

The repo root script **`download_data.sh`** pulls the shared benchmark bundle from Google Drive into **`benchmarks/`** using [gdown](https://github.com/wkentaro/gdown) (folder mode).

From the **repository root**:

```bash
chmod +x download_data.sh   # once, if needed
./download_data.sh
```

What it does:

- Creates `benchmarks/` if missing.
- Installs **`gdown`** with `pip install gdown` if the command is not on your `PATH`.
- Runs `gdown --folder` on the Drive folder configured in the script and writes under `benchmarks/`.

After a successful run you should see a layout similar to:

- `benchmarks/mcnc/` — MCNC (`Combinational/`, `Sequential/`, …)
- `benchmarks/classic/classic/` — small classic ESOP PLAs (paths may match the Drive layout exactly)

Older layouts used `benchmarks/eda/{mcnc,classic/...}`; Python resolution falls back there if the new paths are missing. The `benchmarks/` directory is **gitignored** (not part of the clone).

If download fails, check Google Drive access, `gdown` version, and that you run the script from the repo root so `-O benchmarks/` is correct.

## Run the main Python tool (interactive RPLA)

The menu-driven driver is **`python/rpla.py`**. Run it **from the `python` directory** so package imports resolve:

```bash
cd python
python3 rpla.py
```

The interactive menu exposes only two choices:

- **(1)** Calculation of cost of an ESOP PLA (classic)
- **(9)** Exit

**Typical flow (option 1):**

1. Start `python3 rpla.py` and enter **`1`** when prompted.
2. Enter the path to an `.esop` file (relative to `python/` or absolute), for example after `download_data.sh`:

   - `../benchmarks/classic/classic/example.esop`
   - or, with the legacy layout: `../benchmarks/eda/classic/classic/example.esop`

The tool reads the PLA header and product lines, runs Mitra2012-style and optimized cost passes, and prints summaries (including a final comparison table when applicable).

## Batch convert from the repo root (non-interactive)

Optional root-level Python helpers (for example `convert_to_esop.py`) expect a downloaded `benchmarks/` tree; see each script’s `--help` for flags and inputs.

- `python3 verify_esop_accuracy.py` — format checks on `*.esop` under `benchmarks/` (and optional `./eda`; see below)

## Legacy `eda/` symlink at the project root

Some older scripts use `PROJECT_ROOT / "eda"`:

- `generate_esop_accurate.py`
- `fast_esop_generator.py`

`verify_esop_accuracy.py` searches `benchmarks/**/*.esop` first and also `./eda` if present. To point `eda` at the dataset:

```bash
ln -sfn benchmarks eda
```

(or link `eda` to whichever folder holds your trees).

## Java (optional)

Prebuilt output is described in `javacode/dist/README.TXT`. From `javacode/dist/`:

```bash
java -jar BenchmarkPLA.jar
```

Alternatively, compile the `benchmarkpla` package from `javacode/` with your IDE or `javac` and run `benchmarkpla.RPLA`.

## Submodule

`third_party/exorcism` is a reference checkout of EXORCISM-4 sources. Initialize with:

```bash
git submodule update --init --recursive
```
