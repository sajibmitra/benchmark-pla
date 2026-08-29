# reversible_gate_analysis.py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------
# Data Definition
# -----------------------------
data = {
    "Gate": [
        "Toffoli", "Fredkin", "Peres", "MUX",
        "Proposed UMG", "Proposed UNG"
    ],
    "Area": [64, 64, 65, 66, 65, 64],
    "WireLength": [179, 179, 74, 313, 210, 179],
    "Power": [1.2552, 1.2030, 2.0522, 2.1578, 1.4402, 1.4619],
    "HPWL": [896062, 896062, 907700, 898293, 896230, 896062],
    "RiseTime": [2.1184, 2.4427, 2.1184, 1.6, 1.6, 1.6],
    "FallTime": [1.8279, 1.4886, 1.8279, 1.8279, 1.6, 1.6],
}

df = pd.DataFrame(data)
df.set_index("Gate", inplace=True)

metrics = df.columns

# -----------------------------
# Normalization for Radar Chart
# Lower values are better -> invert normalization
# -----------------------------
normalized_df = (df.max() - df) / (df.max() - df.min())

# -----------------------------
# Radar Chart
# -----------------------------
angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
angles += angles[:1]

fig = plt.figure(figsize=(16, 7))

ax1 = fig.add_subplot(1, 2, 1, polar=True)

colors = {
    "Toffoli": "#1f77b4",
    "Fredkin": "#ff7f0e",
    "Peres": "#2ca02c",
    "MUX": "#d62728",
    "Proposed UMG": "#9467bd",
    "Proposed UNG": "#17becf",
}

for gate in normalized_df.index:
    values = normalized_df.loc[gate].tolist()
    values += values[:1]
    ax1.plot(angles, values, label=gate, linewidth=2,
             color=colors.get(gate, None))
    ax1.fill(angles, values, alpha=0.1,
             color=colors.get(gate, None))

ax1.set_xticks(angles[:-1])
ax1.set_xticklabels(metrics)
ax1.set_title("Normalized Multi-Metric Comparison of Reversible Gates",
              fontsize=12, pad=20)
ax1.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))

# -----------------------------
# Grouped Bar Chart
# -----------------------------
# ax2 = fig.add_subplot(1, 2, 2)
# x = np.arange(len(metrics))
# width = 0.13

# for i, gate in enumerate(df.index):
#     ax2.bar(x + i * width, df.loc[gate], width,
#             label=gate, color=colors.get(gate, None))

# ax2.set_xticks(x + width * (len(df.index) / 2))
# ax2.set_xticklabels(metrics, rotation=45, ha='right')
# ax2.set_ylabel("Metric Values")
# ax2.set_title("Quantitative Comparison of Reversible Gates")
# ax2.grid(axis='y', linestyle='--', alpha=0.4)

# # Highlight proposed gates
# for spine in ax2.spines.values():
#     spine.set_linewidth(1.2)

# handles, labels = ax2.get_legend_handles_labels()
# fig.legend(handles, labels, loc='lower center', ncol=3)

# plt.tight_layout(rect=[0, 0.05, 1, 1])
plt.savefig("reversible_gate_comparison.png", dpi=600, bbox_inches='tight')
plt.show()
