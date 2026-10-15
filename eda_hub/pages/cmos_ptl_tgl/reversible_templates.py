"""Generate Liberty, LEF, and SPICE template files for reversible gates with support for CNTFET and memristor technologies."""
from typing import Literal

from eda_hub.pages.post_cmos.physical import resolve_post_cmos_device_model

# Supported gate types
GATE_TYPES = frozenset({
    "NOT",      # 1×1: P = ¬A
    "FG",       # 2×2 Feynman Gate: P = A, Q = A ⊕ B
    "TG",       # 3×3 Toffoli Gate: P = A, Q = B, R = (A ∧ B) ⊕ C
    "FRG",      # 3×3 Fredkin Gate: P = A, Q = (A' ∧ B) ⊕ (A ∧ C), R = (A' ∧ C) ⊕ (A ∧ B)
    "PG",       # 3×3 Peres Gate: P = A, Q = A ⊕ B, R = (A ∧ B) ⊕ C
    "MUX",      # 3×3 Multiplexer Gate: P = A, Q = A ⊕ B ⊕ C, R = (A ∧ B) ⊕ (A' ∧ C)
    "UMG",      # 3×3 Universal Multiplexer Gate
    "UNG",      # 3×3 Universal NOR Gate
    "NMG",      # 3×3 NMG Gate
    "custom",   # User-defined custom gate
})

# Supported technologies (lowercase for validation)
TECHNOLOGIES = frozenset({
    "cntfet",      # Carbon Nanotube FET
    "memristor",   # Memristor-based reversible logic
})

# Supported file formats
FILE_FORMATS = frozenset({
    "liberty",  # Liberty (.lib) format
    "lef",      # LEF (Layout Exchange Format)
    "spice",    # SPICE netlist format
    "verilog",  # Verilog netlist format
    "gds",      # GDSII layout placeholder format
})

GATE_LOGIC = {
    "NOT": {
        "description": "P = ¬A",
        "inputs": ["A"],
        "outputs": ["P"],
        "equations": ["P = ¬A"],
    },
    "FG": {
        "description": "P = A, Q = A ⊕ B",
        "inputs": ["A", "B"],
        "outputs": ["P", "Q"],
        "equations": ["P = A", "Q = A ⊕ B"],
    },
    "TG": {
        "description": "P = A, Q = B, R = (A ∧ B) ⊕ C",
        "inputs": ["A", "B", "C"],
        "outputs": ["P", "Q", "R"],
        "equations": ["P = A", "Q = B", "R = (A ∧ B) ⊕ C"],
    },
    "FRG": {
        "description": "P = A, Q = (¬A ∧ B) ∨ (A ∧ C), R = (¬A ∧ C) ∨ (A ∧ B)",
        "inputs": ["A", "B", "C"],
        "outputs": ["P", "Q", "R"],
        "equations": ["P = A", "Q = (¬A ∧ B) ∨ (A ∧ C)", "R = (¬A ∧ C) ∨ (A ∧ B)"],
    },
    "PG": {
        "description": "P = A, Q = A ⊕ B, R = C ⊕ (A ∧ B)",
        "inputs": ["A", "B", "C"],
        "outputs": ["P", "Q", "R"],
        "equations": ["P = A", "Q = A ⊕ B", "R = C ⊕ (A ∧ B)"],
    },
    "MUX": {
        "description": "P = A, Q = A ⊕ B ⊕ C, R = (¬A ∧ C) ⊕ (A ∧ B)",
        "inputs": ["A", "B", "C"],
        "outputs": ["P", "Q", "R"],
        "equations": ["P = A", "Q = A ⊕ B ⊕ C", "R = (¬A ∧ C) ⊕ (A ∧ B)"],
    },
    "UMG": {
        "description": "P = A, Q = B ⊕ C, R = (¬A ∧ C) ⊕ (A ∧ B)",
        "inputs": ["A", "B", "C"],
        "outputs": ["P", "Q", "R"],
        "equations": ["P = A", "Q = B ⊕ C", "R = (¬A ∧ C) ⊕ (A ∧ B)"],
    },
    "UNG": {
        "description": "P = A, Q = B, R = (A ∨ B) ⊕ C",
        "inputs": ["A", "B", "C"],
        "outputs": ["P", "Q", "R"],
        "equations": ["P = A", "Q = B", "R = (A ∨ B) ⊕ C"],
    },
    "NMG": {
        "description": "P = A ⊕ B, Q = (B ∧ ¬C) ⊕ (A ∧ C), R = (¬B ∧ C) ⊕ (A ∧ ¬C)",
        "inputs": ["A", "B", "C"],
        "outputs": ["P", "Q", "R"],
        "equations": [
            "P = A ⊕ B",
            "Q = (B ∧ ¬C) ⊕ (A ∧ C)",
            "R = (¬B ∧ C) ⊕ (A ∧ ¬C)",
        ],
    },
    "custom": {
        "description": "User-defined reversible gate",
        "inputs": ["A", "B", "C"],
        "outputs": ["P", "Q", "R"],
        "equations": ["P = A", "Q = B", "R = C"],
    },
}

