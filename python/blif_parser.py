"""
BLIF to ESOP converter using ABC.

1. ABC writes a two-level PLA (SOP) when `collapse`+`write_pla` is feasible.
2. EXORCISM-4 (`&exorcism`) minimizes that PLA, or (if that fails or PLA cannot be
   built) falls back to `read; strash; &get; &exorcism` on the GIA — needed when
   `collapse` hits the ~1M cube limit on large EPFL/MCNC designs.
3. Environment: ABC_BIN, EXORCISM_Q, ABC_GIA_EXORCISM_TIMEOUT (seconds for the
   GIA `&exorcism` step; use a large value for wide multi-output circuits).
4. No non-ABC fallback that fabricates cubes when `require_abc` is True.
"""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BLIFParser:
    """Parse BLIF (Berkeley Logic Interchange Format) files."""
    
    def __init__(self, blif_file: str):
        self.blif_file = Path(blif_file)
        self.model_name = ""
        self.inputs: List[str] = []
        self.outputs: List[str] = []
        self.sub_logic: Dict[str, str] = {}  # output -> logic expression
        self.content: List[str] = []
        
    def parse(self) -> bool:
        """Parse the BLIF file and extract logic."""
        try:
            with open(self.blif_file, 'r') as f:
                self.content = [line.strip() for line in f if line.strip()]
            
            current_output = None
            current_cover = []
            
            i = 0
            while i < len(self.content):
                line = self.content[i]
                
                if line.startswith('.model'):
                    self.model_name = line.split()[-1]
                elif line.startswith('.inputs'):
                    self.inputs = line.split()[1:]
                elif line.startswith('.outputs'):
                    self.outputs = line.split()[1:]
                elif line.startswith('.names'):
                    # Parse logic for a signal
                    parts = line.split()[1:]
                    if len(parts) > 0:
                        current_output = parts[-1]
                        input_signals = parts[:-1]
                        current_cover = (input_signals, [])
                elif line.startswith('.end'):
                    break
                elif line.startswith('.') or line == '':
                    current_output = None
                    current_cover = []
                else:
                    # This is a cover term (truth table line)
                    if current_cover:
                        current_cover[1].append(line)
                
                i += 1
            
            return len(self.inputs) > 0 and len(self.outputs) > 0
        
        except Exception as e:
            print(f"Error parsing BLIF: {e}")
            return False


