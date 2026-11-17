"""
Runs 3 demand scenarios and saves charts + a summary table to outputs/.
Usage:  python run.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))
from capacity import load_data, optimize_plan, summarize  # noqa: E402

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

data = load_data()
scenarios = {
    "Base plan": dict(demand_growth=0.00),
    "Growth +20%": dict(demand_growth=0.20),
    "Growth +20% + 3rd shift on L2": dict(demand_growth=0.20, extra_shifts={"L2": 1}),
    "Growth +20% + 3rd shift on L3": dict(demand_growth=0.20, extra_shifts={"L3": 1}),
}

rows = []
for name, params in scenarios.items():
    s = summarize(optimize_plan(data, **params))
    rows.append({"scenario": name,
                 "service_level_%": s["service_level_pct"],
                 "unmet_kg": s["unmet_kg"],
                 "bottleneck": s["bottleneck_line"],
                 "kg_gained_per_extra_hr": s["value_extra_hour"].max(),
                 **{f"util_{k}_%": v for k, v in s["avg_utilization"].sort_index().items()}})

    # Heatmap: utilization by line and month
    util = s["utilization_pct"].sort_index()
    fig, ax = plt.subplots(figsize=(10, 3))
    im = ax.imshow(util.values, cmap="RdYlGn_r", vmin=50, vmax=100, aspect="auto")
    ax.set_xticks(range(len(util.columns)), [m[-2:] for m in util.columns])
    ax.set_yticks(range(len(util.index)), util.index)
    for i in range(util.shape[0]):
        for j in range(util.shape[1]):
            ax.text(j, i, f"{util.values[i, j]:.0f}", ha="center", va="center", fontsize=8)
    ax.set_title(f"Line utilization % by month: {name}")
    ax.set_xlabel("Month (2027)")
    fig.colorbar(im, ax=ax, label="%")
    fig.tight_layout()
    fname = name.lower().replace(" ", "_").replace("%", "pct").replace("+", "plus")
    fig.savefig(OUT / f"heatmap_{fname}.png", dpi=150)
    plt.close(fig)

summary = pd.DataFrame(rows)
summary.to_csv(OUT / "scenario_summary.csv", index=False)
print(summary.to_string(index=False))
print(f"\nCharts saved to {OUT}/")
