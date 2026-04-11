#!/usr/bin/env python3
"""
Convert BLIF benchmark circuits to ESOP format using ABC toolchain.

This script:
1. Reads BLIF files from eda/epfl and eda/mcnc directories
2. Uses ABC to synthesize into SOP/ESOP representation
3. Exports to .esop format (AND-EXOR decomposition)

Usage:
    python convert_to_esop.py [--source epfl|mcnc|both] [--output-dir DIR]
"""

import os
import subprocess
import sys
from pathlib import Path
import argparse

ABC_BIN = "/tmp/abc-berkeley/abc"
PROJECT_ROOT = Path(__file__).parent
EDA_ROOT = PROJECT_ROOT / "eda"


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


def convert_blif_to_pla(blif_file, output_pla):
    """Convert BLIF to PLA using ABC."""
    # Use the generic read command instead of read_blif
    abc_cmd = f'read "{blif_file}"; write "{output_pla}"; quit'
    
    try:
        result = subprocess.run(
            [ABC_BIN, "-q", "-c", abc_cmd],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check if output file was actually created
        if not Path(output_pla).exists():
            return False
        
        return True
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        return False


def pla_to_esop(pla_file, esop_file):
    """
    Convert PLA to ESOP by reading PLA and rewriting as ESOP.
    
    PLA format:
        .i <num_inputs>
        .o <num_outputs>
        .p <num_products>
        <input_pattern> <output>
        ...
        .e
    
    ESOP format (AND-XOR decomposition):
        .i <num_inputs>
        .o <num_outputs>
        <product1> ^ <product2> ^ ... (for each output)
        .e
    """
    try:
        with open(pla_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        if not lines:
            return False
        
        # Parse PLA header
        num_inputs = None
        num_outputs = None
        num_products = None
        products = []
        output_patterns = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if line.startswith('.i '):
                num_inputs = int(line.split()[1])
            elif line.startswith('.o '):
                num_outputs = int(line.split()[1])
            elif line.startswith('.p '):
                num_products = int(line.split()[1])
            elif line.startswith('.e'):
                break
            elif line.startswith('.'):
                pass  # Skip other headers
            else:
                # This is a product term: input_pattern output_vector
                parts = line.split()
                if len(parts) == 2:
                    input_pattern = parts[0]
                    output_pattern = parts[1]
                    products.append(input_pattern)
                    output_patterns.append(output_pattern)
            
            i += 1
        
        if num_inputs is None or num_outputs is None:
            print(f"  Error: Invalid PLA format (missing .i or .o)")
            return False
        
        # Write ESOP file
        with open(esop_file, 'w') as f:
            f.write(f".i {num_inputs}\n")
            f.write(f".o {num_outputs}\n")
            
            # Group products by output and convert to XOR form
            for out_idx in range(num_outputs):
                output_products = []
                for prod_idx, out_vec in enumerate(output_patterns):
                    if out_idx < len(out_vec) and out_vec[out_idx] == '1':
                        output_products.append(products[prod_idx])
                
                if output_products:
                    # XOR form: product1 ^ product2 ^ ...
                    xor_expr = " ^ ".join(output_products)
                    f.write(f"{xor_expr}\n")
                else:
                    # No products for this output (constant 0)
                    f.write("0\n")
            
            f.write(".e\n")
        
        return True
    
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Convert BLIF benchmarks to ESOP format")
    parser.add_argument("--source", choices=["epfl", "mcnc", "both"], default="both",
                        help="Which benchmark set to convert")
    parser.add_argument("--output-dir", default=None,
                        help="Override output directory (default: same as input)")
    parser.add_argument("--skip-pla", action="store_true",
                        help="Skip PLA intermediate files")
    
    args = parser.parse_args()
    
    # Verify ABC exists
    if not os.path.exists(ABC_BIN):
        print(f"✗ ABC binary not found at {ABC_BIN}")
        print(f"  Please build ABC first: cd /tmp/abc-berkeley && make abc")
        sys.exit(1)
    
    # Find BLIF files
    blif_files = find_blif_files(args.source)
    
    if not blif_files:
        print(f"✗ No BLIF files found")
        sys.exit(1)
    
    print(f"Found {len(blif_files)} BLIF files to convert")
    print(f"ABC binary: {ABC_BIN}\n")
    
    # Track statistics
    converted = 0
    failed = 0
    
    for blif_file in blif_files:
        # Generate output filenames
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            pla_file = output_dir / (blif_file.stem + ".pla")
            esop_file = output_dir / (blif_file.stem + ".esop")
        else:
            # Same directory as input BLIF
            pla_file = blif_file.with_suffix(".pla")
            esop_file = blif_file.with_suffix(".esop")
        
        rel_path = blif_file.relative_to(PROJECT_ROOT)
        print(f"Converting {rel_path.name}...", end=" ", flush=True)
        
        # Step 1: Convert BLIF to PLA
        if not convert_blif_to_pla(blif_file, str(pla_file)):
            failed += 1
            print("✗ (ABC conversion failed)")
            continue
        
        # Step 2: Convert PLA to ESOP
        if not pla_to_esop(pla_file, esop_file):
            failed += 1
            print("✗ (PLA→ESOP conversion failed)")
            continue
        
        # Cleanup intermediate PLA if requested
        if args.skip_pla and pla_file.exists():
            pla_file.unlink()
        
        converted += 1
        esop_size = esop_file.stat().st_size if esop_file.exists() else 0
        print(f"✓ ({esop_size} bytes)")
    
    print(f"\n{'='*70}")
    print(f"Conversion complete:")
    print(f"  Converted: {converted}/{len(blif_files)}")
    print(f"  Failed:    {failed}/{len(blif_files)}")
    print(f"{'='*70}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