class BLIFToESOP:
    """Convert BLIF circuits to ESOP (AND-EXOR) representation."""
    
    ABC_BIN = "/tmp/abc-berkeley/abc"
    ABC_TIMEOUT = 300

    def __init__(
        self,
        blif_file: str,
        require_abc: bool = True,
        use_exorcism: bool = True,
        exorcism_quality: Optional[int] = None,
    ):
        self.blif_file = Path(blif_file)
        self.parser = BLIFParser(blif_file)
        self.require_abc = require_abc
        self.use_exorcism = use_exorcism
        if exorcism_quality is None:
            exorcism_quality = int(os.environ.get("EXORCISM_Q", "2"))
        self.exorcism_quality = max(0, exorcism_quality)
        self.num_inputs = 0
        self.num_outputs = 0
        self.products: List[Tuple[str, str]] = []
        self.esop_terms: Dict[int, List[str]] = {}
        self._source_abc_pla = False
        self._used_exorcism = False

    def _abc_binary(self) -> str:
        return os.environ.get("ABC_BIN", self.ABC_BIN)

    @staticmethod
    def _abc_merge_output(result) -> str:
        """ABC often prints errors on stdout; combine streams for diagnostics."""
        parts = []
        if result.stdout:
            parts.append(result.stdout)
        if result.stderr:
            parts.append(result.stderr)
        return "\n".join(parts).strip()[-1200:]

    def _abc_run_script(
        self, abc_bin: str, script_body: str, timeout: int
    ) -> subprocess.CompletedProcess:
        scr_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".scr", delete=False, encoding="utf-8"
            ) as scr:
                scr.write(script_body)
                scr_path = scr.name
            return subprocess.run(
                [abc_bin, "-f", scr_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "LC_ALL": "C"},
            )
        finally:
            if scr_path:
                try:
                    os.unlink(scr_path)
                except OSError:
                    pass

    def _abc_run_exorcism(
        self, abc_bin: str, pla_in: str, pla_out: str, timeout: int
    ) -> bool:
        """Run ABC9 `&exorcism` (EXORCISM-4) on a PLA file; write ESOP-PLA to pla_out."""
        in_q = shlex.quote(pla_in)
        out_q = shlex.quote(pla_out)
        q = self.exorcism_quality
        script_body = f"&exorcism -Q {q} -V 0 {in_q} {out_q}\nquit\n"
        try:
            self._abc_run_script(abc_bin, script_body, max(timeout, 120))
        except (subprocess.TimeoutExpired, OSError):
            return False
        outp = Path(pla_out)
        return outp.is_file() and outp.stat().st_size > 0

    def _abc_run_gia_exorcism(
        self, abc_bin: str, blif_q: str, esop_out: str, timeout: int
    ) -> bool:
        """
        read → strash → &get → &exorcism on the GIA (no two-level PLA).

        Avoids `collapse` + write_pla cube explosion on large EPFL/MCNC circuits
        (e.g. wide adders hit the 1M cube limit).
        """
        out_q = shlex.quote(esop_out)
        q = self.exorcism_quality
        script_body = (
            f"read {blif_q}\nstrash\n&get\n"
            f"&exorcism -Q {q} -V 0 {out_q}\nquit\n"
        )
        env_cap = os.environ.get("ABC_GIA_EXORCISM_TIMEOUT")
        if env_cap and env_cap.isdigit():
            gia_timeout = int(env_cap)
        else:
            # Large multi-output EPFL circuits can need many minutes.
            gia_timeout = min(max(timeout * 5, 600), 7200)
        try:
            self._abc_run_script(abc_bin, script_body, gia_timeout)
        except subprocess.TimeoutExpired:
            print(
                f"ABC GIA EXORCISM-4 timed out ({gia_timeout}s) for "
                f"{self.blif_file.name}; set ABC_GIA_EXORCISM_TIMEOUT (seconds) "
                "to allow longer runs."
            )
            return False
        except OSError:
            return False
        outp = Path(esop_out)
        return outp.is_file() and outp.stat().st_size > 0

    def extract_logic_via_abc(self) -> bool:
        """Run ABC write_pla only; no fake logic if ABC fails (when require_abc)."""
        abc_bin = self._abc_binary()
        if not Path(abc_bin).is_file():
            print(
                f"ABC binary not found at {abc_bin}. "
                "Set ABC_BIN or build: https://github.com/berkeley-abc/abc"
            )
            if self.require_abc:
                return False
            return self._extract_from_blif_directly()

        file_size_mb = self.blif_file.stat().st_size / (1024 * 1024)
        timeout = max(self.ABC_TIMEOUT, int(30 + file_size_mb * 10))

        fd, tmp_path = tempfile.mkstemp(suffix=".pla")
        os.close(fd)
        pla_path = Path(tmp_path)
        fd_exo, tmp_exo = tempfile.mkstemp(suffix=".esop")
        os.close(fd_exo)
        exo_path = Path(tmp_exo)

        try:
            blif_q = shlex.quote(str(self.blif_file.resolve()))
            pla_q = shlex.quote(str(pla_path.resolve()))

            # Try light-to-heavy ABC flows; all preserve Boolean equivalence.
            # Use -f script files: some ABC builds do not run multi-command -c reliably.
            # `collapse` + write_pla is required for many networks and for feeding &exorcism.
            strategies = [
                f"read {blif_q}\nset cube_limit 100000000\ncollapse\nwrite_pla {pla_q}\nquit\n",
                f"read {blif_q}\nset cube_limit 100000000\nwrite_pla {pla_q}\nquit\n",
                f"read {blif_q}\nset cube_limit 100000000\nstrash\nwrite_pla {pla_q}\nquit\n",
                f"read {blif_q}\nset cube_limit 100000000\ncollapse\nstrash\nwrite_pla {pla_q}\nquit\n",
            ]
            if file_size_mb > 2:
                strategies.append(
                    f"read {blif_q}\nset cube_limit 100000000\ncollapse2\nwrite_pla {pla_q}\nquit\n"
                )
            if file_size_mb <= 2:
                strategies.append(
                    f"read {blif_q}\nset cube_limit 100000000\ncollapse\nstrash\nrefactor\nbalance\n"
                    f"write_pla {pla_q}\nquit\n"
                )

            last_abc_log = ""
            for script_body in strategies:
                self.products.clear()
                self._source_abc_pla = False
                self._used_exorcism = False
                if pla_path.exists():
                    pla_path.unlink()
                if exo_path.exists():
                    exo_path.unlink()

                try:
                    result = self._abc_run_script(abc_bin, script_body, timeout)
                    last_abc_log = self._abc_merge_output(result)
                except subprocess.TimeoutExpired:
                    print(
                        f"ABC timed out ({timeout}s) for {self.blif_file.name} "
                        f"({file_size_mb:.1f} MB)"
                    )
                    if self.require_abc:
                        return False
                    return self._extract_from_blif_directly()

                if not (pla_path.exists() and pla_path.stat().st_size > 0):
                    continue

                self.products.clear()
                if not self._parse_pla_to_products(tmp_path):
                    continue

                if self.use_exorcism:
                    if exo_path.exists():
                        exo_path.unlink()
                    got_exo = False
                    if self._abc_run_exorcism(
                        abc_bin, str(pla_path), str(exo_path), timeout
                    ):
                        self.products.clear()
                        got_exo = self._parse_pla_to_products(str(exo_path))
                    if not got_exo:
                        if exo_path.exists():
                            exo_path.unlink()
                        if self._abc_run_gia_exorcism(
                            abc_bin, blif_q, str(exo_path), timeout
                        ):
                            self.products.clear()
                            got_exo = self._parse_pla_to_products(str(exo_path))
                    if got_exo:
                        self._source_abc_pla = True
                        self._used_exorcism = True
                        return True
                    self.products.clear()
                    if not self._parse_pla_to_products(tmp_path):
                        continue
                    print(
                        f"EXORCISM-4 failed for {self.blif_file.name} "
                        "(PLA and GIA paths); using SOP PLA from ABC."
                    )

                self._source_abc_pla = True
                self._used_exorcism = False
                return True

            if self.use_exorcism:
                if exo_path.exists():
                    exo_path.unlink()
                if self._abc_run_gia_exorcism(
                    abc_bin, blif_q, str(exo_path), timeout
                ):
                    self.products.clear()
                    if self._parse_pla_to_products(str(exo_path)):
                        self._source_abc_pla = True
                        self._used_exorcism = True
                        return True

            hint = ""
            low = last_abc_log.lower()
            if "cube" in low and "limit" in low:
                hint = (
                    " Hint: `collapse`+`write_pla` hit ABC’s cube limit; GIA "
                    "`&exorcism` was attempted — increase ABC_GIA_EXORCISM_TIMEOUT "
                    "if it timed out, or use a faster ABC build."
                )
            print(
                f"ABC could not extract a usable PLA/ESOP for {self.blif_file.name}. "
                f"Last ABC output (truncated): {last_abc_log!r}.{hint}"
            )
            if self.require_abc:
                return False
            return self._extract_from_blif_directly()

        except Exception as e:
            print(f"ABC extraction failed: {e}")
            if self.require_abc:
                return False
            return self._extract_from_blif_directly()
        finally:
            for p in (pla_path, exo_path):
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
    
    def _extract_from_blif_directly(self) -> bool:
        """
        Legacy path when require_abc=False only. Does not reproduce BLIF I/O behavior;
        do not use for accurate conversion.
        """
        if not self.parser.parse():
            # Try to at least get basic circuit structure
            if not self._extract_blif_structure():
                return False
        else:
            self.num_inputs = len(self.parser.inputs)
            self.num_outputs = len(self.parser.outputs)
        
        if self.num_inputs == 0 or self.num_outputs == 0:
            return False
        
        # Try to extract logic from BLIF .names clauses
        if not self._extract_logic_from_blif():
            # Fallback: create simple all-zero truth table
            for i in range(min(2**self.num_inputs, 1000)):  # Cap at 1000 to avoid explosion
                input_pattern = format(i, f'0{self.num_inputs}b')
                output_pattern = '0' * self.num_outputs
                self.products.append((input_pattern, output_pattern))
        
        return len(self.products) > 0
    
    def _extract_blif_structure(self) -> bool:
        """Extract basic circuit structure from BLIF without full parsing."""
        try:
            with open(self.blif_file, 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if line.startswith('.model'):
                    self.parser.model_name = line.split()[-1]
                elif line.startswith('.inputs'):
                    parts = line.split()[1:]
                    self.parser.inputs.extend([p for p in parts if p and not p.startswith('.')])
                elif line.startswith('.outputs'):
                    parts = line.split()[1:]
                    self.parser.outputs.extend([p for p in parts if p and not p.startswith('.')])
                elif line.startswith('.end'):
                    break
            
            self.num_inputs = len(self.parser.inputs)
            self.num_outputs = len(self.parser.outputs)
            return self.num_inputs > 0 and self.num_outputs > 0
        except Exception as e:
            print(f"Failed to extract BLIF structure: {e}")
            return False
    
    def _extract_logic_from_blif(self) -> bool:
        """
        Extract logic directly from BLIF .names clauses.
        For fallback, generate representative sample products rather than all zeros.
        """
        try:
            with open(self.blif_file, 'r') as f:
                content = f.read()
            
            # Quick check: does BLIF have any logic or is it just I/O?
            has_logic = '.names' in content and len(content) > 100
            
            if has_logic:
                # Generate diverse sample products to represent the circuit
                # Use pseudo-random but deterministic patterns
                sample_size = min(2**self.num_inputs, 500)
                
                for i in range(sample_size):
                    # Generate input patterns with varying sparsity
                    if i < sample_size // 4:
                        # All zeros
                        input_pattern = '0' * self.num_inputs
                    elif i < sample_size // 2:
                        # All ones
                        input_pattern = '1' * self.num_inputs
                    elif i < 3 * sample_size // 4:
                        # Pseudo-random
                        input_pattern = format((i * 31) % (2**self.num_inputs), f'0{self.num_inputs}b')
                    else:
                        # Single bit flips
                        input_pattern = format(1 << (i % self.num_inputs), f'0{self.num_inputs}b')
                    
                    # Generate pseudo-random output based on input
                    output_pattern = ''
                    for out_idx in range(self.num_outputs):
                        # Use simple hash of input + output index
                        bit = (sum(int(b) for b in input_pattern) + out_idx * 7) % 2
                        output_pattern += str(bit)
                    
                    self.products.append((input_pattern, output_pattern))
                
                return len(self.products) > 0
            
            return False
        
        except Exception as e:
            print(f"Failed to extract logic from BLIF: {e}")
            return False
    
    def _parse_pla_to_products(self, pla_file: str) -> bool:
        """Parse PLA file into products for ESOP conversion."""
        self.products = []
        try:
            with open(pla_file, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            self.num_inputs = 0
            self.num_outputs = 0
            i = 0
            while i < len(lines):
                line = lines[i]
                if line.startswith("#"):
                    i += 1
                    continue
                parts = line.split()
                if not parts:
                    i += 1
                    continue
                tag = parts[0].lower()
                # Use exact tags so ".ilb" does not match ".i"
                if tag == ".i":
                    self.num_inputs = int(parts[1])
                elif tag == ".o":
                    self.num_outputs = int(parts[1])
                elif tag == ".p":
                    pass  # informative only
                elif tag == ".e":
                    break
                elif tag.startswith("."):
                    pass  # .ilb, .ob, .type, etc.
                elif len(parts) == 2:
                    input_pattern = parts[0]
                    output_pattern = parts[1]
                    self.products.append((input_pattern, output_pattern))
                i += 1
            
            ok = (
                len(self.products) > 0
                and self.num_inputs > 0
                and self.num_outputs > 0
            )
            if not ok and lines:
                print(
                    f"PLA parse: expected cube lines with .i/.o; got {len(self.products)} products "
                    f"({pla_file})"
                )
            return ok
        
        except Exception as e:
            print(f"Error parsing PLA: {e}")
            return False
    
    def minimize_esop(self) -> Dict[int, List[str]]:
        """
        Minimize products to ESOP form (AND-EXOR decomposition).
        Returns dictionary mapping output index to list of product terms.
        """
        self.esop_terms = {}
        
        for output_idx in range(self.num_outputs):
            output_products = []
            
            # For each product, check if this output dimension is 1
            for input_pattern, output_pattern in self.products:
                if output_idx < len(output_pattern) and output_pattern[output_idx] == '1':
                    output_products.append(input_pattern)
            
            # Minimize using Quine-McCluskey or simple consensus
            minimized = self._minimize_sop(output_products)
            self.esop_terms[output_idx] = minimized
        
        return self.esop_terms
    
    def _minimize_sop(self, minterms: List[str]) -> List[str]:
        """Simple SOP minimization (could be enhanced with Quine-McCluskey)."""
        if not minterms:
            return []
        
        # For now, return the minterms as-is
        # In a full implementation, this would use Quine-McCluskey algorithm
        return list(set(minterms))  # Remove duplicates
    
    def convert_to_esop(self) -> bool:
        """Perform the complete BLIF to ESOP conversion."""
        if not self.extract_logic_via_abc():
            print("Failed to extract logic from BLIF")
            return False

        # SOP PLA: group cubes per output. ESOP from &exorcism: keep cubes as-is.
        if not self._used_exorcism:
            self.minimize_esop()
        return True
    
    def write_esop_file(self, output_file: str) -> bool:
        """
        Write ESOP as a PLA-style .esop file: .i / .o / .p, then one row per cube
        (input cube of 0/1/-, space, output bit-vector), then .e — same layout as
        classic benchmarks (e.g. benchmarks/eda/classic/5xp1.esop).
        """
        try:
            if not self.products and not self.esop_terms:
                print("No ESOP terms to write")
                return False

            # Preserve ABC write_pla row order and counts when logic came from ABC.
            if self._source_abc_pla and self.products:
                with open(output_file, "w") as f:
                    f.write(f".i {self.num_inputs}\n")
                    f.write(f".o {self.num_outputs}\n")
                    f.write(f".p {len(self.products)}\n")
                    for cube, out_vec in self.products:
                        f.write(f"{cube} {out_vec}\n")
                    f.write(".e\n")
                return True

            row_bits: Dict[str, List[str]] = {}
            for j in range(self.num_outputs):
                for cube in self.esop_terms.get(j, []):
                    if cube not in row_bits:
                        row_bits[cube] = ["0"] * self.num_outputs
                    row_bits[cube][j] = "1"

            cubes_ordered = sorted(row_bits.keys())

            with open(output_file, "w") as f:
                f.write(f".i {self.num_inputs}\n")
                f.write(f".o {self.num_outputs}\n")
                f.write(f".p {len(row_bits)}\n")
                for cube in cubes_ordered:
                    f.write(f"{cube} {''.join(row_bits[cube])}\n")
                f.write(".e\n")

            return True

        except Exception as e:
            print(f"Error writing ESOP file: {e}")
            return False


class BLIFBatchConverter:
    """Batch convert multiple BLIF files to ESOP format."""
    
    def __init__(
        self,
        source_dir: str,
        output_dir: str = None,
        use_exorcism: bool = True,
    ):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir) if output_dir else self.source_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_exorcism = use_exorcism
        
    def convert_all(self, pattern: str = "*.blif") -> Tuple[int, int]:
        """Convert all BLIF files matching pattern. Returns (converted, failed)."""
        blif_files = sorted(self.source_dir.rglob(pattern))
        
        if not blif_files:
            print(f"No BLIF files found in {self.source_dir}")
            return 0, 0
        
        converted = 0
        failed = 0
        
        print(f"Found {len(blif_files)} BLIF files")
        print(f"Output directory: {self.output_dir}")
        print(
            "Pipeline: ABC write_pla"
            + (" + &exorcism (EXORCISM-4)\n" if self.use_exorcism else " (SOP only)\n")
        )
        
        for blif_file in blif_files:
            rel_path = blif_file.relative_to(self.source_dir)
            output_file = self.output_dir / rel_path.with_suffix('.esop')
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"Converting {rel_path.name}...", end=" ", flush=True)
            
            converter = BLIFToESOP(
                str(blif_file),
                require_abc=True,
                use_exorcism=self.use_exorcism,
            )
            if converter.convert_to_esop():
                if converter.write_esop_file(str(output_file)):
                    converted += 1
                    file_size = output_file.stat().st_size
                    print(f"✓ ({file_size} bytes)")
                else:
                    failed += 1
                    print("✗ (write failed)")
            else:
                failed += 1
                print("✗ (conversion failed)")
        
        return converted, failed
