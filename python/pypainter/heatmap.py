import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

df = pd.DataFrame(data)

def safe_improve(e, p):
    return np.where(e != 0, (e - p) / e * 100, 0)

improvements = pd.DataFrame({
    "GA": safe_improve(df["GA_existing"], df["GA_proposed"]),
    "GB": safe_improve(df["GB_existing"], df["GB_proposed"]),
    "AI": safe_improve(df["AI_existing"], df["AI_proposed"]),
    "QC": safe_improve(df["QC_existing"], df["QC_proposed"]),
}, index=df["Benchmark"])

# Heatmap
plt.figure(figsize=(12, 8))
plt.imshow(improvements.values, aspect='auto')
plt.colorbar(label="Improvement (%)")

plt.xticks(range(4), improvements.columns)
plt.yticks(range(len(improvements.index)), improvements.index)

plt.title("RPLA Improvement Heatmap (Proposed vs Existing)")

# annotations
for i in range(improvements.shape[0]):
    for j in range(improvements.shape[1]):
        plt.text(j, i, f"{improvements.iloc[i, j]:.1f}",
                 ha='center', va='center', fontsize=7)

plt.tight_layout()

os.makedirs("figures", exist_ok=True)
plt.savefig("figures/rpla_heatmap.png", dpi=300, bbox_inches='tight')
plt.show()