COMMENT_PREFIX = {
    "liberty": " * ",
    "lef": "# ",
    "spice": "* ",
    "verilog": "// ",
    "gds": "# ",
}

BLOCK_OPEN = {
    "liberty": "/*\n",
    "lef": "",
    "spice": "",
    "verilog": "",
    "gds": "",
}

BLOCK_CLOSE = {
    "liberty": " */\n",
    "lef": "",
    "spice": "",
    "verilog": "",
    "gds": "",
}


def _model_header_line(technology: str, model_type: str | None) -> str:
    m = resolve_post_cmos_device_model(technology, model_type)
    return f"Model: {m['citation']}"


def _liberty_area_placeholder(technology: str, model_type: str | None, io_total: int) -> float:
    m = resolve_post_cmos_device_model(technology, model_type)
    if technology.lower() == "memristor":
        r_ratio = m["roff_ohm"] / max(m["ron_ohm"], 1.0)
        return round(85.0 + io_total * 12.0 + 8.0 * (r_ratio / 100.0), 1)
    length_scale = m["lch_nm"] / 45.0
    return round(72.0 * (length_scale**0.85) + io_total * 8.0, 1)


def _liberty_leakage_uw(technology: str, model_type: str | None) -> float:
    m = resolve_post_cmos_device_model(technology, model_type)
    if technology.lower() == "memristor":
        r_leak = m["ron_ohm"] / 1e6
        return round(0.002 + r_leak, 4)
    ioff = m.get("ioff_a", 1e-9)
    return round(max(ioff * m["vdd_v"] * 1e6, 0.0005), 4)


def _liberty_delay_base_ns(technology: str, model_type: str | None, vdd: float) -> float:
    m = resolve_post_cmos_device_model(technology, model_type)
    if technology.lower() == "memristor":
        base = 0.08 + 0.015 * (m["roff_ohm"] / 10000.0)
        if m.get("model_type") == "yakopcic":
            base *= 0.85
        return base
    length_scale = m["lch_nm"] / 45.0
    vdd_ratio = vdd / max(m["vdd_v"], 0.1)
    return 0.025 * length_scale / max(vdd_ratio, 0.5)


def _boolean_equation_rhs_to_verilog(rhs: str) -> str:
    """Map Unicode Boolean notation in GATE_LOGIC equations to Verilog operators."""
    s = rhs.strip()
    s = s.replace("¬", "~")
    s = s.replace("∧", "&")
    s = s.replace("∨", "|")
    s = s.replace("⊕", "^")
    return s


