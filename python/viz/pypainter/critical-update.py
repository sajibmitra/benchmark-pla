# critical_line_chart_rpla.py
import matplotlib.pyplot as plt
import numpy as np

# --------------------------------------------------
# Benchmark Data: Existing vs Proposed
# --------------------------------------------------
benchmarks = [
    "5xp1", "9sym", "adr3", "apex3", "b12", "bw", "cordic",
    "duke2", "e64", "inc4", "inc5", "misex1", "misex2",
    "pdc", "rd53", "rd73", "rd84", "sasao", "sao2",
    "t481", "table3", "table5", "vag2", "xor5", "z5xp1", "z9sym"
]

# Existing values
GA_existing = [166, 427, 67, 3998, 159, 305, 12162, 941, 2170, 17, 25, 88, 199,
               3801, 56, 187, 328, 14, 284, 49, 2602, 2539, 2018, 8, 167, 427]
GB_existing = [112, 385, 48, 1799, 132, 64, 10640, 667, 2148, 11, 18, 51, 176,
               3006, 42, 141, 265, 13, 236, 53, 1814, 1819, 1836, 8, 114, 385]
AI_existing = [115, 377, 46, 1795, 126, 87, 10661, 674, 2148, 12, 19, 50, 167,
               3026, 40, 137, 261, 10, 230, 38, 1811, 1682, 1770, 4, 117, 377]
QC_existing = [418, 1405, 157, 8654, 453, 446, 41694, 2735, 8410, 35, 55, 193, 622,
               12096, 134, 487, 928, 29, 890, 133, 7537, 7516, 6926, 8, 425, 1405]

# Proposed values
GA_proposed = [94, 227, 46, 3066, 80, 270, 5257, 612, 1340, 11, 16, 56, 87,
               1255, 37, 107, 186, 9, 166, 26, 1618, 1357, 1029, 4, 117, 227]
GB_proposed = [35, 184, 25, 867, 52, 28, 3734, 337, 1317, 2, 5, 19, 63,
               459, 22, 60, 121, 6, 117, 29, 830, 637, 847, 4, 58, 184]
AI_proposed = [43, 176, 25, 863, 46, 52, 3713, 345, 1318, 6, 10, 18, 56,
               484, 21, 57, 119, 5, 112, 14, 830, 635, 830, 0, 66, 176]
QC_proposed = [262, 931, 142, 6346, 256, 374, 20105, 1920, 6588, 35, 56, 108, 279,
               3083, 121, 331, 658, 29, 606, 82, 4890, 3841, 4345, 4, 369, 931]

# --------------------------------------------------
# Plot Configuration
# --------------------------------------------------
metrics = [
    ("Total Gates (GA)", GA_existing, GA_proposed),
    ("Garbage Outputs (GB)", GB_existing, GB_proposed),
    ("Ancilla Inputs (AI)", AI_existing, AI_proposed),
    ("Quantum Cost (QC)", QC_existing, QC_proposed),
]

# Color scheme suitable for publication
existing_color = "#1f77b4"   # Blue
proposed_color = "#d62728"   # Red

# Create 2x2 subplot layout
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle(
    "Benchmark Analysis of Proposed vs Existing RPLA Designs",
    fontsize=16,
    fontweight="bold"
)

axes = axes.flatten()
x = np.arange(len(benchmarks))

for ax, (title, existing, proposed) in zip(axes, metrics):
    ax.plot(
        x, existing,
        marker='o',
        linestyle='-',
        linewidth=2,
        markersize=5,
        color=existing_color,
        label="Existing"
    )
    ax.plot(
        x, proposed,
        marker='s',
        linestyle='--',
        linewidth=2,
        markersize=5,
        color=proposed_color,
        label="Proposed"
    )

    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(benchmarks, rotation=45, ha='right')
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.set_ylabel("Value")

# Shared legend
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='upper center', ncol=2, frameon=False)

plt.tight_layout(rect=[0, 0, 1, 0.95])

# Save high-resolution figure
plt.savefig("rpla_critical_line_chart.png", dpi=600, bbox_inches="tight")
plt.savefig("rpla_critical_line_chart.pdf", bbox_inches="tight")

plt.show()
