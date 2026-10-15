"""Logic synthesis service using Yosys and ABC for reversible gates."""
from typing import Literal

from eda_hub.pages.cmos_ptl_tgl.reversible_templates import GATE_LOGIC, render_gate_logic_comment
from eda_hub.pages.post_cmos.physical import resolve_post_cmos_device_model
from eda_hub.tools import ToolNotFoundError, resolve_yosys_executable

# Supported synthesis formats
SYNTHESIS_FORMATS = frozenset({
    "verilog",  # Verilog netlist
    "blif",     # Berkeley Logic Interchange Format
    "aiger",    # And-Inverter Graph format
    "bench",    # BENCH format
})

# Gate type mappings for synthesis
GATE_SYNTHESIS_MAP = {
    "NOT": "not",
    "FG": "feynman",
    "TG": "toffoli",
    "FRG": "fredkin",
    "PG": "peres",
    "MUX": "mux",
    "UMG": "umg",
    "UNG": "ung",
    "NMG": "nmg",
    "custom": "custom",
}


def _normalize_equation(expr: str) -> str:
    return (
        expr.replace("¬", "!")
            .replace("∧", "&")
            .replace("∨", "|")
            .replace("⊕", "^")
    )


def _gate_verilog_definition(gate: str) -> tuple[list[str], list[str], list[str]]:
    gate_upper = gate.upper()
    logic = GATE_LOGIC.get(gate_upper, GATE_LOGIC["custom"])
    return logic["inputs"], logic["outputs"], logic["equations"]


def generate_synthesis_script(
    gate: str,
    technology: str,
    output_format: str,
    vdd: float = 0.9,
    model_type: str | None = None,
) -> str:
    """Generate a Yosys synthesis script for a reversible gate."""
    gate_lower = gate.lower()
    gate_upper = gate.upper()
    model_line = resolve_post_cmos_device_model(technology, model_type)["citation"]

    if output_format not in SYNTHESIS_FORMATS:
        raise ValueError(f"Unsupported synthesis format: {output_format}")

    inputs, outputs, equations = _gate_verilog_definition(gate_upper)
    port_list = ", ".join(inputs + outputs)

    verilog_body = [
        f"module {gate_lower}_gate({port_list});",
        *(f"  input {inp};" for inp in inputs),
        *(f"  output {out};" for out in outputs),
        "",
    ]

    for eq in equations:
        lhs, rhs = eq.split("=", 1)
        verilog_body.append(f"  assign {lhs.strip()} = {_normalize_equation(rhs.strip())};")

    verilog_body.append("endmodule")
    verilog_source = "\n".join(verilog_body)

    script = f"""# Yosys synthesis script for reversible gate: {gate}
# Technology: {technology}
# Model: {model_line}
# Output format: {output_format}
# Vdd: {vdd}V

{render_gate_logic_comment(gate_upper, 'yosys')}
# Read the reversible gate definition
read_verilog -sv << EOF
{verilog_source}
EOF

# Synthesis flow
hierarchy -check
proc
opt
techmap
opt

# Generate output in requested format
"""

    if output_format == "verilog":
        script += "write_verilog -noattr synthesized_gate.v\n"
    elif output_format == "blif":
        script += "write_blif synthesized_gate.blif\n"
    elif output_format == "aiger":
        script += "write_aiger synthesized_gate.aiger\n"
    elif output_format == "bench":
        script += "write_bench synthesized_gate.bench\n"

    script += """
# Generate statistics
stat
"""

    return script


def run_yosys_synthesis(
    gate: str,
    technology: str,
    output_format: str,
    vdd: float = 0.9,
    model_type: str | None = None,
) -> str:
    """Run Yosys synthesis and return the result."""
    import subprocess
    import tempfile
    import os

    # Generate synthesis script
    script_content = generate_synthesis_script(gate, technology, output_format, vdd, model_type)
    model_line = resolve_post_cmos_device_model(technology, model_type)["citation"]

    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ys', delete=False) as script_file:
        script_file.write(script_content)
        script_path = script_file.name

    try:
        yosys_cmd = resolve_yosys_executable()
    except ToolNotFoundError as exc:
        return f"Error: {exc}"

    try:
        # Run Yosys
        result = subprocess.run(
            [yosys_cmd, '-s', script_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return f"Error: Yosys synthesis failed\n{result.stderr}"

        gate_upper = gate.upper()
        logic = GATE_LOGIC.get(gate_upper, GATE_LOGIC["custom"])
        logic_lines = [
            f"Gate: {gate_upper}",
            f"Technology: {technology}",
            f"Model: {model_line}",
            f"Inputs: {', '.join(logic['inputs'])}",
            f"Outputs: {', '.join(logic['outputs'])}",
            "Equations:",
            *logic['equations'],
            "",
        ]
        logic_summary = "\n".join(logic_lines)

        return f"Yosys Synthesis Result for {gate} ({technology}, {model_line})\n\n{logic_summary}{result.stdout}"

    except subprocess.TimeoutExpired:
        return "Error: Yosys synthesis timed out"
    except FileNotFoundError:
        return "Error: Yosys not found under EDA_ROOT. Set EDA_YOSYS to a path under Data/eda."
    finally:
        # Clean up temporary file
        try:
            os.unlink(script_path)
        except:
            pass


def generate_abc_optimization(
    gate: str,
    technology: str,
    input_format: str = "blif",
) -> str:
    """Generate ABC optimization script for logic minimization."""
    gate_lower = gate.lower()

    abc_script = f"""# ABC optimization script for {gate}
# Technology: {technology}

# Read the gate netlist
read {gate_lower}_gate.{input_format}

# Logic optimization flow
strash
rewrite -l
refactor -l
balance
rewrite -l
refactor -l
balance

# Technology mapping (if applicable)
# map

# Generate optimized output
write_blif {gate_lower}_optimized.blif

# Print statistics
print_stats
"""

    return abc_script


__all__ = [
    "SYNTHESIS_FORMATS",
    "GATE_SYNTHESIS_MAP",
    "generate_synthesis_script",
    "run_yosys_synthesis",
    "generate_abc_optimization",
]