"""CLI: run Qiskit realization comparison on any local workstation."""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path
from typing import Any

from eda_hub.pages.benchmarks.benchmark_index import build_index
from eda_hub.pages.benchmarks.esop_cost import EsopCostError
from eda_hub.pages.qiskit.comparison import (
    compare_benchmark_circuit,
    compare_esop_file,
    preferred_benchmark_filename,
)

HEADERS = [
    "circuit",
    "source",
    "std_gates",
    "std_garbages",
    "std_ancilla_inputs",
    "std_quantum_cost",
    "std_cnot",
    "std_toffoli",
    "umg_gates",
    "umg_garbages",
    "umg_ancilla_inputs",
    "umg_quantum_cost",
    "umg_umg",
    "umg_ung",
    "umg_cnot",
    "gaur_gates",
    "gaur_garbages",
    "gaur_ancilla_inputs",
    "gaur_quantum_cost",
    "gaur_cnot",
    "gaur_toffoli",
    "gaur_toffoli_depth",
    "gaur_width",
    "gaur_fom",
    "zhou_gates",
    "zhou_garbages",
    "zhou_ancilla_inputs",
    "zhou_quantum_cost",
    "zhou_cnot",
    "zhou_toffoli",
    "zhou_swap",
    "zhou_depth",
    "zhou_C",
]


def entry_to_row(entry: dict[str, Any]) -> list[Any]:
    std = entry["realizations"]["standard_quantum"]
    umg = entry["realizations"]["umg_ung"]
    gaur = entry["realizations"]["gaur2024"]
    zhou = entry["realizations"]["zhou2026"]
    return [
        entry["circuit"],
        entry["source"],
        std["gates"],
        std["garbages"],
        std["ancilla_inputs"],
        std["quantum_cost"],
        std["gate_mix"]["cnot_gates"],
        std["gate_mix"].get("toffoli_gates", 0),
        umg["gates"],
        umg["garbages"],
        umg["ancilla_inputs"],
        umg["quantum_cost"],
        umg["gate_mix"].get("umg_templates", 0),
        umg["gate_mix"].get("ung_templates", 0),
        umg["gate_mix"]["cnot_gates"],
        gaur["gates"],
        gaur["garbages"],
        gaur["ancilla_inputs"],
        gaur["quantum_cost"],
        gaur["gate_mix"]["cnot_gates"],
        gaur["gate_mix"].get("toffoli_gates", 0),
        gaur["gate_mix"].get("toffoli_depth", 0),
        gaur["gate_mix"].get("qubit_width", 0),
        gaur["gate_mix"].get("fom", gaur["quantum_cost"]),
        zhou["gates"],
        zhou["garbages"],
        zhou["ancilla_inputs"],
        zhou["quantum_cost"],
        zhou["gate_mix"]["cnot_gates"],
        zhou["gate_mix"].get("toffoli_gates", 0),
        zhou["gate_mix"].get("swap_gates", 0),
        zhou["gate_mix"].get("circuit_depth", 0),
        zhou["gate_mix"].get("C", zhou["quantum_cost"]),
    ]


def _compute_entry(args: tuple[str, str, str, str]) -> dict[str, Any]:
    suite, category, circuit_name, filename = args
    return compare_benchmark_circuit(
        suite=suite,
        category=category,
        circuit=circuit_name,
        filename=filename,
    )


def _print_summary(entry: dict[str, Any]) -> None:
    reals = entry["realizations"]
    print(f"circuit: {entry['circuit']}  source: {entry['source']}")
    for key in ("standard_quantum", "umg_ung", "gaur2024", "zhou2026"):
        item = reals[key]
        print(f"  {key:18s} quantum_cost={item['quantum_cost']}")


def _run_file(path: Path) -> int:
    entry = compare_esop_file(path)
    _print_summary(entry)
    return 0


def _run_circuit(suite: str, category: str, circuit: str, filename: str | None) -> int:
    entry = compare_benchmark_circuit(
        suite=suite,
        category=category,
        circuit=circuit,
        filename=filename,
    )
    _print_summary(entry)
    return 0


def _load_done_circuits(csv_path: Path) -> set[str]:
    if not csv_path.is_file():
        return set()
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return {row["circuit"] for row in reader if row.get("circuit")}


