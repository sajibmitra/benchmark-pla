"""Resolve EDA CLI tools only under EDA_ROOT (Data/eda). No /usr fallbacks."""
from __future__ import annotations

import os
from pathlib import Path

from .paths import eda_root

_ENV_YOSYS = ("EDA_YOSYS", "YOSYS_PATH", "YOSYS")
_ENV_ABC = ("EDA_ABC", "ABC_PATH", "ABC")
_ENV_OPENROAD = ("EDA_OPENROAD", "OPENROAD_PATH", "OPENROAD")
_ENV_NGSPICE = ("EDA_NGSPICE", "NGSPICE_PATH", "NGSPICE")
_ENV_STA = ("EDA_STA", "STA_PATH", "STA")
_ENV_XSCHEM = ("EDA_XSCHEM", "XSCHEM_PATH", "XSCHEM")


class ToolNotFoundError(FileNotFoundError):
    """Raised when a required EDA tool is missing under EDA_ROOT."""


def _under_eda(path: Path) -> bool:
    try:
        path.resolve().relative_to(eda_root())
        return True
    except ValueError:
        return False


def _from_env_under_eda(keys: tuple[str, ...]) -> str | None:
    for key in keys:
        raw = os.environ.get(key, "").strip()
        if not raw:
            continue
        p = Path(raw).expanduser()
        if not p.is_file() or not os.access(p, os.X_OK):
            # Allow env value that is just a tool name under EDA_ROOT/bin.
            cand = eda_root() / "bin" / raw
            if cand.is_file() and os.access(cand, os.X_OK) and _under_eda(cand):
                return str(cand.resolve())
            continue
        resolved = p.resolve()
        if _under_eda(resolved):
            return str(resolved)
    return None


def _first_executable(candidates: list[Path]) -> str | None:
    for cand in candidates:
        try:
            if cand.is_file() and os.access(cand, os.X_OK) and _under_eda(cand):
                return str(cand.resolve())
        except OSError:
            continue
    return None


def _bin_candidates(name: str, extra: list[Path] | None = None) -> list[Path]:
    root = eda_root()
    out = [root / "bin" / name]
    if extra:
        out.extend(extra)
    return out


def resolve_abc_executable() -> str:
    p = _from_env_under_eda(_ENV_ABC)
    if p:
        return p
    root = eda_root()
    found = _first_executable(
        _bin_candidates(
            "abc",
            [root / "abc" / "abc", root / "yosys" / "yosys-abc"],
        )
    )
    if found:
        return found
    raise ToolNotFoundError(f"abc not found under EDA_ROOT={eda_root()}")


def resolve_yosys_executable() -> str:
    p = _from_env_under_eda(_ENV_YOSYS)
    if p:
        return p
    root = eda_root()
    found = _first_executable(_bin_candidates("yosys", [root / "yosys" / "yosys"]))
    if found:
        return found
    raise ToolNotFoundError(f"yosys not found under EDA_ROOT={eda_root()}")


def resolve_openroad_executable() -> str:
    p = _from_env_under_eda(_ENV_OPENROAD)
    if p:
        return p
    root = eda_root()
    found = _first_executable(
        _bin_candidates(
            "openroad",
            [
                root / "OpenROAD" / "build" / "bin" / "openroad",
                root / "OpenROAD" / "install" / "bin" / "openroad",
            ],
        )
    )
    if found:
        return found
    raise ToolNotFoundError(f"openroad not found under EDA_ROOT={eda_root()}")


def resolve_ngspice_executable() -> str:
    p = _from_env_under_eda(_ENV_NGSPICE)
    if p:
        return p
    root = eda_root()
    found = _first_executable(
        _bin_candidates(
            "ngspice",
            [
                root / "ngspice" / "release" / "src" / "ngspice",
                root / "ngspice" / "bin" / "ngspice",
            ],
        )
    )
    if found:
        return found
    raise ToolNotFoundError(f"ngspice not found under EDA_ROOT={eda_root()}")


def resolve_sta_executable() -> str:
    p = _from_env_under_eda(_ENV_STA)
    if p:
        return p
    root = eda_root()
    found = _first_executable(
        _bin_candidates(
            "sta",
            [
                root / "OpenSTA" / "build" / "sta",
                root / "OpenSTA" / "app" / "sta",
            ],
        )
    )
    if found:
        return found
    raise ToolNotFoundError(f"sta not found under EDA_ROOT={eda_root()}")


def resolve_xschem_executable() -> str:
    p = _from_env_under_eda(_ENV_XSCHEM)
    if p:
        return p
    root = eda_root()
    found = _first_executable(
        _bin_candidates(
            "xschem",
            [root / "xschem" / "install" / "bin" / "xschem"],
        )
    )
    if found:
        return found
    raise ToolNotFoundError(f"xschem not found under EDA_ROOT={eda_root()}")


__all__ = [
    "ToolNotFoundError",
    "eda_root",
    "resolve_abc_executable",
    "resolve_ngspice_executable",
    "resolve_openroad_executable",
    "resolve_sta_executable",
    "resolve_xschem_executable",
    "resolve_yosys_executable",
]
