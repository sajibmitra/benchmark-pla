import numpy as np
import matplotlib.pyplot as plt

# -----------------------------
# Benchmark data (Existing vs Proposed)
# -----------------------------
benchmarks = [
    "5xp1", "9sym", "adr3", "apex3", "b12", "bw", "cordic",
    "duke2", "e64", "inc4"
]

GA_existing = [166, 427, 67, 3998, 159, 305, 12162, 941, 2170, 16]
GA_proposed = [132, 377, 52, 3719, 127, 281, 11389, 874, 2074, 11]

GB_existing = [112, 385, 48, 1799, 132, 64, 10640, 667, 2148, 10]
GB_proposed = [44, 111, 26, 520, 56, 30, 1573, 157, 121, 4]

AI_existing = [115, 377, 46, 1795, 167, 87, 10661, 674, 2148, 11]
AI_proposed = [47, 103, 24, 516, 50, 53, 1552, 164, 121, 5]

QC_existing = [418, 1405, 157, 8654, 453, 446, 41694, 2735, 8410, 34]
QC_proposed = [452, 1681, 172, 9655, 495, 445, 50765, 3262, 10282, 35]

x = np.arange(len(benchmarks))
width = 0.38

# -----------------------------
# Create subplots (2x2)
# -----------------------------
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle("ICCAD 2026: Proposed vs Existing RPLA Design Comparison", fontsize=14)

def plot_metric(ax, existing, proposed, title):
    ax.bar(x - width/2, existing, width, label="Existing", color="gray")
    ax.bar(x + width/2, proposed, width, label="Proposed", color="black")

    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(benchmarks, rotation=45, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

# -----------------------------
# Individual plots
# -----------------------------
plot_metric(axes[0, 0], GA_existing, GA_proposed, "Total Gates (GA)")
plot_metric(axes[0, 1], GB_existing, GB_proposed, "Garbage Outputs (GB)")
plot_metric(axes[1, 0], AI_existing, AI_proposed, "Ancilla Inputs (AI)")
plot_metric(axes[1, 1], QC_existing, QC_proposed, "Quantum Cost (QC)")

# -----------------------------
# Shared legend
# -----------------------------
handles, labels = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=2)

plt.tight_layout(rect=[0, 0, 1, 0.95])

# Save publication-quality figure
plt.savefig("iccad_rpla_comparison.png", dpi=600, bbox_inches="tight")

plt.show()
