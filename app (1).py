import pandas as pd
import streamlit as st
from clash_logic import (DAY_ORDER, explain_clash, find_clashes, free_slots,
                         load_timetable, suggest_fix, to_minutes, weekly_grid)

RED = "background-color:#ffd6d6;color:#111111"  # dark text so it is readable in dark theme

st.set_page_config(page_title="Timetable Clash Detector", page_icon="📅", layout="wide")
st.title("📅 Timetable Clash Detector")
st.caption("Upload a timetable (CSV/Excel) with columns: "
           "day, start, end, subject, faculty, room, class_group")

with st.sidebar:
    st.header("Settings")
    uploaded = st.file_uploader("Timetable file", type=["csv", "xlsx"])
    use_sample = st.checkbox("Use sample data", value=uploaded is None)
    day_start = st.text_input("College starts", "09:00")
    day_end = st.text_input("College ends", "17:00")

source = uploaded if uploaded is not None else ("sample_timetable.csv" if use_sample else None)
if source is None:
    st.info("Upload a file or tick 'Use sample data'.")
    st.stop()

try:
    df = load_timetable(source)
    ds, de = to_minutes(day_start), to_minutes(day_end)
except Exception as e:
    st.error(f"Could not read timetable: {e}")
    st.stop()

clashes = find_clashes(df)
bad_rows = set(clashes.row_1) | set(clashes.row_2) if len(clashes) else set()

c1, c2, c3 = st.columns(3)
c1.metric("Sessions", len(df))
c2.metric("Clashes", len(clashes))
c3.metric("Sessions affected", len(bad_rows))

st.subheader("Clashes")
if clashes.empty:
    st.success("No clashes found. 🎉")
else:
    out = clashes.copy()
    out["explanation"] = [explain_clash(df, c) for _, c in clashes.iterrows()]
    out["suggestion"] = [suggest_fix(df, c) for _, c in clashes.iterrows()]
    show = out.drop(columns=["row_1", "row_2"])
    st.dataframe(show.style.apply(lambda r: [RED] * len(r), axis=1),
                 use_container_width=True, hide_index=True)
    st.download_button("Download clash report (CSV)", show.to_csv(index=False),
                       "clash_report.csv", "text/csv")

tab_day, tab_week = st.tabs(["Day view", "Weekly grid"])

with tab_day:
    days = [d for d in DAY_ORDER if d in set(df.day)] or sorted(df.day.unique())
    day = st.selectbox("Day", days)
    view = df[df.day == day].sort_values("start_min")
    view_disp = view[["start", "end", "subject", "faculty", "room", "class_group"]]
    st.dataframe(view_disp.style.apply(
        lambda r: [RED if r.name in bad_rows else ""] * len(r), axis=1),
        use_container_width=True)

with tab_week:
    f_col = st.selectbox("Filter by", ["All", "class_group", "faculty", "room"])
    sub = df
    if f_col != "All":
        val = st.selectbox("Select", sorted(df[f_col].unique()), key="grid_val")
        sub = df[df[f_col] == val]
    grid, flags = weekly_grid(sub, bad_rows, ds, de)
    st.dataframe(grid.style.apply(
        lambda _: flags.map(lambda x: RED if x else ""), axis=None),
        use_container_width=True)
    st.caption("Red cells contain a clash. Clash flags use the full timetable.")

st.subheader("Free slots")
col = st.radio("Check by", ["room", "faculty", "class_group"], horizontal=True)
value = st.selectbox("Select", sorted(df[col].unique()), key="free_val")
fday = st.selectbox("Day", days, key="free_day")
slots = free_slots(df, col, value, fday, ds, de)
st.write(f"**{value}** is free on {fday}: " + (", ".join(slots) if slots else "no free slots (1h+)"))
