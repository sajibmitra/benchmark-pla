"""Scan MCNC / EPFL benchmark trees under EDA_BENCHMARKS_ROOT (default ~/eda/calculate-rpla-cost/benchmarks)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

SUITE_NAMES = ("mcnc", "epfl", "classic")

# Subset exposed by GET /api/v1/eda/benchmarks (eda.mitverse.com/benchmarks).
INDEX_SUITE_NAMES = ("mcnc", "classic")
INDEX_CATEGORY_BY_SUITE: dict[str, frozenset[str]] = {
    "mcnc": frozenset({"Combinational/pla/All_PLAs"}),
    "classic": frozenset({"classic"}),
}


def generated_benchmark_root() -> Path:
    """Writable tree mirroring <suite>/<category>/*.esop when the main benchmark dir is read-only."""
    raw = os.environ.get("EDA_BENCHMARKS_GENERATED_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".local/share/mitverse-eda/benchmark-generated").resolve()


def _resolve_under(suite_base: Path, parts: list[str]) -> Path | None:
    if not suite_base.is_dir():
        return None
    try:
        resolved_base = suite_base.resolve()
        full = suite_base.joinpath(*parts).resolve()
    except (OSError, ValueError):
        return None
    try:
        full.relative_to(resolved_base)
    except ValueError:
        return None
    if not full.is_file():
        return None
    return full


def resolve_benchmark_file(suite: str, relative_path: str) -> Path | None:
    """Resolve a file under the primary benchmark tree or the generated overlay."""
    suite_key = suite.lower().strip()
    if suite_key not in SUITE_NAMES:
        return None
    parts = [p for p in relative_path.replace("\\", "/").split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        return None
    primary = (_benchmark_root() / suite_key).resolve()
    found = _resolve_under(primary, parts)
    if found is not None:
        return found
    gen = (generated_benchmark_root() / suite_key).resolve()
    return _resolve_under(gen, parts)


def _benchmark_root() -> Path:
    from eda_hub.paths import benchmarks_root
    return benchmarks_root()


def _scan_leaf(dirpath: Path) -> dict[str, dict[str, str]]:
    """Map stem -> {lowercase extension -> exact filename on disk}."""
    circuits: dict[str, dict[str, str]] = {}
    try:
        for f in dirpath.iterdir():
            if not f.is_file() or f.name.startswith("."):
                continue
            stem = f.stem
            suf = f.suffix
            if not suf or len(suf) < 2:
                continue
            ext = suf[1:]
            key = ext.lower()
            circuits.setdefault(stem, {})[key] = f.name
    except OSError:
        return {}
    return {
        stem: dict(sorted(ext_map.items()))
        for stem, ext_map in sorted(circuits.items(), key=lambda x: x[0].lower())
    }


def scan_suite(suite_path: Path) -> dict[str, dict[str, dict[str, str]]]:
    categories: dict[str, dict[str, dict[str, str]]] = {}
    if not suite_path.is_dir():
        return categories

    def visit(path: Path, rel_key: str | None) -> None:
        files = _scan_leaf(path)
        if files:
            category_name = rel_key if rel_key is not None else (suite_path.name if suite_path.name == "classic" else "all")
            categories[category_name] = files

        try:
            children = sorted(path.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return

        for child in children:
            if child.name.startswith(".") or not child.is_dir():
                continue
            child_key = f"{rel_key}/{child.name}" if rel_key else child.name
            visit(child, child_key)

    visit(suite_path, None)
    return dict(sorted(categories.items(), key=lambda item: item[0].lower()))


def _merge_category_maps(
    into: dict[str, dict[str, dict[str, str]]],
    extra: dict[str, dict[str, dict[str, str]]],
) -> None:
    for cat, circuits in extra.items():
        into.setdefault(cat, {})
        for stem, ext_map in circuits.items():
            into[cat].setdefault(stem, {})
            into[cat][stem].update(ext_map)


def _filter_index_suites(
    suites: dict[str, dict[str, dict[str, dict[str, str]]]],
) -> dict[str, dict[str, dict[str, dict[str, str]]]]:
    filtered: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
    for name in INDEX_SUITE_NAMES:
        suite = suites.get(name)
        if not suite:
            continue
        allowed = INDEX_CATEGORY_BY_SUITE.get(name)
        if allowed is None:
            filtered[name] = suite
        else:
            filtered[name] = {cat: circ for cat, circ in suite.items() if cat in allowed}
    return filtered


def build_index() -> dict[str, Any]:
    root = _benchmark_root()
    gen = generated_benchmark_root()
    suites: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
    # Only scan suites exposed by the public index (skip epfl/classic full-tree walks).
    for name in INDEX_SUITE_NAMES:
        suites[name] = scan_suite(root / name)
        gen_suite = gen / name
        if gen_suite.is_dir():
            _merge_category_maps(suites[name], scan_suite(gen_suite))
    return {
        "suites": _filter_index_suites(suites),
        "root": str(root),
        "generated_root": str(gen),
    }
