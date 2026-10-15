#!/usr/bin/env python3
"""Compute Mitra2016 / Tara2016 / Optimized GA, GB, AI, QC on All_PLAs (+ classic)."""
from __future__ import annotations

import copy
import csv
import sys
import tempfile
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eda_hub.pages.benchmarks.mitra2016_calculation import Mitra2016Calculation
from eda_hub.pages.benchmarks.optimized_rpla_calculation import OptimizedRPLACalculation
from eda_hub.pages.benchmarks.tara2016_calculation import Tara2016Calculation
from eda_hub.shared.rpla import RPLA
ALL_PLAS = ROOT / "benchmarks/mcnc/Combinational/pla/All_PLAs"
CLASSIC = ROOT / "benchmarks/classic/classic"

SKIP_PREFIX = (
    "#",
    ".ilb",
    ".ob",
    ".type",
    ".model",
    ".inputs",
    ".outputs",
    ".mv",
    ".label",
)

EXISTING_TABLE = [
    "5xp1", "9sym", "alu3", "apex3", "b12", "bw", "cordic", "duke2", "e64",
    "inc5", "misex1", "misex2", "pdc", "rd53", "rd73", "rd84", "sao2", "t481",
    "table3", "table5", "vg2", "xor5", "z5xp1", "z9sym",
]

# Extra well-known MCNC names (PLA-only or extra ESOPs) to reach 60+.
EXTRA_MCNC = [
    "alu1", "alu2", "alu4", "al2", "alcom", "amd", "apla", "apex1", "apex2",
    "apex4", "apex5", "b10", "b11", "b2", "b3", "b9", "br1", "br2", "chkn",
    "clip", "clpl", "con1", "dc1", "dc2", "dekoder", "dist", "dk17", "dk27",
    "dk48", "ex5", "ex7", "exp", "f51m", "gary", "ibm", "in0", "in1", "in2",
    "in3", "in4", "in5", "in6", "in7", "inc", "luc", "m1", "m2", "m3", "mark1",
    "max46", "misex3c", "mlp4", "pope", "ryy6", "shift", "signet", "sqn",
    "sqr6", "sqrt8", "squar5", "tms", "ts10", "vtx1", "wim", "x1dn", "x9dn",
]


def find_source(name: str) -> Path | None:
    """Prefer classic .esop (Table 9 provenance), then All_PLAs .esop, then .pla."""
    lower = name.lower()
    for folder, ext in ((CLASSIC, ".esop"), (ALL_PLAS, ".esop"), (ALL_PLAS, ".pla")):
        if not folder.is_dir():
            continue
        exact = folder / f"{name}{ext}"
        if exact.exists():
            return exact
        for p in folder.glob(f"*{ext}"):
            if p.stem.lower() == lower:
                return p
    return None


def cleaned_text(path: Path) -> str:
    keep = []
    for raw in path.read_text(errors="replace").splitlines():
        s = raw.strip()
        if not s:
            continue
        low = s.lower()
        if any(low.startswith(pfx) for pfx in SKIP_PREFIX):
            continue
        keep.append(s)
    if keep and not any(line.lower().startswith(".e") and len(line.split()[0]) <= 2 for line in keep):
        keep.append(".e")
    return "\n".join(keep) + "\n"


def metrics_of(calc) -> tuple[int, int, int, int]:
    return (
        int(calc.gates),
        int(calc.garbages),
        int(calc.ancilla_input_count),
        int(calc.quantumCost),
    )