def render_gate_logic_comment(gate: str, file_format: str) -> str:
    gate_upper = gate.upper()
    logic = GATE_LOGIC.get(gate_upper, GATE_LOGIC["custom"])
    prefix = COMMENT_PREFIX.get(file_format, "# ")

    if file_format == "liberty":
        lines = [BLOCK_OPEN[file_format]]
        lines.append(f"{prefix}Gate logic for {gate_upper}")
        lines.append(f"{prefix}Inputs: {', '.join(logic['inputs'])}")
        lines.append(f"{prefix}Outputs: {', '.join(logic['outputs'])}")
        lines.append(f"{prefix}Equations:")
        for eq in logic["equations"]:
            lines.append(f"{prefix}{eq}")
        lines.append(BLOCK_CLOSE[file_format])
        return "\n".join(lines)

    lines = [
        f"{prefix}Gate logic for {gate_upper}",
        f"{prefix}Inputs: {', '.join(logic['inputs'])}",
        f"{prefix}Outputs: {', '.join(logic['outputs'])}",
        f"{prefix}Equations:",
    ]
    for eq in logic["equations"]:
        lines.append(f"{prefix}{eq}")
    lines.append("")
    return "\n".join(lines)


def generate_liberty_template(
    gate: str,
    technology: str,
    vdd: float = 0.9,
    model_type: str | None = None,
) -> str:
    """Generate a Liberty template for a reversible gate."""
    gate_upper = gate.upper()
    tech_display = "CNTFET" if technology.lower() == "cntfet" else "Memristor"
    model_line = _model_header_line(technology, model_type)
    
    # Map gate to function description
    gate_funcs = {
        "NOT": "1×1 NOT gate: P = ¬A",
        "FG": "2×2 Feynman gate: P = A, Q = A ⊕ B",
        "TG": "3×3 Toffoli gate: P = A, Q = B, R = (A ∧ B) ⊕ C",
        "FRG": "3×3 Fredkin gate",
        "PG": "3×3 Peres gate",
        "MUX": "3×3 Multiplexer gate",
        "UMG": "3×3 Universal Multiplexer gate",
        "UNG": "3×3 Universal NOR gate",
        "NMG": "3×3 NMG gate",
        "custom": "Custom reversible gate",
    }
    
    gate_desc = gate_funcs.get(gate_upper, f"{gate_upper} reversible gate")
    
    # Get input/output counts
    io_counts = {
        "NOT": (1, 1),
        "FG": (2, 2),
        "TG": (3, 3),
        "FRG": (3, 3),
        "PG": (3, 3),
        "MUX": (3, 3),
        "UMG": (3, 3),
        "UNG": (3, 3),
        "NMG": (3, 3),
        "custom": (3, 3),
    }
    inputs, outputs = io_counts.get(gate_upper, (1, 1))
    area_placeholder = _liberty_area_placeholder(technology, model_type, inputs + outputs)
    leakage_uw = _liberty_leakage_uw(technology, model_type)
    delay_base = _liberty_delay_base_ns(technology, model_type, vdd)
    
    lib_template = f"""/*
 * Reversible Gate Library - {gate_upper}
 * Technology: {tech_display}
 * {model_line}
 * Vdd: {vdd}V
 * Generated template for post-CMOS synthesis
 * 
 * {gate_desc}
 */

{render_gate_logic_comment(gate_upper, 'liberty')}
library({gate_upper}_{technology}_rev) {{
  
  /* Library-wide attributes */
  time_unit : "1ns";
  voltage_unit : "1V";
  current_unit : "1uA";
  capacitive_load_unit(1, pf);
  leakage_power_unit : "1uW";
  pulling_resistance_unit : "1kohm";
  
  slew_upper_threshold_pct_rise : 80.0;
  slew_upper_threshold_pct_fall : 80.0;
  slew_lower_threshold_pct_rise : 20.0;
  slew_lower_threshold_pct_fall : 20.0;
  
  /* Technology specification */
  define_cell_area( area : 1.0; );
  
  technology( "{technology}_reversible" ) {{
    capacitive_load_unit : 1pf;
    voltage_unit : "1V";
    current_unit : "1uA";
    time_unit : "1ns";
    nom_process : 1.0;
    nom_temperature : 25.0;
    nom_voltage : {vdd};
  }}
  
  /* Operational conditions */
  operating_conditions( nom ) {{
    process : 1.0;
    temperature : 25.0;
    voltage : {vdd};
    tree_type : balanced_tree;
  }}
  
  /* Cell: Reversible {gate_upper} */
  cell( rev_{gate_upper.lower()} ) {{
    description : "{gate_desc}";
    area : {{ value : {area_placeholder}; }} /* Placeholder area in lambda^2 — fill from ngspice */
    
    /* Power specification */
    cell_leakage_power : {leakage_uw}; /* uW @ nominal conditions */
    
    /* Pin list */
    pin( VDD ) {{
      direction : inout;
      capacitance : 0.05;
    }}
    
    pin( GND ) {{
      direction : inout;
      capacitance : 0.05;
    }}
    
    /* Input pins */
"""

    # Add input pins
    input_names = ["A", "B", "C", "D"]
    for i in range(inputs):
        lib_template += f"""    pin( {input_names[i]} ) {{
      direction : input;
      capacitance : 0.02;
      rise_capacitance : 0.018;
      fall_capacitance : 0.022;
      max_transition : 0.5;
    }}
    
"""
    
    # Add output pins
    output_names = ["P", "Q", "R", "S"]
    d0 = f"{delay_base:.3f}"
    d1 = f"{delay_base * 1.4:.3f}"
    d2 = f"{delay_base * 2.0:.3f}"
    d3 = f"{delay_base * 3.2:.3f}"
    d4 = f"{delay_base * 5.5:.3f}"
    for i in range(outputs):
        lib_template += f"""    pin( {output_names[i]} ) {{
      direction : output;
      capacitance : 0.01;
      max_capacitance : 0.1;
      max_transition : 0.5;
      
      timing() {{
        related_pin : "{input_names[0]}";
        timing_type : combinational;
        cell_rise(delay_template_5x5) {{
          index_1("0.01, 0.05, 0.1, 0.2, 0.5");
          index_2("0.01, 0.05, 0.1, 0.2, 0.5");
          values(\\
            "{d0}, {d1}, {d2}, {d3}, {d4}", \\
            "{d1}, {d2}, {d2}, {d3}, {d4}", \\
            "{d2}, {d2}, {d3}, {d3}, {d4}", \\
            "{d3}, {d3}, {d3}, {d4}, {d4}", \\
            "{d4}, {d4}, {d4}, {d4}, {d4}");
        }}
        cell_fall(delay_template_5x5) {{
          index_1("0.01, 0.05, 0.1, 0.2, 0.5");
          index_2("0.01, 0.05, 0.1, 0.2, 0.5");
          values(\\
            "{d0}, {d1}, {d2}, {d3}, {d4}", \\
            "{d1}, {d2}, {d2}, {d3}, {d4}", \\
            "{d2}, {d2}, {d3}, {d3}, {d4}", \\
            "{d3}, {d3}, {d3}, {d4}, {d4}", \\
            "{d4}, {d4}, {d4}, {d4}, {d4}");
        }}
      }}
    }}
    
"""
    
    lib_template += """  }} /* cell */
}}
"""
    
    return lib_template


