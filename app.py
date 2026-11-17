"""
Interactive what-if app.  Run:  streamlit run app.py
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from capacity import load_data, optimize_plan, summarize  # noqa: E402

st.set_page_config(page_title="Plant Capacity Planner", layout="wide")
st.title("Plant Capacity Planner")
st.caption("Can the plant deliver the commercial plan? Fictional dairy plant data.")

data = load_data()

with st.sidebar:
    st.header("Scenario")
    growth = st.slider("Demand growth vs. forecast", -20, 40, 0, step=5, format="%d%%") / 100
    use_oee = st.checkbox("Override OEE for all lines")
    oee = st.slider("OEE", 0.50, 0.95, 0.75, step=0.01) if use_oee else None
    st.subheader("Add a shift")
    extra = {l: 1 for l in data["lines"]["line_id"]
             if st.checkbox(f"+1 shift on {l}", key=l)}

result = optimize_plan(data, demand_growth=growth, extra_shifts=extra, oee_override=oee)
s = summarize(result)

c1, c2, c3 = st.columns(3)
c1.metric("Service level", f"{s['service_level_pct']}%")
c2.metric("Unmet demand", f"{s['unmet_kg']:,.0f} kg")
c3.metric("Bottleneck line", s["bottleneck_line"])

st.subheader("Utilization % by line and month")
st.dataframe(s["utilization_pct"].sort_index().style.background_gradient(
    cmap="RdYlGn_r", vmin=50, vmax=100).format("{:.0f}"), width="stretch")

left, right = st.columns(2)
with left:
    st.subheader("Unmet demand by product (kg)")
    st.bar_chart(s["unmet_by_sku"])
with right:
    st.subheader("Extra kg served per +1 hour (shadow price)")
    st.bar_chart(s["value_extra_hour"])
    st.subheader("Available hours per line / month")
    st.dataframe(result["lines"][["line_id", "name", "shifts_per_day", "oee", "available_hrs"]],
                 hide_index=True, width="stretch")

with st.expander("Production plan (kg by line, product, month)"):
    plan = result["plan"].pivot_table(index=["line_id", "sku"], columns="month",
                                      values="kg", aggfunc="sum", fill_value=0)
    st.dataframe(plan.round(0), width="stretch")
