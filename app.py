"""Flood-to-Action Engine - Tactical Police Operations Dashboard.

Interactive decision support dashboard for Chennai Traffic Police.
Evaluates subway flood risk from 12-hour rainfall forecasts and outputs
operational action sheets, barricade times, and dewatering pump priorities.
"""

from pathlib import Path
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.engine import get_action_sheet, get_pump_table, get_triggers, score
from src.rain import get_forecast
from src.replay import EVENT_OPTIONS, evaluate_event

# ----------------------------------------------------------------------
# Page Setup
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Flood-to-Action Engine | Chennai Traffic Police",
    page_icon="🚨",
    layout="wide",
)

st.title("🚨 Flood-to-Action Engine")
st.caption("Tactical Decision Support for Chennai Traffic Police & Greater Chennai Corporation")

# ----------------------------------------------------------------------
# Sidebar Controls
# ----------------------------------------------------------------------
st.sidebar.header("🕹️ Operation Controls")

mode = st.sidebar.radio("Mode", ["Live", "Replay"])
horizon_h = st.sidebar.slider("Forecast Horizon (Hours)", min_value=1, max_value=12, value=12, step=1)
multiplier = st.sidebar.slider("Rain Multiplier", min_value=0.5, max_value=2.0, value=1.0, step=0.1)

demo_storm = st.sidebar.checkbox(
    "🌧️ Demo Storm (Synthetic Heavy Rain)",
    value=False,
    help="Injects 12h heavy rain storm series so demo functions even on dry days.",
)

# ----------------------------------------------------------------------
# Data Loading & Forecast Preparation
# ----------------------------------------------------------------------
triggers = get_triggers()

if demo_storm:
    # 12-hour synthetic cloudburst curve (peaks at 15 mm/h)
    demo_series = [2.0, 4.0, 8.0, 12.0, 15.0, 12.0, 8.0, 5.0, 3.0, 2.0, 1.0, 0.0]
    now_ts = pd.Timestamp.now(tz="Asia/Kolkata").floor("h")
    time_series = [now_ts + pd.Timedelta(hours=i) for i in range(12)]

    demo_records = []
    for aid in triggers["asset_id"]:
        for ts, p in zip(time_series, demo_series):
            demo_records.append({"asset_id": aid, "ts": ts, "precip_mm": p})
    rain_df = pd.DataFrame(demo_records)
    is_cached = False
    st.sidebar.warning("⚡ Demo Storm active: synthetic 12h rain injected.")
else:
    rain_df, is_cached = get_forecast()
    if is_cached:
        st.sidebar.info("ℹ️ Using cached forecast")

# Score subways
scored_df = score(rain_df, triggers, horizon_h=horizon_h, multiplier=multiplier)

# ----------------------------------------------------------------------
# KPI Highlights Header
# ----------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
red_count = len(scored_df[scored_df["band"] == "red"])
orange_count = len(scored_df[scored_df["band"] == "orange"])
amber_count = len(scored_df[scored_df["band"] == "amber"])
green_count = len(scored_df[scored_df["band"] == "green"])

col1.metric("🔴 Red (Imminent Closure)", red_count)
col2.metric("🟠 Orange (High Risk)", orange_count)
col3.metric("🟡 Amber (Monitor)", amber_count)
col4.metric("🟢 Green (Normal)", green_count)

# ----------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------
tab_map, tab_actions, tab_replay = st.tabs(["🗺️ Live Map", "📋 Action Sheet", "⏪ Replay"])

# ----------------------------------------------------------------------
# TAB 1: Map
# ----------------------------------------------------------------------
with tab_map:
    # Rainfall summary bar chart above map
    st.subheader(f"Next {horizon_h}-Hour Precipitation Trend (Chennai Area Average)")
    chart_rain = (
        rain_df.groupby("ts")["precip_mm"]
        .mean()
        .reset_index()
        .sort_values("ts")
        .iloc[:horizon_h]
    )
    chart_rain["Scaled Rain (mm/h)"] = chart_rain["precip_mm"] * multiplier
    chart_rain["Hour"] = chart_rain["ts"].dt.strftime("%H:%M")
    st.bar_chart(chart_rain.set_index("Hour")["Scaled Rain (mm/h)"], height=160)

    # Folium Interactive Map
    st.subheader("Subway Tactical Status Map")
    chennai_center = [13.06, 80.24]
    m = folium.Map(location=chennai_center, zoom_start=12, tiles="OpenStreetMap")

    band_colors = {
        "red": "#dc3545",
        "orange": "#fd7e14",
        "amber": "#ffc107",
        "green": "#28a745",
    }

    for _, row in scored_df.iterrows():
        lat = row.get("lat")
        lon = row.get("lon")
        if pd.isna(lat) or pd.isna(lon):
            continue

        band = row["band"]
        color = band_colors.get(band, "#6c757d")
        barricade_val = row.get("barricade_by")
        barricade_str = (
            pd.to_datetime(barricade_val).strftime("%H:%M (%d %b)")
            if pd.notna(barricade_val)
            else "Not Required"
        )

        popup_html = f"""
        <div style="font-family: Arial, sans-serif; min-width: 200px; font-size: 13px;">
            <b style="font-size: 14px;">{row['name']}</b><br>
            <hr style="margin: 4px 0;">
            <b>Status:</b> <span style="color:{color}; font-weight:bold;">{band.upper()}</span><br>
            <b>Ratio:</b> {row['ratio']:.2f} (Trigger: {row['trigger']:.1f} mm)<br>
            <b>Peak 3h:</b> {row['peak3h']:.1f} mm<br>
            <b>Barricade By:</b> <span style="color:#d9534f; font-weight:bold;">{barricade_str}</span><br>
            <b>Diversion:</b> {row.get('divert_note', 'N/A')}<br>
            <div style="margin-top:6px; font-size: 11px; color: #555;">{row['why']}</div>
        </div>
        """

        folium.CircleMarker(
            location=[float(lat), float(lon)],
            radius=9,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{row['name']} [{band.upper()}] - Ratio: {row['ratio']:.2f}",
        ).add_to(m)

    st_folium(m, width="100%", height=520, returned_objects=[])