def _run_category(
    *,
    suite: str,
    category: str,
    csv_path: Path,
    json_path: Path | None,
    timeout_sec: int,
) -> int:
    circuits_map = build_index().get("suites", {}).get(suite, {}).get(category)
    if not circuits_map:
        print(f"No circuits for {suite}/{category}", file=sys.stderr)
        return 1

    circuit_names = sorted(circuits_map.keys(), key=str.lower)
    done = _load_done_circuits(csv_path)
    write_header = not csv_path.is_file() or csv_path.stat().st_size == 0
    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    if json_path and json_path.is_file():
        try:
            prior = json.loads(json_path.read_text(encoding="utf-8"))
            entries.extend(prior.get("entries", []))
            skipped.extend(prior.get("skipped", []))
        except json.JSONDecodeError:
            pass

    pending = [name for name in circuit_names if name not in done]
    print(
        f"Exporting {len(circuit_names)} circuits ({len(done)} done, "
        f"{len(pending)} pending) -> {csv_path}",
        flush=True,
    )

    started = time.time()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a" if done else "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(HEADERS)
        for idx, circuit_name in enumerate(pending, start=len(done) + 1):
            files = circuits_map[circuit_name]
            filename = preferred_benchmark_filename(files)
            if not filename:
                skipped.append({"circuit": circuit_name, "error": "No supported source file"})
                print(f"[{idx}/{len(circuit_names)}] SKIP {circuit_name}: no source", flush=True)
                continue

            t0 = time.time()
            args = (suite, category, circuit_name, filename)
            try:
                if timeout_sec > 0:
                    with mp.get_context("spawn").Pool(1) as pool:
                        async_result = pool.apply_async(_compute_entry, (args,))
                        entry = async_result.get(timeout=timeout_sec)
                else:
                    entry = _compute_entry(args)
            except mp.TimeoutError:
                skipped.append(
                    {
                        "circuit": circuit_name,
                        "filename": filename,
                        "error": f"Timed out after {timeout_sec}s",
                    }
                )
                print(
                    f"[{idx}/{len(circuit_names)}] TIMEOUT {circuit_name} (>{timeout_sec}s)",
                    flush=True,
                )
                continue
            except EsopCostError as exc:
                skipped.append({"circuit": circuit_name, "filename": filename, "error": str(exc)})
                print(f"[{idx}/{len(circuit_names)}] FAIL {circuit_name}: {exc}", flush=True)
                continue
            except Exception as exc:  # noqa: BLE001 — batch runner must continue
                skipped.append({"circuit": circuit_name, "filename": filename, "error": str(exc)})
                print(f"[{idx}/{len(circuit_names)}] FAIL {circuit_name}: {exc}", flush=True)
                continue

            writer.writerow(entry_to_row(entry))
            fh.flush()
            entries.append(entry)
            elapsed = time.time() - t0
            std_qc = entry["realizations"]["standard_quantum"]["quantum_cost"]
            print(
                f"[{idx}/{len(circuit_names)}] OK {circuit_name} "
                f"std_qc={std_qc} ({elapsed:.1f}s)",
                flush=True,
            )
            if json_path:
                payload = {
                    "suite": suite,
                    "category": category,
                    "circuit_count": len(circuits_map),
                    "computed_count": len(entries),
                    "skipped": skipped,
                    "entries": entries,
                }
                json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    total = time.time() - started
    print(
        f"Done: {len(entries)}/{len(circuits_map)} computed, "
        f"{len(skipped)} skipped, {total:.1f}s this run",
        flush=True,
    )
    print(f"Wrote {csv_path}", flush=True)
    return 0 if entries or done else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eda-qiskit-analysis",
        description=(
            "Run the four Qiskit realization methodologies locally "
            "(standard / UMG-UNG / Gaur2024 / Zhou2026)."
        ),
    )
    p.add_argument(
        "--file",
        type=Path,
        help="Path to a local .esop or .pla file",
    )
    p.add_argument("--suite", default="mcnc", help="Benchmark suite (default: mcnc)")
    p.add_argument(
        "--category",
        default="Combinational/pla/All_PLAs",
        help="Benchmark category under the suite",
    )
    p.add_argument("--circuit", help="Single circuit name within --suite/--category")
    p.add_argument("--filename", help="Optional source filename override (e.g. 5xp1.esop)")
    p.add_argument(
        "--all",
        action="store_true",
        help="Export every circuit in --suite/--category to CSV",
    )
    p.add_argument(
        "--csv",
        type=Path,
        help="Output CSV path when using --all (default under cwd)",
    )
    p.add_argument(
        "--json",
        type=Path,
        help="Optional JSON sidecar path when using --all",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-circuit timeout seconds for --all (0 disables; default 600)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.file:
            return _run_file(args.file)
        if args.all:
            slug = args.category.replace("/", "-")
            csv_path = args.csv or Path(
                f"qiskit-realization-comparison-{args.suite}-{slug}.csv"
            )
            json_path = args.json
            if json_path is None and args.csv is None:
                json_path = csv_path.with_suffix(".json")
            return _run_category(
                suite=args.suite.lower().strip(),
                category=args.category.strip(),
                csv_path=csv_path,
                json_path=json_path,
                timeout_sec=max(0, int(args.timeout)),
            )
        if args.circuit:
            return _run_circuit(
                args.suite.lower().strip(),
                args.category.strip(),
                args.circuit,
                args.filename,
            )
    except EsopCostError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