def generate_lef_template(
    gate: str,
    technology: str,
    model_type: str | None = None,
) -> str:
    """Generate a LEF template for a reversible gate."""
    gate_upper = gate.upper()
    model_line = _model_header_line(technology, model_type)
    
    # Get input/output counts
    io_counts = {
        "NOT": (1, 1),
        "FG": (2, 2),
        "TG": (3, 3),
        "FRG": (3, 3),
        "PG": (3, 3),
        "MUX": (3, 3),
        "UMG": (3, 3),
        "UNG": (3, 3),
        "NMG": (3, 3),
        "custom": (3, 3),
    }
    inputs, outputs = io_counts.get(gate_upper, (1, 1))
    
    # LEF assumes 1 lambda = 0.1 micrometers
    cell_width = 10 + (inputs + outputs) * 2
    cell_height = 10
    
    logic_comment = render_gate_logic_comment(gate_upper, "lef")
    lef_template = f"""{logic_comment}# LEF Template for Reversible Gate: {gate_upper}
# Technology: {technology}
# {model_line}
# Generated for post-CMOS synthesis

VERSION 5.8;

NAMESCASESENSITIVE ON;

UNITS
  DATABASE MICRONS 1000;
END UNITS

LAYER M1
  TYPE ROUTING;
  DIRECTION HORIZONTAL;
  PITCH 0.4;
  OFFSET 0.2;
  WIDTH 0.24;
  SPACING 0.24;
  AREA 0.0576;
END M1

LAYER VIA01
  TYPE CUT;
  SPACING 0.2;
  SIZE 0.2 BY 0.2;
END VIA01

LAYER M2
  TYPE ROUTING;
  DIRECTION VERTICAL;
  PITCH 0.4;
  OFFSET 0.2;
  WIDTH 0.24;
  SPACING 0.24;
  AREA 0.0576;
END M2

MACRO rev_{gate_upper.lower()}
  CLASS BLOCK;
  SYMMETRY X Y;
  ORIGIN 0 0;
  SIZE {cell_width} {cell_height};
  
  SITE CoreSite;
  
  PIN VDD
    USE POWER;
    PORT
      LAYER M1;
      RECT 0 {cell_height - 1} {cell_width} {cell_height};
    END
  END VDD
  
  PIN GND
    USE GROUND;
    PORT
      LAYER M1;
      RECT 0 0 {cell_width} 1;
    END
  END GND
  
"""

    # Add input pins
    input_names = ["A", "B", "C", "D"]
    for i in range(inputs):
        x = 1 + i * 2
        lef_template += f"""  PIN {input_names[i]}
    DIRECTION INPUT;
    USE SIGNAL;
    PORT
      LAYER M1;
      RECT {x} 0 {x + 1} 1;
    END
  END {input_names[i]}
  
"""
    
    # Add output pins
    output_names = ["P", "Q", "R", "S"]
    for i in range(outputs):
        x = 1 + (inputs + i) * 2
        lef_template += f"""  PIN {output_names[i]}
    DIRECTION OUTPUT;
    USE SIGNAL;
    PORT
      LAYER M1;
      RECT {x} {cell_height - 1} {x + 1} {cell_height};
    END
  END {output_names[i]}
  
"""
    
    lef_template += f"""END rev_{gate_upper.lower()}

END LIBRARY
"""
    
    return lef_template


