"""
Plant capacity planning model.

Step 1  available_hours()  -> how many productive hours each line has per month
Step 2  optimize_plan()    -> linear program that assigns demand to lines
                              to minimize unmet demand, then production hours
Step 3  summarize()        -> utilization per line, bottlenecks, capacity gap
"""
import pandas as pd
import pulp
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def load_data(data_dir: Path = DATA) -> dict:
    return {name: pd.read_csv(data_dir / f"{name}.csv")
            for name in ["lines", "products", "line_product", "demand"]}


def available_hours(lines: pd.DataFrame, extra_shifts: dict | None = None,
                    oee_override: float | None = None) -> pd.DataFrame:
    """Productive hours per line per month = (calendar hours - maintenance) x OEE."""
    df = lines.copy()
    if extra_shifts:
        df["shifts_per_day"] += df["line_id"].map(extra_shifts).fillna(0)
    df["shifts_per_day"] = df["shifts_per_day"].clip(upper=3)  # max 3 shifts of 8h
    if oee_override is not None:
        df["oee"] = oee_override
    gross = df["shifts_per_day"] * df["hours_per_shift"] * df["days_per_month"]
    df["available_hrs"] = ((gross - df["maintenance_hrs"]) * df["oee"]).round(1)
    return df


def optimize_plan(data: dict, demand_growth: float = 0.0,
                  extra_shifts: dict | None = None,
                  oee_override: float | None = None) -> dict:
    """
    Decision variable: kg of product p made on line l in month m.
    Objective: (1) minimize unmet demand, (2) then minimize total line hours.
    """
    lines = available_hours(data["lines"], extra_shifts, oee_override)
    lp_rates = data["line_product"]
    demand = data["demand"].copy()
    demand["demand_kg"] = demand["demand_kg"] * (1 + demand_growth)

    months = sorted(demand["month"].unique())
    cap = {k: float(v) for k, v in lines.set_index("line_id")["available_hrs"].items()}
    rate = {(r.line_id, r.sku): float(r.rate_kg_hr) for r in lp_rates.itertuples()}
    dem = {(r.month, r.sku): float(r.demand_kg) for r in demand.itertuples()}

    prob = pulp.LpProblem("capacity_plan", pulp.LpMinimize)
    x = {(l, p, m): pulp.LpVariable(f"x_{l}_{p}_{m}", lowBound=0)
         for (l, p) in rate for m in months}
    short = {(m, p): pulp.LpVariable(f"short_{m}_{p}", lowBound=0) for (m, p) in dem}

    hours = pulp.lpSum((1 / rate[l, p]) * x[l, p, m] for (l, p, m) in x)
    prob += 1000 * pulp.lpSum(short.values()) + hours  # big penalty on unmet demand

    for (m, p), d in dem.items():  # meet demand or record shortage
        prob += pulp.lpSum(x[l, pp, mm] for (l, pp, mm) in x if pp == p and mm == m) + short[m, p] == d
    cap_cons = {}
    for l in cap:  # line hours cannot exceed available hours
        for m in months:
            cap_cons[l, m] = pulp.lpSum((1 / rate[ll, p]) * x[ll, p, mm] for (ll, p, mm) in x
                               if ll == l and mm == m) <= cap[l]
            prob += cap_cons[l, m], f"cap_{l}_{m.replace('-', '_')}"

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    plan = pd.DataFrame([{"line_id": l, "sku": p, "month": m, "kg": v.value(),
                          "hours": v.value() / rate[l, p]}
                         for (l, p, m), v in x.items() if v.value() > 1e-6])
    shortage = pd.DataFrame([{"month": m, "sku": p, "unmet_kg": v.value()}
                             for (m, p), v in short.items()])
    # Shadow price (dual value) of each capacity constraint: how much unmet demand
    # drops if a line gets 1 extra hour. Divided by the 1000 penalty and summed over
    # months, it reads as "extra kg served in the year with +1 hour per month".
    # It can point to a line that is NOT the obvious one, because lines share products.
    shadow = pd.Series({l: sum(-prob.constraints[f"cap_{l}_{m.replace('-', '_')}"].pi for m in months) / 1000
                        for l in cap}, name="kg_served_per_extra_hour").round(0)
    return {"plan": plan, "shortage": shortage, "lines": lines, "shadow": shadow,
            "demand": demand, "status": pulp.LpStatus[prob.status]}


def summarize(result: dict) -> dict:
    plan, lines = result["plan"], result["lines"]
    used = plan.groupby(["line_id", "month"])["hours"].sum().unstack(fill_value=0)
    util = (used.div(lines.set_index("line_id")["available_hrs"], axis=0) * 100).round(1)

    shortage = result["shortage"]
    total_demand = result["demand"]["demand_kg"].sum()
    unmet = shortage["unmet_kg"].sum()
    return {
        "utilization_pct": util,                                   # line x month
        "avg_utilization": util.mean(axis=1).round(1).sort_values(ascending=False),
        # True bottleneck = line where an extra hour serves the most unmet demand
        "bottleneck_line": (result["shadow"].idxmax() if result["shadow"].max() > 0
                            else "None (all demand met)"),
        "value_extra_hour": result["shadow"].sort_values(ascending=False),
        "unmet_by_sku": shortage.groupby("sku")["unmet_kg"].sum().round(0),
        "service_level_pct": round(100 * (1 - unmet / total_demand), 2),
        "unmet_kg": round(unmet),
    }
