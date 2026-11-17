"""
Generates FICTIONAL data for a dairy (cheese) plant.
No real company data is used. Run once:  python data/generate_data.py
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)
OUT = Path(__file__).parent

# --- Production lines -------------------------------------------------------
lines = pd.DataFrame([
    # line_id, name,               shifts/day, hours/shift, days/month, OEE, planned maintenance hrs/month
    ["L1", "Fresh cheese line",     3, 8, 26, 0.78, 24],
    ["L2", "Pasta filata line",     2, 8, 26, 0.72, 16],
    ["L3", "Aged cheese line",      2, 8, 24, 0.80, 16],
    ["L4", "Multi-purpose line",    2, 8, 26, 0.70, 20],
], columns=["line_id", "name", "shifts_per_day", "hours_per_shift",
            "days_per_month", "oee", "maintenance_hrs"])

# --- Products (SKU families) ------------------------------------------------
products = pd.DataFrame([
    ["FRESCO", "Queso fresco",   1_050_000],
    ["PANELA", "Queso panela",     900_000],
    ["OAXACA", "Queso Oaxaca",     560_000],
    ["MANCH",  "Manchego-style",   280_000],
    ["CREMA",  "Cream cheese",     170_000],
], columns=["sku", "description", "base_monthly_kg"])

# --- Which line can make which product, and how fast (kg per hour) ----------
line_product = pd.DataFrame([
    ["L1", "FRESCO", 4200], ["L1", "PANELA", 3900],
    ["L2", "OAXACA", 2400],
    ["L3", "MANCH",  1300], ["L3", "PANELA", 3000],
    ["L4", "FRESCO", 3200], ["L4", "OAXACA", 1800], ["L4", "CREMA", 1500],
], columns=["line_id", "sku", "rate_kg_hr"])

# --- 12-month demand forecast with seasonality + growth --------------------
months = pd.period_range("2027-01", periods=12, freq="M")
# Higher demand around Lent (Mar-Apr) and December
seasonality = np.array([0.95, 1.00, 1.12, 1.10, 0.98, 0.95,
                        0.93, 0.96, 1.00, 1.03, 1.05, 1.15])
growth = {"FRESCO": 0.04, "PANELA": 0.06, "OAXACA": 0.10, "MANCH": 0.03, "CREMA": 0.12}

rows = []
for _, p in products.iterrows():
    for i, m in enumerate(months):
        trend = (1 + growth[p.sku]) ** (i / 12)
        noise = rng.normal(1, 0.03)
        rows.append([str(m), p.sku, round(p.base_monthly_kg * seasonality[i] * trend * noise)])
demand = pd.DataFrame(rows, columns=["month", "sku", "demand_kg"])

for name, df in {"lines": lines, "products": products,
                 "line_product": line_product, "demand": demand}.items():
    df.to_csv(OUT / f"{name}.csv", index=False)
    print(f"saved data/{name}.csv  ({len(df)} rows)")