def generate_spice_template(
    gate: str,
    technology: str,
    vdd: float = 0.9,
    model_type: str | None = None,
) -> str:
    """Generate a SPICE template for a reversible gate."""
    gate_upper = gate.upper()
    model_line = _model_header_line(technology, model_type)
    dev = resolve_post_cmos_device_model(technology, model_type)
    
    # Get input/output counts
    io_counts = {
        "NOT": (1, 1),
        "FG": (2, 2),
        "TG": (3, 3),
        "FRG": (3, 3),
        "PG": (3, 3),
        "MUX": (3, 3),
        "UMG": (3, 3),
        "UNG": (3, 3),
        "NMG": (3, 3),
        "custom": (3, 3),
    }
    inputs, outputs = io_counts.get(gate_upper, (1, 1))
    
    logic_comment = render_gate_logic_comment(gate_upper, "spice")
    spice_template = f"""{logic_comment}.title Reversible {gate_upper} Gate - {technology} Technology
* {model_line}
* Generated template for post-CMOS synthesis
* Vdd = {vdd}V

.param W_n=100n W_p=200n L=10n

"""    
    if technology.upper() == "CNTFET":
        spice_template += f"""* Carbon Nanotube FET model parameters ({dev.get('model_type', 'stanford')})
.param Lch={dev['lch_nm']}n Dcnt={dev['dcnt_nm']}n Eg={dev['eg_ev']}
.param Vth_n={dev['eg_ev'] / 2.0:.2f} Vth_p=-{dev['eg_ev'] / 2.0:.2f}
.param ION={dev['ion_ua']}u IOFF={dev['ioff_a']:.0e} Cgate={dev['cgate_ff']}f

"""
    elif technology.upper() == "MEMRISTOR":
        spice_template += f"""* Memristor-based reversible logic model ({dev.get('model_type', 'vteam')})
.param Ron={dev['ron_ohm']} Roff={dev['roff_ohm']} D={dev['d_nm']}n
.param Von={dev['von_v']} Voff={dev['voff_v']} x_init={dev['x_init']}

"""
    
    spice_template += f"""* Power supplies
VDD VDD GND {vdd}
VSS VSS GND 0

* Input signal definitions
"""
    
    # Add input voltage sources
    input_names = ["A", "B", "C", "D"]
    for i in range(inputs):
        spice_template += f"V{input_names[i]} {input_names[i]} GND PULSE(0 {vdd} 0 0.1n 0.1n 5n 10n)\n"
    
    spice_template += f"""
* Device instances (placeholder topology for {gate_upper})
"""
    
    logic = GATE_LOGIC.get(gate_upper, GATE_LOGIC["custom"])
    if technology.upper() == "CNTFET":
        spice_template += "* CNTFET devices (carbon nanotube based) — placeholders; replace with full network per gate.\n"
        if gate_upper == "NOT":
            spice_template += f"""
* Inverter-style sketch for NOT (P = ~A)
M1 P A VDD VDD CNTFET_P W={{W_p}} L={{L}} Chirality={{Chirality}}
M2 P A GND GND CNTFET_N W={{W_n}} L={{L}} Chirality={{Chirality}}

"""
        else:
            for eq in logic["equations"]:
                spice_template += f"* {eq}\n"
            spice_template += "* Instantiate pull-up/pull-down or transmission-gate networks per output above.\n\n"
    elif technology.upper() == "MEMRISTOR":
        spice_template += "* Memristor-based reversible logic — placeholders.\n"
        if gate_upper == "NOT":
            spice_template += f"""
* Example memristive link for NOT (P = ~A); tune model for your technology
R1 P A MEMRISTOR W=100n L=50n Roff={{Roff}} Ron={{Ron}} Vth={{Vth_mem}}

"""
        else:
            for eq in logic["equations"]:
                spice_template += f"* {eq}\n"
            spice_template += "* Add memristive / hybrid devices implementing each output equation.\n\n"
    
    spice_template += f"""* Output load capacitance
"""
    output_names = ["P", "Q", "R", "S"]
    for i in range(outputs):
        spice_template += f"CL{i} {output_names[i]} GND 10f\n"
    
    in_names = logic["inputs"]
    out_names = logic["outputs"]
    sub_ports = " ".join(in_names + out_names)
    plot_nodes = " ".join(f"V({n})" for n in in_names + out_names)
    eq_lines = "\n".join(f"* {eq}" for eq in logic["equations"])

    spice_template += f"""
* Analysis: Transient simulation
.tran 0 100n 0 0.1n

* Subcircuit ports match this gate ({gate_upper}): inputs then outputs
.subckt rev_{gate_upper.lower()} {sub_ports}
{eq_lines}
* Insert transistor- or device-level implementation here
.ends rev_{gate_upper.lower()}

* Control and measurement
.control
run
plot {plot_nodes}
.endc

.end
"""
    
    return spice_template


