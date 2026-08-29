# impactful_heatmap_umg_ung.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --------------------------------------------------
# Original Data from the Table
# --------------------------------------------------
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

df = pd.DataFrame(data).set_index("Gate")

# --------------------------------------------------
# Baseline Gates for Comparison
# --------------------------------------------------
baseline_umg = df.loc["MUX"]
baseline_ung = df.loc["Fredkin"]

# --------------------------------------------------
# Percentage Improvement Calculation
# Positive value -> Improvement (reduction)
# --------------------------------------------------
def percentage_improvement(proposed, baseline):
    return ((baseline - proposed) / baseline) * 100

umg_improvement = percentage_improvement(
    df.loc["Proposed UMG"], baseline_umg
)
ung_improvement = percentage_improvement(
    df.loc["Proposed UNG"], baseline_ung
)

improvement_df = pd.DataFrame(
    [umg_improvement, ung_improvement],
    index=["Proposed UMG vs MUX", "Proposed UNG vs Fredkin"]
).round(2)

# --------------------------------------------------
# Heatmap Visualization
# --------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 3))

# Create heatmap using imshow
im = ax.imshow(improvement_df.values, cmap="RdYlGn", aspect="auto")

# Axis labels
ax.set_xticks(np.arange(len(improvement_df.columns)))
ax.set_yticks(np.arange(len(improvement_df.index)))
ax.set_xticklabels(improvement_df.columns, rotation=45, ha="right")
ax.set_yticklabels(improvement_df.index)

# Annotate each cell with percentage values
for i in range(improvement_df.shape[0]):
    for j in range(improvement_df.shape[1]):
        value = improvement_df.iloc[i, j]
        ax.text(j, i, f"{value:.1f}%", ha="center", va="center", color="black")

# Title and colorbar
ax.set_title(
    "Percentage Improvement of Proposed UMG and UNG over Baseline Gates",
    fontsize=12,
    pad=15
)
cbar = fig.colorbar(im)
cbar.set_label("Improvement (%)")

plt.tight_layout()
plt.savefig("umg_ung_impact_heatmap.png", dpi=600, bbox_inches="tight")
plt.show()
