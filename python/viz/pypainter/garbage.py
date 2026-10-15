import matplotlib.pyplot as plt

# Benchmark names
benchmarks = [
    "5xp1","9sym","alu3","apex3","b12","bw","cordic","duke2","e64","in5","misex1","misex2","pdc","rd53","rd73","rd84","sao2","t481", "table3","table5","vg2","xor5","z5xp1","z9sym"
]

# Garbage Outputs (GB)
GB_existing = [276,896,285,4113,163,230,18233,1059,2145,856,78,195,4076,156,876,2044,491,4766,4004,3674,821,84,274,896]
GB_proposed = [82,252,120,1181,53,17,3625,442,1366,124,20,74,459,49,176,392,228,674,1538,966,244,24,75,252]

plt.figure(figsize=(12, 6))
plt.plot(benchmarks, GB_existing, marker='o', linestyle='-', color='green', label='Existing GB')
plt.plot(benchmarks, GB_proposed, marker='s', linestyle='--', color='orange', label='Proposed GB')

plt.title("Line-Based Comparison of Garbage Outputs (GB)")
plt.xlabel("Benchmark Circuits")
plt.ylabel("Garbage Outputs (GB)")
plt.xticks(rotation=60)
plt.legend()
plt.grid(True, linestyle='--', linewidth=0.5)
plt.tight_layout()

plt.savefig("rpla_line_comparison_GB.png", dpi=300)
plt.show()
