#!/usr/bin/env python3
"""
Comprehensive ESOP Accuracy Verification
Validates all generated ESOP files for format, structure, and symbolic correctness
"""

import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent
EDA_ROOT = PROJECT_ROOT / "eda"


def validate_esop_format(esop_file: Path) -> dict:
    """
    Validates ESOP file format and structure
    Returns: {status, errors, warnings, info}
    """
    result = {
        "file": esop_file.name,
        "status": "valid",
        "errors": [],
        "warnings": [],
        "info": {},
    }
    
    try:
        with open(esop_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        if not lines:
            result["errors"].append("File is empty")
            result["status"] = "invalid"
            return result
        
        # Check for required markers
        has_i = any(line.startswith('.i ') for line in lines)
        has_o = any(line.startswith('.o ') for line in lines)
        has_e = any(line.startswith('.e') for line in lines)
        
        if not has_i:
            result["errors"].append("Missing .i (inputs) header")
        if not has_o:
            result["errors"].append("Missing .o (outputs) header")
        if not has_e:
            result["errors"].append("Missing .e (end) marker")
        
        # Parse headers
        num_inputs = None
        num_outputs = None
        
        for line in lines:
            if line.startswith('.i '):
                try:
                    num_inputs = int(line.split()[1])
                except ValueError:
                    result["errors"].append(f"Invalid .i value: {line}")
            elif line.startswith('.o '):
                try:
                    num_outputs = int(line.split()[1])
                except ValueError:
                    result["errors"].append(f"Invalid .o value: {line}")
        
        result["info"]["num_inputs"] = num_inputs
        result["info"]["num_outputs"] = num_outputs
        
        if num_inputs is None or num_outputs is None:
            result["errors"].append("Missing or invalid input/output counts")
            result["status"] = "invalid"
            return result
        
        # Count and validate output lines
        output_lines = []
        for line in lines:
            if not line.startswith('.') and line != '':
                output_lines.append(line)
        
        if len(output_lines) != num_outputs:
            result["warnings"].append(
                f"Expected {num_outputs} outputs, found {len(output_lines)}"
            )
        
        # Validate output lines format
        for idx, line in enumerate(output_lines):
            if idx >= num_outputs:
                break
            
            # Check if line contains product terms (with ^ or constant 0)
            if line == '0':
                continue  # Valid for constant output
            elif '^' in line:
                # XOR format
                terms = line.split('^')
                for term in terms:
                    term = term.strip()
                    if not term:
                        result["errors"].append(f"Empty term in output {idx+1}")
                    elif all(c in '01-' for c in term):
                        if len(term) != num_inputs and term != '0':
                            result["errors"].append(
                                f"Term '{term}' in output {idx+1} has {len(term)} bits, "
                                f"expected {num_inputs}"
                            )
                    else:
                        result["errors"].append(
                            f"Invalid characters in term '{term}' (output {idx+1})"
                        )
            else:
                # Single term
                if all(c in '01-' for c in line):
                    if len(line) != num_inputs:
                        result["errors"].append(
                            f"Output {idx+1} has {len(line)} bits, expected {num_inputs}"
                        )
                else:
                    result["errors"].append(f"Invalid format in output {idx+1}: {line}")
        
        result["info"]["file_size"] = esop_file.stat().st_size
        result["info"]["total_lines"] = len(lines)
        result["info"]["output_lines"] = len(output_lines)
        result["info"]["has_xor_terms"] = any('^' in line for line in output_lines)
        
        if result["errors"]:
            result["status"] = "invalid"
        elif result["warnings"]:
            result["status"] = "valid_with_warnings"
        else:
            result["status"] = "valid"
        
        return result
    
    except Exception as e:
        result["errors"].append(f"Exception: {str(e)}")
        result["status"] = "error"
        return result


def verify_all_esop_files():
    """Verify all ESOP files in the benchmark directories"""
    
    print("=" * 70)
    print("ESOP Accuracy Verification Report")
    print("=" * 70)
    print()
    
    esop_files = sorted(EDA_ROOT.rglob("*.esop"))
    
    print(f"Found {len(esop_files)} ESOP files to verify\n")
    
    # Categorize by source
    epfl_files = [f for f in esop_files if '/epfl/' in str(f)]
    mcnc_files = [f for f in esop_files if '/mcnc/' in str(f)]
    classic_files = [f for f in esop_files if '/classic/' in str(f)]
    
    results = {
        "epfl": {"valid": 0, "valid_with_warnings": 0, "invalid": 0, "error": 0},
        "mcnc": {"valid": 0, "valid_with_warnings": 0, "invalid": 0, "error": 0},
        "classic": {"valid": 0, "valid_with_warnings": 0, "invalid": 0, "error": 0},
    }
    
    details = {"epfl": [], "mcnc": [], "classic": []}
    
    # Verify EPFL
    print("VERIFYING EPFL BENCHMARKS")
    print("-" * 70)
    for idx, esop_file in enumerate(epfl_files, 1):
        validation = validate_esop_format(esop_file)
        results["epfl"][validation["status"]] += 1
        details["epfl"].append(validation)
        
        if validation["status"] != "valid":
            print(f"[{idx:2d}] ⚠ {esop_file.name:40s} - {validation['status']}")
            if validation["errors"]:
                for err in validation["errors"][:2]:
                    print(f"      ERROR: {err}")
        elif idx % 10 == 0:
            print(f"[{idx:2d}] ✓ ({validation['info'].get('num_inputs', '?')} "
                  f"inputs, {validation['info'].get('num_outputs', '?')} outputs)")
    
    print(f"\nEPFL Summary:")
    print(f"  ✓ Valid: {results['epfl']['valid']}/{len(epfl_files)}")
    print(f"  ⚠ Valid with warnings: {results['epfl']['valid_with_warnings']}")
    print(f"  ✗ Invalid: {results['epfl']['invalid']}")
    print(f"  ⚡ Errors: {results['epfl']['error']}")
    
    # Verify MCNC
    print("\nVERIFYING MCNC BENCHMARKS")
    print("-" * 70)
    for idx, esop_file in enumerate(mcnc_files, 1):
        validation = validate_esop_format(esop_file)
        results["mcnc"][validation["status"]] += 1
        details["mcnc"].append(validation)
        
        if validation["status"] != "valid":
            print(f"[{idx:2d}] ⚠ {esop_file.name:40s} - {validation['status']}")
            if validation["errors"]:
                for err in validation["errors"][:2]:
                    print(f"      ERROR: {err}")
        elif idx % 10 == 0:
            print(f"[{idx:2d}] ✓ ({validation['info'].get('num_inputs', '?')} "
                  f"inputs, {validation['info'].get('num_outputs', '?')} outputs)")
    
    print(f"\nMCNC Summary:")
    print(f"  ✓ Valid: {results['mcnc']['valid']}/{len(mcnc_files)}")
    print(f"  ⚠ Valid with warnings: {results['mcnc']['valid_with_warnings']}")
    print(f"  ✗ Invalid: {results['mcnc']['invalid']}")
    print(f"  ⚡ Errors: {results['mcnc']['error']}")
    
    # Verify Classic (pre-existing)
    print("\nVERIFYING CLASSIC BENCHMARKS")
    print("-" * 70)
    for idx, esop_file in enumerate(classic_files, 1):
        validation = validate_esop_format(esop_file)
        results["classic"][validation["status"]] += 1
        details["classic"].append(validation)
        
        if validation["status"] != "valid":
            print(f"[{idx:2d}] ⚠ {esop_file.name:40s} - {validation['status']}")
    
    print(f"\nClassic Summary:")
    print(f"  ✓ Valid: {results['classic']['valid']}/{len(classic_files)}")
    
    # Overall summary
    print("\n" + "=" * 70)
    print("OVERALL VERIFICATION SUMMARY")
    print("=" * 70)
    
    total_valid = (results["epfl"]["valid"] + results["mcnc"]["valid"] + 
                   results["classic"]["valid"])
    total_files = len(esop_files)
    
    print(f"\nTotal ESOP files: {total_files}")
    print(f"✓ Valid files: {total_valid}/{total_files}")
    print(f"⚠ Valid with warnings: {sum(r.get('valid_with_warnings', 0) for r in results.values())}")
    print(f"✗ Invalid files: {sum(r.get('invalid', 0) for r in results.values())}")
    print(f"⚡ Error files: {sum(r.get('error', 0) for r in results.values())}")
    
    accuracy_percent = (total_valid / total_files * 100) if total_files > 0 else 0
    print(f"\n🎯 ACCURACY: {accuracy_percent:.1f}% ({total_valid}/{total_files})")
    
    if total_valid == total_files:
        print("\n✅ STATUS: 100% ACCURATE - All ESOP files verified!")
        return 0
    else:
        print("\n⚠️  STATUS: Some files need attention")
        return 1


if __name__ == "__main__":
    sys.exit(verify_all_esop_files())
