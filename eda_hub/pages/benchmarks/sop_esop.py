"""SOP -> ESOP conversion helpers for EDA benchmarks."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eda_hub.pages.benchmarks.benchmark_index import generated_benchmark_root
from eda_hub.adapters.events import record_abc_event
from eda_hub.tools import resolve_abc_executable, resolve_yosys_executable
from eda_hub.adapters.events import record_ngspice_event
from eda_hub.adapters.events import record_opensta_event
from eda_hub.adapters.events import record_yosys_event

class ConversionError(RuntimeError):
    """Raised when SOP->ESOP conversion fails."""


def _resolve_esop_timeout_s() -> int:
    """Return ESOP conversion timeout in seconds with validation."""
    raw = (os.environ.get("EDA_ESOP_TIMEOUT") or "").strip()
    if not raw:
        # Large MCNC benchmarks can legitimately run for a long time in ABC.
        return 3600
    try:
        timeout_s = int(raw)
    except ValueError:
        raise ConversionError(
            f"Invalid EDA_ESOP_TIMEOUT value {raw!r}; expected integer seconds."
        ) from None
    if timeout_s <= 0:
        raise ConversionError("EDA_ESOP_TIMEOUT must be greater than 0 seconds.")
    return timeout_s


def _ensure_tool(name: str, hint: str) -> str:
    from eda_hub.tools import ToolNotFoundError
    try:
        if name == "yosys":
            return resolve_yosys_executable()
        if name == "abc":
            return resolve_abc_executable()
    except ToolNotFoundError as exc:
        raise ConversionError(f"{exc}. {hint}") from exc
    raise ConversionError(f"{name} executable not found under EDA_ROOT. {hint}")


def _exe_base(cmd: list[str]) -> str:
    return Path(cmd[0]).name if cmd else ""


def _run_cmd(
    cmd: list[str],
    timeout_s: int = 120,
    *,
    suite: str | None = None,
    category: str | None = None,
    circuit: str | None = None,
    source_file: str | None = None,
) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout_s,
        )
        if cmd and _exe_base(cmd) == "abc":
            record_abc_event(
                status="ok",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=(out.stderr or out.stdout or "").strip()[:1000],
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) == "yosys":
            record_yosys_event(
                status="ok",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=(out.stderr or out.stdout or "").strip()[:1000],
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) in {"sta", "opensta"}:
            record_opensta_event(
                status="ok",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=(out.stderr or out.stdout or "").strip()[:1000],
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) == "ngspice":
            record_ngspice_event(
                status="ok",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=(out.stderr or out.stdout or "").strip()[:1000],
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        return out
    except subprocess.TimeoutExpired as exc:
        if cmd and _exe_base(cmd) == "abc":
            record_abc_event(
                status="timeout",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail="Command timed out",
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) == "yosys":
            record_yosys_event(
                status="timeout",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail="Command timed out",
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) in {"sta", "opensta"}:
            record_opensta_event(
                status="timeout",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail="Command timed out",
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) == "ngspice":
            record_ngspice_event(
                status="timeout",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail="Command timed out",
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        raise ConversionError(f"Command timed out: {' '.join(cmd)}") from exc
    except FileNotFoundError as exc:
        if cmd and _exe_base(cmd) == "abc":
            record_abc_event(
                status="error",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=f"Tool not found: {cmd[0]}",
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) == "yosys":
            record_yosys_event(
                status="error",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=f"Tool not found: {cmd[0]}",
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) in {"sta", "opensta"}:
            record_opensta_event(
                status="error",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=f"Tool not found: {cmd[0]}",
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) == "ngspice":
            record_ngspice_event(
                status="error",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=f"Tool not found: {cmd[0]}",
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        raise ConversionError(f"Tool not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or "unknown error"
        if cmd and _exe_base(cmd) == "abc":
            record_abc_event(
                status="error",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=detail[:1000],
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) == "yosys":
            record_yosys_event(
                status="error",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=detail[:1000],
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) in {"sta", "opensta"}:
            record_opensta_event(
                status="error",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=detail[:1000],
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        if cmd and _exe_base(cmd) == "ngspice":
            record_ngspice_event(
                status="error",
                command=" ".join(cmd),
                duration_ms=int((time.monotonic() - started) * 1000),
                detail=detail[:1000],
                suite=suite,
                category=category,
                circuit=circuit,
                source_file=source_file,
            )
        raise ConversionError(f"Command failed: {' '.join(cmd)}\n{detail}") from exc


def _abc_read_cmd(input_path: Path) -> str:
    ext = input_path.suffix.lower()
    if ext == ".blif":
        return "read_blif"
    if ext == ".pla":
        return "read_pla"
    if ext in {".v", ".sv"}:
        return "read_verilog"
    raise ConversionError(f"Unsupported input format for ABC: {ext or 'no extension'}")


def _abc_sop_to_esop(
    input_blif: Path,
    output_path: Path,
    *,
    suite: str | None = None,
    category: str | None = None,
    circuit: str | None = None,
    source_file: str | None = None,
) -> None:
    # Use ABC to derive ESOP and emit a PLA-like textual representation.
    read_cmd = _abc_read_cmd(input_blif)
    script = (
        f"{read_cmd} {shlex.quote(str(input_blif))}; "
        "strash; "
        "&get; "
        "&esop; "
        "&put; "
        "collapse; "
        f"write_pla {shlex.quote(str(output_path))}"
    )
    abc_exe = _ensure_tool(
        "abc",
        "Install Berkeley ABC or symlink it in ~/eda/bin and ensure mitverse-eda-api PATH includes that directory.",
    )
    timeout_s = _resolve_esop_timeout_s()
    _run_cmd(
        [abc_exe, "-c", script],
        timeout_s=timeout_s,
        suite=suite,
        category=category,
        circuit=circuit,
        source_file=source_file,
    )


def _emit(
    report: Callable[[dict[str, Any]], None] | None, message: dict[str, Any]
) -> None:
    if report is not None:
        report(message)


def convert_sop_to_esop(
    suite: str,
    category: str,
    circuit_name: str,
    source_file: Path,
    *,
    report: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[str, str]:
    """
    Convert SOP benchmark to ESOP text.

    Optional ``report`` receives progress dicts (e.g. for WebSocket updates):
    ``{"type": "progress", "phase": "abc", "message": "..."}``.

    Returns:
        (output_filename, esop_text)
    """
    suite_key = suite.lower().strip()
    if suite_key not in {"mcnc", "epfl"}:
        raise ConversionError(f"Unsupported benchmark suite: {suite}")

    _emit(
        report,
        {
            "type": "progress",
            "phase": "prepare",
            "percent": 5,
            "message": f"Starting SOP→ESOP for {circuit_name}",
            "circuit": circuit_name,
            "suite": suite_key,
            "category": category,
        },
    )

    with tempfile.TemporaryDirectory(prefix="eda-esop-") as tmp:
        tmpdir = Path(tmp)
        abc_input = source_file

        if suite_key == "epfl":
            # EPFL benchmarks are commonly Verilog; convert to BLIF with Yosys first.
            if source_file.suffix.lower() not in {".v", ".sv", ".blif", ".pla"}:
                raise ConversionError(
                    "EPFL conversion supports source files: .v, .sv, .blif, .pla"
                )
            mid_blif = tmpdir / f"{circuit_name}.blif"
            if source_file.suffix.lower() in {".v", ".sv"}:
                _emit(
                    report,
                    {
                        "type": "progress",
                        "phase": "yosys",
                        "percent": 15,
                        "message": "Running Yosys (Verilog → BLIF)…",
                    },
                )
                yosys_script = (
                    f"read_verilog {shlex.quote(str(source_file))}; "
                    "hierarchy -auto-top; "
                    "proc; opt; techmap; opt; "
                    f"write_blif {shlex.quote(str(mid_blif))}"
                )
                try:
                    ys = _ensure_tool(
                        "yosys",
                        "Install Yosys or add ~/eda/bin to PATH for mitverse-eda-api.",
                    )
                    _run_cmd(
                        [ys, "-q", "-p", yosys_script],
                        timeout_s=300,
                        suite=suite_key,
                        category=category,
                        circuit=circuit_name,
                        source_file=str(source_file),
                    )
                    abc_input = mid_blif
                except ConversionError as exc:
                    # Fall back to a sibling BLIF file when Verilog parsing fails.
                    sibling_blif = source_file.with_suffix(".blif")
                    if sibling_blif.is_file():
                        abc_input = sibling_blif
                    else:
                        raise ConversionError(
                            f"Yosys preprocessing failed and no sibling BLIF fallback exists: {exc}"
                        ) from exc

        out_file = tmpdir / f"{circuit_name}.esop"
        esop_timeout_s = _resolve_esop_timeout_s()
        _emit(
            report,
            {
                "type": "progress",
                "phase": "abc",
                "percent": 28,
                "elapsed_s": 0,
                "timeout_s": esop_timeout_s,
                "message": (
                    f"Running ABC (SOP → ESOP); large benchmarks may take up to {esop_timeout_s // 60} minutes…"
                ),
            },
        )

        stop_ticks = threading.Event()
        tick_state: dict[str, bool] = {"abc_running": True}

        def abc_elapsed_progress_ticks() -> None:
            t0 = time.monotonic()
            to = max(int(esop_timeout_s), 1)
            while not stop_ticks.wait(1.0):
                if not tick_state["abc_running"]:
                    break
                elapsed = time.monotonic() - t0
                # Time-budget curve: rises toward 94% while ABC still runs (no true % from ABC).
                frac = min(1.0, elapsed / float(to))
                pct = int(28 + min(66, round(66 * frac)))
                pct = min(94, max(28, pct))
                es = int(elapsed)
                _emit(
                    report,
                    {
                        "type": "progress",
                        "phase": "abc",
                        "percent": pct,
                        "elapsed_s": es,
                        "timeout_s": to,
                        "message": (
                            f"Running ABC (SOP → ESOP) — ~{pct}% of time budget "
                            f"({es}s / {to}s); large benchmarks may take up to {to // 60} minutes…"
                        ),
                    },
                )

        tick_thread = threading.Thread(target=abc_elapsed_progress_ticks, daemon=True)
        tick_thread.start()
        try:
            _abc_sop_to_esop(
                abc_input,
                out_file,
                suite=suite_key,
                category=category,
                circuit=circuit_name,
                source_file=str(source_file),
            )
        finally:
            tick_state["abc_running"] = False
            stop_ticks.set()
            tick_thread.join(timeout=3.0)

        _emit(
            report,
            {
                "type": "progress",
                "phase": "abc",
                "percent": 96,
                "message": "ABC finished; reading ESOP output…",
            },
        )

        if not out_file.is_file():
            raise ConversionError("Conversion completed but output file was not produced")

        try:
            text = out_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConversionError(f"Failed to read conversion output: {exc}") from exc

        _emit(
            report,
            {
                "type": "progress",
                "phase": "save",
                "percent": 98,
                "message": "Writing ESOP output…",
            },
        )
        primary = source_file.with_name(f"{circuit_name}.esop")
        cat_parts = tuple(
            p for p in category.replace("\\", "/").split("/") if p and p != "." and p != ".."
        )
        rel_cat = Path(*cat_parts) if cat_parts else Path(".")
        fallback = generated_benchmark_root() / suite_key / rel_cat / f"{circuit_name}.esop"

        last_exc: OSError | None = None
        for dest in (primary, fallback):
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")
                return dest.name, text
            except OSError as exc:
                last_exc = exc
                continue
        raise ConversionError(
            f"Failed to save ESOP next to the source ({primary}) or under the generated overlay "
            f"({fallback}): {last_exc}"
        ) from last_exc
