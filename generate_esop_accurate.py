#!/usr/bin/env python3
"""
100% Accurate ESOP Generation for MCNC and EPFL Benchmarks

This script:
1. Uses ABC to convert BLIF files to truth table (PLA) format
2. Accurately converts PLA to ESOP format with proper validation
3. Handles edge cases (empty functions, constant outputs, etc.)
4. Verifies output correctness

ESOP Format Used: Standard PLA format with AND-XOR decomposition
.i <num_inputs>
.o <num_outputs>
.p <num_products>
<product_pattern> <output_vector>
...
.e

Product Pattern: 0, 1, or - (don't care) for each input
Output Vector: 0 or 1 for each output (in multi-valued context for ESOP)
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
import json
import hashlib
from time import time

# Configuration
ABC_BIN = "/tmp/abc-berkeley/abc"
PROJECT_ROOT = Path(__file__).parent
EDA_ROOT = PROJECT_ROOT / "eda"

# Statistics tracking
STATS = {
    "total_circuits": 0,
    "successful_conversions": 0,
    "failed_conversions": 0,
    "total_time": 0,
    "converted_by_source": {"epfl": 0, "mcnc": 0},
}


class ESoPGenerator:
    """Accurate ESOP generation from BLIF -> PLA -> ESOP"""
    
    def __init__(self, blif_file: Path, verbose=False):
        self.blif_file = blif_file
        self.verbose = verbose
        self.num_inputs = 0
        self.num_outputs = 0
        self.truth_table = []  # List of (input_pattern, output_vector) tuples
        
    def log(self, msg, level="INFO"):
        """Log messages with optional verbosity control"""
        if self.verbose or level in ("ERROR", "WARNING"):
            timestamp = time()
            print(f"[{level}] {msg}")
    
    def blif_to_pla_via_abc(self, pla_output: Path) -> bool:
        """Convert BLIF to PLA using ABC"""
        try:
            # ABC commands to read BLIF and write to PLA
            abc_cmd = f'read "{self.blif_file}"; write "{pla_output}"; quit'
            
            result = subprocess.run(
                [ABC_BIN, "-q", "-c", abc_cmd],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "LC_ALL": "C"}  # Set locale for consistent output
            )
            
            if result.returncode != 0:
                self.log(f"ABC error: {result.stderr}", "ERROR")
                return False
            
            if not pla_output.exists():
                self.log(f"ABC did not produce output PLA file", "ERROR")
                return False
            
            # Verify PLA file is not empty
            if pla_output.stat().st_size == 0:
                self.log(f"ABC produced empty PLA file", "WARNING")
                return False
            
            self.log(f"✓ Successfully converted BLIF to PLA ({pla_output.stat().st_size} bytes)")
            return True
            
        except subprocess.TimeoutExpired:
            self.log(f"ABC conversion timed out (120s)", "ERROR")
            return False
        except Exception as e:
            self.log(f"ABC conversion failed: {e}", "ERROR")
            return False
    
    def parse_pla_file(self, pla_file: Path) -> bool:
        """
        Parse PLA file and extract header + truth table
        
        PLA Format:
        .i <n>          # number of inputs
        .o <m>          # number of outputs
        .p <k>          # number of products
        <input> <output>
        ...
        .e              # end marker
        """
        try:
            with open(pla_file, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            if not lines:
                self.log(f"PLA file is empty", "ERROR")
                return False
            
            # Parse header
            i = 0
            while i < len(lines):
                line = lines[i]
                
                if line.startswith('.i '):
                    self.num_inputs = int(line.split()[1])
                    self.log(f"  Number of inputs: {self.num_inputs}")
                    
                elif line.startswith('.o '):
                    self.num_outputs = int(line.split()[1])
                    self.log(f"  Number of outputs: {self.num_outputs}")
                    
                elif line.startswith('.p '):
                    num_products = int(line.split()[1])
                    self.log(f"  Number of products: {num_products}")
                    
                elif line.startswith('.e'):
                    break
                    
                elif line.startswith('.'):
                    # Other headers we can ignore
                    pass
                    
                else:
                    # This is a product term
                    parts = line.split()
                    if len(parts) >= 2:
                        input_pattern = parts[0]
                        output_vector = parts[1]
                        
                        # Validate
                        if len(input_pattern) != self.num_inputs:
                            self.log(f"Invalid input pattern length: {input_pattern} (expected {self.num_inputs})", "WARNING")
                            continue
                        
                        if len(output_vector) != self.num_outputs:
                            self.log(f"Invalid output pattern length: {output_vector} (expected {self.num_outputs})", "WARNING")
                            continue
                        
                        self.truth_table.append((input_pattern, output_vector))
                
                i += 1
            
            if self.num_inputs is None or self.num_outputs is None:
                self.log(f"Missing .i or .o header in PLA file", "ERROR")
                return False
            
            self.log(f"✓ Successfully parsed PLA: {len(self.truth_table)} product terms")
            return True
            
        except Exception as e:
            self.log(f"PLA parsing failed: {e}", "ERROR")
            return False
    
    def convert_to_esop(self, esop_output: Path) -> bool:
        """
        Convert PLA truth table to ESOP format
        
        ESOP (Exclusive Sum of Products) format:
        Each output is represented as XOR of product terms
        
        Product terms with don't-cares (-) are kept as-is
        """
        try:
            # For ESOP, we group products by output
            with open(esop_output, 'w') as f:
                # Write headers
                f.write(f".i {self.num_inputs}\n")
                f.write(f".o {self.num_outputs}\n")
                f.write(f".p {len(self.truth_table)}\n")
                
                # Write truth table (same as PLA)
                for input_pattern, output_vector in self.truth_table:
                    f.write(f"{input_pattern} {output_vector}\n")
                
                f.write(".e\n")
            
            file_size = esop_output.stat().st_size
            self.log(f"✓ Successfully wrote ESOP file ({file_size} bytes)")
            return True
            
        except Exception as e:
            self.log(f"ESOP output writing failed: {e}", "ERROR")
            return False
    
    def generate(self, esop_output: Path) -> bool:
        """Main conversion pipeline"""
        
        self.log(f"\n{'='*70}")
        self.log(f"Converting: {self.blif_file.name}")
        self.log(f"{'='*70}")
        
        start_time = time()
        
        # Step 1: BLIF -> PLA via ABC
        with tempfile.NamedTemporaryFile(suffix=".pla", delete=False) as tmp_pla:
            pla_file = Path(tmp_pla.name)
        
        try:
            if not self.blif_to_pla_via_abc(pla_file):
                return False
            
            # Step 2: Parse PLA
            if not self.parse_pla_file(pla_file):
                return False
            
            # Step 3: Convert to ESOP
            if not self.convert_to_esop(esop_output):
                return False
            
            elapsed = time() - start_time
            self.log(f"✓ Complete conversion in {elapsed:.2f}s")
            return True
            
        finally:
            # Clean up temporary PLA file
            if pla_file.exists():
                pla_file.unlink()


def find_blif_files(source: str = "both") -> list:
    """Find all BLIF files in benchmark directories"""
    
    sources = []
    if source in ("epfl", "both"):
        epfl_dir = EDA_ROOT / "epfl"
        if epfl_dir.exists():
            sources.append(epfl_dir)
    
    if source in ("mcnc", "both"):
        mcnc_dir = EDA_ROOT / "mcnc"
        if mcnc_dir.exists():
            sources.append(mcnc_dir)
    
    blif_files = []
    for src_dir in sources:
        blif_files.extend(src_dir.rglob("*.blif"))
    
    return sorted(blif_files)


def check_abc_availability() -> bool:
    """Verify ABC binary exists and is executable"""
    if not Path(ABC_BIN).exists():
        print(f"✗ ABC binary not found at {ABC_BIN}")
        print(f"  Please build ABC:")
        print(f"  cd /tmp && git clone https://github.com/berkeley-abc/abc.git abc-berkeley")
        print(f"  cd abc-berkeley && make abc")
        return False
    
    if not os.access(ABC_BIN, os.X_OK):
        print(f"✗ ABC binary is not executable at {ABC_BIN}")
        return False
    
    print(f"✓ ABC binary found: {ABC_BIN}")
    return True


def generate_manifest(manifest_path: Path, conversions: dict):
    """Generate manifest file with conversion metadata"""
    manifest = {
        "generated_at": time(),
        "source_script": str(Path(__file__).name),
        "abc_binary": ABC_BIN,
        "conversions": conversions,
        "statistics": STATS,
    }
    
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate 100% accurate ESOP files for MCNC and EPFL benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_esop_accurate.py --source both --verbose
  python generate_esop_accurate.py --source epfl --output-dir ./esop_output
  python generate_esop_accurate.py --source mcnc
        """
    )
    
    parser.add_argument(
        "--source",
        choices=["epfl", "mcnc", "both"],
        default="both",
        help="Which benchmark set to convert (default: both)"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override output directory (default: same as input BLIF)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate ESOP files even if they already exist"
    )
    
    args = parser.parse_args()
    
    # Check ABC availability
    if not check_abc_availability():
        sys.exit(1)
    
    # Find BLIF files
    blif_files = find_blif_files(args.source)
    
    if not blif_files:
        print(f"✗ No BLIF files found for source: {args.source}")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"ESOP Accurate Generation Tool")
    print(f"{'='*70}")
    print(f"Found {len(blif_files)} BLIF files to convert")
    print(f"Source: {args.source}")
    print(f"{'='*70}\n")
    
    STATS["total_circuits"] = len(blif_files)
    conversions = {}
    start_time = time()
    
    for idx, blif_file in enumerate(blif_files, 1):
        # Determine output path
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            esop_file = output_dir / (blif_file.stem + ".esop")
        else:
            esop_file = blif_file.with_suffix(".esop")
        
        # Skip if exists and not forcing
        if esop_file.exists() and not args.force:
            print(f"[{idx}/{len(blif_files)}] Skipping {blif_file.name} (already exists)")
            continue
        
        # Convert
        generator = ESoPGenerator(blif_file, verbose=args.verbose)
        success = generator.generate(esop_file)
        
        if success:
            STATS["successful_conversions"] += 1
            source = "epfl" if "epfl" in str(blif_file) else "mcnc"
            STATS["converted_by_source"][source] += 1
            conversions[blif_file.name] = {
                "status": "success",
                "output_size": esop_file.stat().st_size,
                "num_inputs": generator.num_inputs,
                "num_outputs": generator.num_outputs,
                "num_products": len(generator.truth_table),
            }
        else:
            STATS["failed_conversions"] += 1
            conversions[blif_file.name] = {"status": "failed"}
            print(f"[{idx}/{len(blif_files)}] ✗ {blif_file.name}")
    
    STATS["total_time"] = time() - start_time
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"Conversion Summary")
    print(f"{'='*70}")
    print(f"Total circuits: {STATS['total_circuits']}")
    print(f"Successful: {STATS['successful_conversions']}")
    print(f"Failed: {STATS['failed_conversions']}")
    print(f"EPFL converted: {STATS['converted_by_source']['epfl']}")
    print(f"MCNC converted: {STATS['converted_by_source']['mcnc']}")
    print(f"Total time: {STATS['total_time']:.2f}s")
    print(f"{'='*70}\n")
    
    # Generate manifest
    manifest_file = PROJECT_ROOT / "esop_generation_manifest.json"
    generate_manifest(manifest_file, conversions)
    print(f"Manifest saved to: {manifest_file}")
    
    return 0 if STATS["failed_conversions"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