# ----------------------------------------------------------------------
# TAB 2: Action Sheet & Pumps
# ----------------------------------------------------------------------
with tab_actions:
    st.subheader("📋 Police Tactical Action Sheet")
    action_sheet = get_action_sheet(scored_df)

    # Format barricade time for display
    display_sheet = action_sheet.copy()
    display_sheet["barricade_by"] = display_sheet["barricade_by"].apply(
        lambda x: pd.to_datetime(x).strftime("%Y-%m-%d %H:%M") if pd.notna(x) else "-"
    )

    # Styled dataframe
    st.dataframe(
        display_sheet,
        use_container_width=True,
        column_config={
            "asset_id": st.column_config.NumberColumn("ID", width="small"),
            "name": st.column_config.TextColumn("Subway Name", width="medium"),
            "band": st.column_config.TextColumn("Risk Band", width="small"),
            "ratio": st.column_config.NumberColumn("Ratio", format="%.2f"),
            "barricade_by": st.column_config.TextColumn("Barricade By (ETA - 60m)", width="medium"),
            "divert_note": st.column_config.TextColumn("Diversion Note", width="large"),
            "why": st.column_config.TextColumn("Decision Rationale", width="large"),
        },
    )

    csv_data = display_sheet.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Action Sheet (CSV)",
        data=csv_data,
        file_name="chennai_police_action_sheet.csv",
        mime="text/csv",
    )

    st.markdown("---")
    st.subheader("🚰 Municipal Dewatering Pump Allocation")
    pump_table = get_pump_table(scored_df, total_pumps=10)
    st.dataframe(
        pump_table,
        use_container_width=True,
        column_config={
            "asset_id": st.column_config.NumberColumn("ID", width="small"),
            "name": st.column_config.TextColumn("Subway Name", width="medium"),
            "band": st.column_config.TextColumn("Risk Band", width="small"),
            "ratio": st.column_config.NumberColumn("Risk Ratio", format="%.2f"),
            "pumps_assigned": st.column_config.NumberColumn("Pumps Assigned", width="small"),
            "maintained_by": st.column_config.TextColumn("Maintained By", width="medium"),
        },
    )

# ----------------------------------------------------------------------
# TAB 3: Replay
# ----------------------------------------------------------------------
with tab_replay:
    st.subheader("⏪ Historical Storm Replay Evaluation")

    event_keys = list(EVENT_OPTIONS.keys())
    selected_event = st.selectbox(
        "Select Historical Event",
        options=event_keys,
        format_func=lambda x: f"{x} ({EVENT_OPTIONS[x]})",
        index=1,
    )

    eval_res = evaluate_event(selected_event)

    # Metrics
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric(
        "🎯 Recall",
        f"{eval_res['recall'] * 100:.0f}%",
        f"{eval_res['matched_count']} of {eval_res['actual_count']} closed subways",
    )
    m_col2.metric(
        "🔍 Precision",
        f"{eval_res['precision'] * 100:.0f}%",
        f"{eval_res['matched_count']} of {eval_res['predicted_count']} predicted alerts",
    )
    m_col3.metric(
        "⚠️ False Alarms",
        eval_res["false_alarms"],
        "Predicted orange/red but not closed",
    )

    st.markdown("---")

    # Side-by-side lists
    col_pred, col_act = st.columns(2)

    with col_pred:
        st.markdown(f"#### 🚨 Predicted (Orange/Red) — {eval_res['predicted_count']}")
        if eval_res["predicted_items"]:
            for item in eval_res["predicted_items"]:
                st.write(item["display"])
        else:
            st.info("No subways reached Orange/Red threshold.")

    with col_act:
        st.markdown(f"#### 🚧 Actually Closed/Restricted — {eval_res['actual_count']}")
        if eval_res["actual_items"]:
            for item in eval_res["actual_items"]:
                st.write(item["display"])
        else:
            st.info("No subways were recorded as closed/restricted.")

    st.markdown("---")
    st.caption("Replay uses reanalysis-style rain and only 4 labelled events; indicative, not a validation.")

# ----------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------
st.markdown("---")
st.caption("Weather data by Open-Meteo.com | Flood-to-Action Engine Prototype")