def evaluate(path: Path) -> dict:
    text = cleaned_text(path)
    with tempfile.NamedTemporaryFile("w", suffix=path.suffix, delete=False) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    try:
        r = RPLA()
        r.skip_pipeline_on_dot_e = True
        r.functions = []
        r.products = []
        r.patternsOfProduct = []
        r.totalLiterals = 0
        r.totalProducts = 0
        r.totalOutputs = 0
        r.readDataFromESOPFile(str(tmp_path))
        if not r.products or r.totalLiterals <= 0:
            raise RuntimeError(f"empty parse products={len(r.products)} i={r.totalLiterals}")

        snap_m = SimpleNamespace(functions=copy.deepcopy(r.functions), products=copy.deepcopy(r.products))
        snap_t = SimpleNamespace(functions=copy.deepcopy(r.functions), products=copy.deepcopy(r.products))
        snap_o = SimpleNamespace(functions=copy.deepcopy(r.functions), products=copy.deepcopy(r.products))

        m = Mitra2016Calculation(snap_m, r.totalLiterals, quiet=True)
        m.andPlane()
        m.xorPlane()
        t = Tara2016Calculation(snap_t, r.totalLiterals, quiet=True)
        t.andPlane()
        t.xorPlane()
        o = OptimizedRPLACalculation(snap_o, r.totalLiterals, quiet=True)
        o.andPlane()
        o.xorPlane()
        mga, mgb, mai, mqc = metrics_of(m)
        tga, tgb, tai, tqc = metrics_of(t)
        oga, ogb, oai, oqc = metrics_of(o)
        return {
            "ok": True,
            "i": r.totalLiterals,
            "o": r.totalOutputs,
            "p": len(r.products),
            "m_ga": mga, "m_gb": mgb, "m_ai": mai, "m_qc": mqc,
            "t_ga": tga, "t_gb": tgb, "t_ai": tai, "t_qc": tqc,
            "o_ga": oga, "o_gb": ogb, "o_ai": oai, "o_qc": oqc,
            "src": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        }
    finally:
        tmp_path.unlink(missing_ok=True)


def candidate_names() -> list[str]:
    names = []
    seen = set()
    for n in EXISTING_TABLE + EXTRA_MCNC:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            names.append(n)
    # Remaining All_PLAs .esop stems not already listed.
    if ALL_PLAS.is_dir():
        for p in sorted(ALL_PLAS.glob("*.esop")):
            key = p.stem.lower()
            if key not in seen:
                seen.add(key)
                names.append(p.stem)
    return names


def mean_red(rows: list[dict], ekey: str, okey: str) -> float | None:
    vals = []
    for r in rows:
        e, o = r[ekey], r[okey]
        if e > 0:
            vals.append((e - o) / e)
    if not vals:
        return None
    return 100.0 * sum(vals) / len(vals)


def main() -> int:
    out_csv = ROOT / "python" / "all_plas_table9_costs.csv"
    names = candidate_names()
    rows = []
    print(f"candidates={len(names)}", flush=True)
    for name in names:
        src = find_source(name)
        if src is None:
            print(f"SKIP {name}: not found", flush=True)
            continue
        t0 = time.time()
        try:
            rec = evaluate(src)  # sequential; large MCNC ESOPs can take ~1 min
            rec["name"] = name
            rec["sec"] = round(time.time() - t0, 3)
            rows.append(rec)
            print(
                f"OK {name:12s} p={rec['p']:4d}  "
                f"M {rec['m_ga']:6d}/{rec['m_gb']:5d}/{rec['m_ai']:5d}/{rec['m_qc']:6d}  "
                f"T {rec['t_ga']:6d}/{rec['t_gb']:5d}/{rec['t_ai']:5d}/{rec['t_qc']:6d}  "
                f"O {rec['o_ga']:6d}/{rec['o_gb']:5d}/{rec['o_ai']:5d}/{rec['o_qc']:6d}  "
                f"{rec['sec']:.2f}s",
                flush=True,
            )
        except Exception as exc:
            print(f"FAIL {name} ({src}): {exc}", flush=True)
            traceback.print_exc()

    if not rows:
        return 1

    fields = [
        "name", "i", "o", "p",
        "m_ga", "m_gb", "m_ai", "m_qc",
        "t_ga", "t_gb", "t_ai", "t_qc",
        "o_ga", "o_gb", "o_ai", "o_qc",
        "sec", "src",
    ]
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out_csv} n={len(rows)}", flush=True)
    for label, prefix in (("Mitra2016", "m"), ("Tara2016", "t")):
        for metric in ("ga", "gb", "ai", "qc"):
            red = mean_red(rows, f"{prefix}_{metric}", f"o_{metric}")
            print(f"  mean red {label} {metric}: {red}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