def generate_verilog_template(
    gate: str,
    technology: str,
    vdd: float = 0.9,
    model_type: str | None = None,
) -> str:
    gate_upper = gate.upper()
    logic_comment = render_gate_logic_comment(gate_upper, "verilog")
    model_line = _model_header_line(technology, model_type)
    logic = GATE_LOGIC.get(gate_upper, GATE_LOGIC["custom"])
    port_list = ", ".join(logic["inputs"] + logic["outputs"])
    module_name = f"rev_{gate_upper.lower()}"

    verilog_template = f"""{logic_comment}// Verilog netlist for reversible gate {gate_upper}
// Technology: {technology}
// {model_line}
// Vdd = {vdd}V

module {module_name}({port_list});
"""

    for pin in logic["inputs"]:
        verilog_template += f"  input {pin};\n"
    for pin in logic["outputs"]:
        verilog_template += f"  output {pin};\n"

    verilog_template += "\n  // Combinational reversible mapping (matches gate definition)\n"
    for eq in logic["equations"]:
        if "=" not in eq:
            continue
        lhs, rhs = eq.split("=", 1)
        out_net = lhs.strip()
        verilog_expr = _boolean_equation_rhs_to_verilog(rhs)
        verilog_template += f"  assign {out_net} = {verilog_expr};\n"

    verilog_template += "\nendmodule\n"
    return verilog_template


