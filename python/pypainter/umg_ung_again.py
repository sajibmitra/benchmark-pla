# Normalized Multi-Metric Heatmap for Reversible Gates
# Suitable for ICCAD/ACM publication

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# -----------------------------
# 1. Define the Dataset
# -----------------------------
data = {
    "Gate": [
        "Toffoli",
        "Fredkin",
        "Peres",
        "MUX",
        "Proposed UMG",
        "Proposed UNG"
    ],
    "Area (µm²)": [64, 64, 65, 66, 65, 64],
    "Wire Length (µm)": [179, 179, 74, 313, 210, 179],
    "Avg Power (1e-4 W)": [1.2552, 1.2030, 2.0522, 2.1578, 1.4402, 1.4619],
    "HPWL (µm)": [896062, 896062, 907700, 898293, 896230, 896062],
    "Rise Time (ps)": [2.1184, 2.4427, 2.1184, 1.6, 1.6, 1.6],
    "Fall Time (ps)": [1.8279, 1.4886, 1.8279, 1.8279, 1.6, 1.6]
}

df = pd.DataFrame(data)
df.set_index("Gate", inplace=True)

# -----------------------------
# 2. Normalize the Metrics
#    Lower values are better,
#    so we invert after normalization.
# -----------------------------
normalized_df = (df - df.min()) / (df.max() - df.min())
normalized_df = 1 - normalized_df  # Higher value = better performance

# -----------------------------
# 3. Plot the Heatmap
# -----------------------------
plt.figure(figsize=(12, 6))
sns.set_theme(style="white")

heatmap = sns.heatmap(
    normalized_df,
    annot=True,
    fmt=".2f",
    cmap="RdYlGn",          # Green = better, Red = worse
    linewidths=0.5,
    linecolor="gray",
    cbar_kws={"label": "Normalized Performance (Higher is Better)"}
)

plt.title(
    "Normalized Multi-Metric Performance Comparison of Reversible Gates",
    fontsize=14,
    weight="bold"
)
plt.xlabel("Performance Metrics", fontsize=12)
plt.ylabel("Reversible Gates", fontsize=12)
plt.xticks(rotation=30, ha="right")
plt.yticks(rotation=0)

plt.tight_layout()

# -----------------------------
# 4. Save the Figure
# -----------------------------
output_path = "normalized_reversible_gates_heatmap.png"
plt.savefig(output_path, dpi=600, bbox_inches="tight")
plt.show()

print(f"Figure saved as: {output_path}")
