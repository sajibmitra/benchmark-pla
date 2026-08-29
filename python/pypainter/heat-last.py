# heatmap_rpla_analysis.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --------------------------------------------------
# Benchmark Data: Existing vs Proposed
# --------------------------------------------------
data = {
    "Benchmark": [
        "5xp1", "9sym", "adr3", "apex3", "b12", "bw", "cordic",
        "duke2", "e64", "inc4", "inc5", "misex1", "misex2",
        "pdc", "rd53", "rd73", "rd84", "sasao", "sao2",
        "t481", "table3", "table5", "vag2", "xor5", "z5xp1", "z9sym"
    ],

    # Existing values
    "GA_existing": [166, 427, 67, 3998, 159, 305, 12162, 941, 2170, 16, 23, 88, 199,
                    3801, 56, 187, 328, 14, 284, 49, 2602, 2539, 2018, 8, 167, 427],
    "GB_existing": [112, 385, 48, 1799, 132, 64, 10640, 667, 2148, 10, 16, 51, 176,
                    3006, 42, 141, 265, 13, 236, 53, 1814, 1819, 1836, 8, 114, 385],
    "AI_existing": [115, 377, 46, 1795, 167, 87, 10661, 674, 2148, 11, 17, 50, 149,
                    3030, 40, 137, 261, 10, 230, 38, 1814, 1682, 1770, 4, 117, 377],
    "QC_existing": [418, 1405, 157, 8654, 453, 446, 41694, 2735, 8410, 34, 53, 193, 122,
                    12096, 134, 487, 928, 29, 890, 134, 7537, 7516, 6926, 8, 425, 1405],

    # Proposed values
    "GA_proposed": [132, 377, 52, 3719, 127, 281, 11389, 874, 2074, 11, 16, 74, 165,
                    3451, 44, 150, 267, 9, 257, 40, 2439, 2384, 1835, 4, 139, 377],
    "GB_proposed": [44, 111, 26, 520, 56, 30, 1573, 157, 121, 4, 6, 25, 79,
                    487, 23, 68, 114, 8, 60, 36, 342, 319, 383, 9, 50, 111],
    "AI_proposed": [47, 103, 24, 516, 50, 53, 1552, 164, 121, 5, 7, 24, 52,
                    511, 21, 64, 110, 5, 54, 21, 342, 182, 317, 5, 53, 103],
    "QC_proposed": [452, 1681, 172, 9655, 495, 445, 50765, 3262, 10282, 35, 56, 206, 673,
                    14115, 141, 550, 1067, 29, 1065, 152, 8995, 8896, 8379, 4, 483, 1681],
}

# --------------------------------------------------
# Create DataFrame
# --------------------------------------------------
df = pd.DataFrame(data)
df.set_index("Benchmark", inplace=True)

# --------------------------------------------------
# Calculate Percentage Improvement
# Positive value  -> Proposed is better (reduction)
# Negative value -> Proposed is worse (increase)
# --------------------------------------------------
metrics = ["GA", "GB", "AI", "QC"]
improvement = pd.DataFrame(index=df.index)

for metric in metrics:
    improvement[metric] = (
        (df[f"{metric}_existing"] - df[f"{metric}_proposed"])
        / df[f"{metric}_existing"] * 100
    )

# Round for display
improvement = improvement.round(1)

# --------------------------------------------------
# Plot Heatmap
# --------------------------------------------------
plt.figure(figsize=(14, 10))

# Use matplotlib's imshow for compatibility
im = plt.imshow(improvement.values, aspect='auto', cmap='RdYlGn')

# Axis labels
plt.xticks(np.arange(len(metrics)), metrics, fontsize=12)
plt.yticks(np.arange(len(improvement.index)), improvement.index, fontsize=10)
plt.xlabel("Design Metrics", fontsize=13)
plt.ylabel("Benchmark Functions", fontsize=13)

# Title
plt.title(
    "Heatmap of Percentage Improvement: Proposed vs Existing RPLA Designs",
    fontsize=14,
    pad=15
)

# Annotate each cell with values
for i in range(improvement.shape[0]):
    for j in range(improvement.shape[1]):
        value = improvement.iloc[i, j]
        plt.text(
            j, i, f"{value:.1f}%",
            ha="center", va="center",
            color="black", fontsize=8
        )

# Colorbar
cbar = plt.colorbar(im)
cbar.set_label("Improvement (%)", fontsize=12)

plt.tight_layout()

# --------------------------------------------------
# Save Figure (Publication Quality)
# --------------------------------------------------
plt.savefig("rpla_heatmap_improvement.png", dpi=600, bbox_inches="tight")
plt.show()
