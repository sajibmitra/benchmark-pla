#!/usr/bin/env python3
"""
Convert BLIF benchmark circuits to ESOP format using ABC toolchain.

Uses python/blif_parser.BLIFToESOP: ABC write_pla only (no non-ABC logic), then
writes classic PLA-style .esop (.i / .o / .p / cube rows / .e).

Usage:
    python convert_to_esop.py [--source epfl|mcnc|both] [--output-dir DIR]
"""

import os
import sys
from pathlib import Path
import argparse

ABC_BIN = "/tmp/abc-berkeley/abc"
PROJECT_ROOT = Path(__file__).parent
EDA_ROOT = PROJECT_ROOT / "benchmarks" / "eda"

sys.path.insert(0, str(PROJECT_ROOT / "python"))
from blif_parser import BLIFToESOP  # noqa: E402


def find_blif_files(source="both"):
    """Find all BLIF files in the benchmark directories."""
    sources = []
    if source in ("epfl", "both"):
        sources.append(EDA_ROOT / "epfl")
    if source in ("mcnc", "both"):
        sources.append(EDA_ROOT / "mcnc")

    blif_files = []
    for src_dir in sources:
        if src_dir.exists():
            blif_files.extend(src_dir.rglob("*.blif"))

    return sorted(blif_files)


def main():
    parser = argparse.ArgumentParser(description="Convert BLIF benchmarks to ESOP format")
    parser.add_argument("--source", choices=["epfl", "mcnc", "both"], default="both",
                        help="Which benchmark set to convert")
    parser.add_argument("--output-dir", default=None,
                        help="Override output directory (default: same as input)")
    parser.add_argument("--skip-pla", action="store_true",
                        help="Do not write intermediate .pla (same content as .esop when kept)")
    parser.add_argument(
        "--no-exorcism",
        action="store_true",
        help="Skip ABC &exorcism (EXORCISM-4); emit SOP PLA from write_pla only",
    )

    args = parser.parse_args()

    abc_bin = os.environ.get("ABC_BIN", ABC_BIN)
    if not os.path.isfile(abc_bin):
        print(f"✗ ABC binary not found at {abc_bin}")
        print("  Set ABC_BIN or build: https://github.com/berkeley-abc/abc")
        sys.exit(1)

    blif_files = find_blif_files(args.source)

    if not blif_files:
        print("✗ No BLIF files found")
        sys.exit(1)

    print(f"Found {len(blif_files)} BLIF files to convert")
    print(f"ABC binary: {abc_bin}\n")

    converted = 0
    failed = 0

    for blif_file in blif_files:
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            pla_file = output_dir / (blif_file.stem + ".pla")
            esop_file = output_dir / (blif_file.stem + ".esop")
        else:
            pla_file = blif_file.with_suffix(".pla")
            esop_file = blif_file.with_suffix(".esop")

        rel_path = blif_file.relative_to(PROJECT_ROOT)
        print(f"Converting {rel_path.name}...", end=" ", flush=True)

        converter = BLIFToESOP(
            str(blif_file),
            require_abc=True,
            use_exorcism=not args.no_exorcism,
        )
        if not converter.convert_to_esop() or not converter.write_esop_file(str(esop_file)):
            failed += 1
            print("✗ (ABC conversion or write failed)")
            continue

        if not args.skip_pla:
            if not converter.write_esop_file(str(pla_file)):
                failed += 1
                print("✗ (could not write .pla)")
                continue

        converted += 1
        esop_size = esop_file.stat().st_size if esop_file.exists() else 0
        print(f"✓ ({esop_size} bytes)")

    print(f"\n{'='*70}")
    print("Conversion complete:")
    print(f"  Converted: {converted}/{len(blif_files)}")
    print(f"  Failed:    {failed}/{len(blif_files)}")
    print(f"{'='*70}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
