#!/usr/bin/env python3
"""
Smart Batch ESOP Converter for EPFL Arithmetic Benchmarks
Uses ABC GIA + EXORCISM-4 directly (no SOP intermediate)
Skips known complex circuits, handles timeouts gracefully
"""
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Add python dir to path
sys.path.insert(0, str(Path(__file__).parent / "python"))

from blif_parser import BLIFToESOP
from benchmark_paths import epfl_arithmetic_dir

# Configuration
SOURCE_DIR = epfl_arithmetic_dir()
TIMEOUT_PER_CIRCUIT = 600  # 10 minutes per circuit (reduced for testing)
SKIP_COMPLEX = ["adder", "div", "hyp"]  # Known to be too complex

def convert_single_blif(blif_file: Path) -> bool:
    """Convert single BLIF to ESOP with timeout handling."""
    esop_file = blif_file.with_suffix('.esop')

    # Skip if already exists
    if esop_file.exists():
        size_mb = esop_file.stat().st_size / (1024 * 1024)
        print(f"✓ (already exists, {size_mb:.1f} MB)")
        return True

    print(f"Converting...", end=" ", flush=True)

    # Set environment for longer EXORCISM-4 runs
    os.environ['ABC_GIA_EXORCISM_TIMEOUT'] = str(TIMEOUT_PER_CIRCUIT)

    try:
        converter = BLIFToESOP(str(blif_file), require_abc=True, use_exorcism=True)

        start_time = time.time()
        success = converter.convert_to_esop()
        elapsed = time.time() - start_time

        if success and converter.write_esop_file(str(esop_file)):
            size_mb = esop_file.stat().st_size / (1024 * 1024)
            print(f"✓ ({elapsed:.1f}s, {size_mb:.1f} MB)")
            return True
        else:
            print(f"✗ (failed in {elapsed:.1f}s)")
            return False

    except Exception as e:
        print(f"✗ (error: {e})")
        return False

def main():
    print("=" * 70)
    print("Smart Batch ESOP Conversion: EPFL Arithmetic")
    print("=" * 70)
    print(f"Source: {SOURCE_DIR}")
    print("Pipeline: ABC GIA + EXORCISM-4 (direct, no SOP)")
    print(f"Per-circuit timeout: {TIMEOUT_PER_CIRCUIT}s")
    print()

    if not SOURCE_DIR.exists():
        print(f"❌ Source directory not found: {SOURCE_DIR}")
        return 1

    # Get all BLIF files
    blif_files = sorted(SOURCE_DIR.glob("*.blif"))
    if not blif_files:
        print("❌ No BLIF files found")
        return 1

    print(f"Found {len(blif_files)} BLIF files")
    print()

    converted = 0
    failed = 0
    skipped = 0
    successful_files = []

    for i, blif_file in enumerate(blif_files, 1):
        name = blif_file.stem
        print("2d", end=" ", flush=True)

        if name in SKIP_COMPLEX:
            print("⊘ (skipped - too complex)")
            skipped += 1
            continue

        if convert_single_blif(blif_file):
            converted += 1
            successful_files.append(name)
        else:
            failed += 1

    print()
    print("=" * 70)
    print("Conversion Summary:")
    print(f"  Total BLIF files:    {len(blif_files)}")
    print(f"  ✓ Converted:         {converted}")
    print(f"  ✗ Failed:            {failed}")
    print(f"  ⊘ Skipped:           {skipped}")
    print(f"  Success rate:        {(converted / len(blif_files) * 100):.1f}%")
    print("=" * 70)

    if successful_files:
        print()
        print("✓ Successfully converted:")
        for name in successful_files:
            esop_file = SOURCE_DIR / f"{name}.esop"
            if esop_file.exists():
                size_mb = esop_file.stat().st_size / (1024 * 1024)
                print(f"   {name:<25} {size_mb:>6.1f} MB")

    if failed > 0:
        print()
        print("✗ Failed:")
        for blif_file in blif_files:
            name = blif_file.stem
            if name not in SKIP_COMPLEX:
                esop_file = SOURCE_DIR / f"{name}.esop"
                if not esop_file.exists():
                    print(f"   {name}")

    if skipped > 0:
        print()
        print("⊘ Skipped - too complex for current setup:")
        for name in SKIP_COMPLEX:
            print(f"   {name}")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())