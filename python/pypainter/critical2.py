# critical_line_chart_umg_ung.py
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# --------------------------------------------------
# Data Definition
# --------------------------------------------------
data = {
    "Gate": [
        "Feynman (EXOR)",
        "Toffoli (AND)",
        "Fredkin (OR)",
        "MUX (Existing)",
        "UMG (Proposed)",
        "UNG (Proposed)"
    ],
    "Area": [63, 64, 64, 66, 65, 64],
    "WireLength": [42, 179, 179, 313, 210, 179],
    "Power": [0.77452, 1.2552, 1.2030, 2.1578, 1.4402, 1.4619],
    "HPWL": [595467, 896062, 896062, 898293, 896230, 896062],
    "RiseTime": [2.3442, 2.1184, 2.4427, 1.6, 1.6, 1.6],
    "FallTime": [2.0262, 1.8279, 1.4886, 1.8279, 1.6, 1.6],
}

df = pd.DataFrame(data)

# Metrics to plot
metrics = ["Area", "WireLength", "Power", "HPWL", "RiseTime", "FallTime"]

# --------------------------------------------------
# Normalize data for comparative visualization
# --------------------------------------------------
df_norm = df.copy()
for metric in metrics:
    df_norm[metric] = (df[metric] - df[metric].min()) / (df[metric].max() - df[metric].min())

# --------------------------------------------------
# Plotting
# --------------------------------------------------
plt.figure(figsize=(14, 8))

colors = {
    "Feynman (EXOR)": "#1f77b4",
    "Toffoli (AND)": "#ff7f0e",
    "Fredkin (OR)": "#2ca02c",
    "MUX (Existing)": "#d62728",
    "UMG (Proposed)": "#9467bd",
    "UNG (Proposed)": "#17becf",
}

for idx, row in df_norm.iterrows():
    plt.plot(
        metrics,
        row[metrics],
        marker='o',
        linewidth=2.5 if "Proposed" in row["Gate"] else 1.8,
        markersize=8,
        label=row["Gate"],
        color=colors[row["Gate"]]
    )

# Emphasize proposed gates
for line in plt.gca().get_lines():
    if "Proposed" in line.get_label():
        line.set_linewidth(3.5)

# --------------------------------------------------
# Styling for publication
# --------------------------------------------------
plt.title(
    "Comparative Performance Analysis of Proposed UMG and UNG\n"
    "with Existing Reversible Gates for Logic Operations",
    fontsize=14,
    fontweight='bold'
)

plt.ylabel("Normalized Performance Metrics", fontsize=12)
plt.xlabel("Performance Metrics", fontsize=12)
plt.grid(True, linestyle='--', alpha=0.4)
plt.legend(loc='upper right', fontsize=10, frameon=False)

plt.tight_layout()
plt.savefig("umg_ung_performance_analysis.png", dpi=600, bbox_inches='tight')
plt.show()
