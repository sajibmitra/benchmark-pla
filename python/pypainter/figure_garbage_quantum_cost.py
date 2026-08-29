from pathlib import Path

import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent / "images"
OUT.mkdir(parents=True, exist_ok=True)

# Benchmark names
benchmarks = [
    "5xp1","9sym","alu3","apex3","b12","bw","cordic","duke2","e64","in5","misex1","misex2","pdc","rd53","rd73","rd84","sao2","t481", "table3","table5","vg2","xor5","z5xp1","z9sym"
]

# Existing values
# GA_existing = [343,1035,343,4704,201,341,19390,1238,2145,1007,103,199,4510,186,1016,2330,555,5231,4524,4208,906,95,341,1035]
GB_existing = [276,896,285,4113,163,230,18233,1059,2145,856,78,195,4076,156,876,2044,491,4766,4004,3674,821,84,274,896]
# AI_existing = [279,888,283,4109,157,253,18212,1066,2145,846,77,188,4100,154,872,2040,485,4751,4004,3672,804,80,277,888]
QC_existing = [979,3255,991,15372,531,893,70489,4079,8385,3260,274,676,15763,549,3203,7571,1788,18044,15435,14282,2988,287,965,3255]
# Proposed values
# GA_proposed = [150,391,180,1772,94,129,4782,621,1367,275,45,78,893,79,316,678,292,1139,2058,1500,329,35,143,391]
GB_proposed = [82,252,120,1181,53,17,3625,442,1366,124,20,74,459,49,176,392,228,674,1538,966,244,24,75,252]
# AI_proposed = [86,244,120,1177,50,41,3604,449,1367,114,19,67,483,47,172,388,222,659,1538,964,227,20,79,244]
QC_proposed = [494,1367,660,6444,290,253,19198,2385,6835,699,113,346,2809,267,1004,2230,1180,3775,8186,5328,1237,115,459,1367]

plt.figure(figsize=(14, 7))

# Plot lines

plt.plot(benchmarks, GB_existing, marker='s', linestyle='-', label='GB Existing')
plt.plot(benchmarks, GB_proposed, marker='s', linestyle='--', label='GB Proposed')


plt.plot(benchmarks, QC_existing, marker='^', linestyle='-', label='QC Existing')
plt.plot(benchmarks, QC_proposed, marker='^', linestyle='--', label='QC Proposed')

plt.title('Comparison of GB and QC for Proposed vs Existing RPLA Designs')
plt.xlabel('Benchmark Functions')
plt.ylabel('Count')
plt.xticks(rotation=90)
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(OUT / "garbage_quantum_cost.pdf", bbox_inches="tight", pad_inches=0.06)
plt.savefig(OUT / "garbage_quantum_cost.png", dpi=300, bbox_inches="tight", pad_inches=0.06)
plt.show()
