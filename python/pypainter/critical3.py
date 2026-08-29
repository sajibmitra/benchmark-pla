# rpla_benchmark_critical_analysis.py
import pandas as pd
import matplotlib.pyplot as plt

# --------------------------------------------------
# Gate-Level Metrics
# --------------------------------------------------
gate_metrics = {
    "Feynman": {"Area": 63, "Wire": 42, "Power": 0.77452, "HPWL": 595467,
                "Rise": 2.3442, "Fall": 2.0262},
    "MUX": {"Area": 66, "Wire": 313, "Power": 2.1578, "HPWL": 898293,
            "Rise": 1.6, "Fall": 1.8279},
    "UMG": {"Area": 65, "Wire": 210, "Power": 1.4402, "HPWL": 896230,
            "Rise": 1.6, "Fall": 1.6},
    "UNG": {"Area": 64, "Wire": 179, "Power": 1.4619, "HPWL": 896062,
            "Rise": 1.6, "Fall": 1.6},
}

# --------------------------------------------------
# Example Benchmark Gate Counts
# Replace these with your actual GA and AI values
# --------------------------------------------------
benchmarks = {
    "5xp1":  {"GA_existing": 166, "AI_existing": 115,
              "GA_proposed": 132, "AI_proposed": 47},
    "9sym":  {"GA_existing": 427, "AI_existing": 377,
              "GA_proposed": 377, "AI_proposed": 103},
    "adr3":  {"GA_existing": 67,  "AI_existing": 46,
              "GA_proposed": 52,  "AI_proposed": 24},
    "apex3": {"GA_existing": 3998,"AI_existing": 1795,
              "GA_proposed": 3719,"AI_proposed": 516},
    "b12":   {"GA_existing": 159, "AI_existing": 167,
              "GA_proposed": 127, "AI_proposed": 50},
}

# --------------------------------------------------
# Function to Compute Metrics
# --------------------------------------------------
def compute_metrics(ga, ai, design="existing"):
    if design == "existing":
        n_mux = ga
        n_fey = ai

        area = n_mux * gate_metrics["MUX"]["Area"] + \
               n_fey * gate_metrics["Feynman"]["Area"]

        wire = n_mux * gate_metrics["MUX"]["Wire"] + \
               n_fey * gate_metrics["Feynman"]["Wire"]

        power = n_mux * gate_metrics["MUX"]["Power"] + \
                n_fey * gate_metrics["Feynman"]["Power"]

        hpwl = n_mux * gate_metrics["MUX"]["HPWL"] + \
               n_fey * gate_metrics["Feynman"]["HPWL"]

        rise = (n_mux * gate_metrics["MUX"]["Rise"] +
                n_fey * gate_metrics["Feynman"]["Rise"]) / (n_mux + n_fey)

        fall = (n_mux * gate_metrics["MUX"]["Fall"] +
                n_fey * gate_metrics["Feynman"]["Fall"]) / (n_mux + n_fey)

    else:  # proposed
        n_umg = ga * 0.5
        n_ung = ga * 0.5
        n_fey = ai

        area = (n_umg * gate_metrics["UMG"]["Area"] +
                n_ung * gate_metrics["UNG"]["Area"] +
                n_fey * gate_metrics["Feynman"]["Area"])

        wire = (n_umg * gate_metrics["UMG"]["Wire"] +
                n_ung * gate_metrics["UNG"]["Wire"] +
                n_fey * gate_metrics["Feynman"]["Wire"])

        power = (n_umg * gate_metrics["UMG"]["Power"] +
                 n_ung * gate_metrics["UNG"]["Power"] +
                 n_fey * gate_metrics["Feynman"]["Power"])

        hpwl = (n_umg * gate_metrics["UMG"]["HPWL"] +
                n_ung * gate_metrics["UNG"]["HPWL"] +
                n_fey * gate_metrics["Feynman"]["HPWL"])

        total_gates = n_umg + n_ung + n_fey
        rise = ((n_umg * gate_metrics["UMG"]["Rise"] +
                 n_ung * gate_metrics["UNG"]["Rise"] +
                 n_fey * gate_metrics["Feynman"]["Rise"]) / total_gates)

        fall = ((n_umg * gate_metrics["UMG"]["Fall"] +
                 n_ung * gate_metrics["UNG"]["Fall"] +
                 n_fey * gate_metrics["Feynman"]["Fall"]) / total_gates)

    return area, wire, power, hpwl, rise, fall

# --------------------------------------------------
# Build DataFrame
# --------------------------------------------------
rows = []
for bench, vals in benchmarks.items():
    existing_metrics = compute_metrics(
        vals["GA_existing"], vals["AI_existing"], "existing")
    proposed_metrics = compute_metrics(
        vals["GA_proposed"], vals["AI_proposed"], "proposed")

    rows.append([bench, "Existing", *existing_metrics])
    rows.append([bench, "Proposed", *proposed_metrics])

df = pd.DataFrame(rows, columns=[
    "Benchmark", "Design", "Area", "WireLength",
    "Power", "HPWL", "RiseTime", "FallTime"
])

# --------------------------------------------------
# Plot Critical Line Charts
# --------------------------------------------------
metrics = ["Area", "WireLength", "Power", "HPWL", "RiseTime", "FallTime"]
colors = {"Existing": "#d62728", "Proposed": "#1f77b4"}

fig, axes = plt.subplots(3, 2, figsize=(14, 12))
axes = axes.flatten()

for ax, metric in zip(axes, metrics):
    for design in ["Existing", "Proposed"]:
        subset = df[df["Design"] == design]
        ax.plot(subset["Benchmark"], subset[metric],
                marker='o', linewidth=2.5,
                label=design, color=colors[design])

    ax.set_title(metric)
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.tick_params(axis='x', rotation=45)

fig.suptitle(
    "Benchmark-Level Critical Analysis of Proposed (UMG/UNG) vs Existing (MUX) RPLA Designs",
    fontsize=14, fontweight='bold'
)

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='upper center', ncol=2)

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig("rpla_benchmark_critical_analysis.png",
            dpi=600, bbox_inches='tight')
plt.show()