def generate_gds_template(
    gate: str,
    technology: str,
    vdd: float = 0.9,
    model_type: str | None = None,
) -> str:
    gate_upper = gate.upper()
    logic_comment = render_gate_logic_comment(gate_upper, "gds")
    logic = GATE_LOGIC.get(gate_upper, GATE_LOGIC["custom"])
    model_line = _model_header_line(technology, model_type)

    gds_template = f"""{logic_comment}# GDSII layout placeholder for reversible gate {gate_upper}
# Technology: {technology}
# {model_line}
# Vdd = {vdd}V
# NOTE: This output is a textual placeholder representation. Actual GDSII is binary.

# Cell: rev_{gate_upper.lower()}
# Inputs: {', '.join(logic['inputs'])}
# Outputs: {', '.join(logic['outputs'])}
# Layout cells and routing will depend on technology-specific physical design rules.
"""
    return gds_template


def generate_template(
    gate: str,
    technology: str,
    file_format: str,
    vdd: float = 0.9,
    model_type: str | None = None,
) -> str:
    """Generate a template file for a reversible gate."""
    gate_upper = gate.upper()
    
    if gate_upper not in GATE_TYPES:
        raise ValueError(f"Unsupported gate type: {gate}. Supported: {', '.join(sorted(GATE_TYPES))}")
    
    if technology not in TECHNOLOGIES:
        raise ValueError(f"Unsupported technology: {technology}. Supported: {', '.join(sorted(TECHNOLOGIES))}")
    
    if file_format not in FILE_FORMATS:
        raise ValueError(f"Unsupported file format: {file_format}. Supported: {', '.join(sorted(FILE_FORMATS))}")
    
    if file_format == "liberty":
        return generate_liberty_template(gate_upper, technology, vdd, model_type)
    elif file_format == "lef":
        return generate_lef_template(gate_upper, technology, model_type)
    elif file_format == "spice":
        return generate_spice_template(gate_upper, technology, vdd, model_type)
    elif file_format == "verilog":
        return generate_verilog_template(gate_upper, technology, vdd, model_type)
    elif file_format == "gds":
        return generate_gds_template(gate_upper, technology, vdd, model_type)
    else:
        raise ValueError(f"Unknown file format: {file_format}")


__all__ = [
    "GATE_TYPES",
    "TECHNOLOGIES",
    "FILE_FORMATS",
    "generate_liberty_template",
    "generate_lef_template",
    "generate_spice_template",
    "generate_verilog_template",
    "generate_gds_template",
    "generate_template",
]
