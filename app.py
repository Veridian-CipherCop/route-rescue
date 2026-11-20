"""Flood-to-Action Engine - Tactical Police Operations Dashboard.

Interactive decision support dashboard for Chennai Traffic Police.
Evaluates subway flood risk from 12-hour rainfall forecasts and outputs
operational action sheets, barricade times, and dewatering pump priorities.
"""

import base64
from pathlib import Path
import random
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.engine import get_action_sheet, get_pump_table, get_triggers, score
from src.rain import get_forecast
from src.replay import EVENT_OPTIONS, evaluate_event

# ----------------------------------------------------------------------
# Page Setup & Styling
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Flood-to-Action Engine | Chennai Traffic Police",
    page_icon="🚨",
    layout="wide",
)

# Background styling from assets/img.png (graceful fallback if missing)
img_path = Path(__file__).resolve().parent / "assets" / "img.png"
if img_path.exists():
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    bg_style = f"""
    background-image: linear-gradient(rgba(5, 10, 20, 0.25), rgba(5, 10, 20, 0.25)), url("data:image/png;base64,{img_b64}");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    """
else:
    bg_style = "background-color: #080c14;"

# Generate ~80 pure CSS rain drops with random inline positions & timing
drops_html = []
random.seed(42)  # Stable positions across reruns
for _ in range(80):
    left = random.randint(0, 100)
    delay = round(random.uniform(0.0, 5.0), 2)
    duration = round(random.uniform(0.6, 1.2), 2)
    height = random.randint(25, 60)
    opacity = round(random.uniform(0.25, 0.60), 2)
    drops_html.append(
        f'<div class="drop" style="left:{left}%; animation-delay:{delay}s; animation-duration:{duration}s; height:{height}px; opacity:{opacity};"></div>'
    )
rain_html = f'<div class="rain">{"".join(drops_html)}</div>'

custom_css = f"""
<style>
/* Full page background with light overlay */
.stApp {{
    {bg_style}
}}

/* Transparent header */
header[data-testid="stHeader"] {{
    background: transparent !important;
}}

/* Remove big dark panel behind the whole page */
.block-container,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main {{
    background: transparent !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    border: none !important;
    box-shadow: none !important;
}}

/* Sidebar: official government console look */
section[data-testid="stSidebar"],
[data-testid="stSidebar"] > div:first-child {{
    background: linear-gradient(180deg, rgba(11, 37, 69, 0.92), rgba(19, 49, 92, 0.88)) !important;
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
    border-right: 3px solid #FF9933 !important;
}}

/* Sidebar glass cards */
.sidebar-glass-card-title {{
    font-size: 11px !important;
    font-weight: 800 !important;
    letter-spacing: 1.2px !important;
    color: #FF9933 !important;
    text-transform: uppercase !important;
    margin-bottom: 8px !important;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: rgba(255, 255, 255, 0.08) !important;
    border: 1px solid rgba(255, 255, 255, 0.18) !important;
    border-radius: 14px !important;
    padding: 14px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18) !important;
}}

/* Saffron accent for inputs */
div[data-testid="stSlider"] div[data-baseweb="slider"] div[role="slider"] {{
    background-color: #FF9933 !important;
    border-color: #FF9933 !important;
    box-shadow: 0 0 10px rgba(255, 153, 51, 0.6) !important;
}}
div[data-testid="stRadio"] [role="radio"][aria-checked="true"] {{
    background-color: #FF9933 !important;
    border-color: #FF9933 !important;
}}
div[data-testid="stCheckbox"] input:checked + div {{
    background-color: #FF9933 !important;
    border-color: #FF9933 !important;
}}

/* Sidebar labels */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] label p,
section[data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p {{
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 0.5px !important;
}}

/* General text readability over photo */
h1, h2, h3, h4, h5, h6, p, span, label, div {{
    color: #ffffff;
    text-shadow: 0 1px 4px rgba(0, 0, 0, 0.9);
}}

/* Remove any background color/highlight on title, subtitle, and metric labels */
h1, h2, h3, h4, .stCaption, small,
div[data-testid="stMetricLabel"],
div[data-testid="stMetricValue"],
div[data-testid="stMetricDelta"] {{
    background: transparent !important;
    background-color: transparent !important;
}}

/* Small widgets get semi-transparent dark card */
div[data-testid="stMetric"] {{
    background: rgba(8, 12, 20, 0.55) !important;
    backdrop-filter: blur(4px) !important;
    -webkit-backdrop-filter: blur(4px) !important;
    border-radius: 12px !important;
    padding: 12px 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
}}

div[data-testid="stDataFrame"] {{
    background: rgba(8, 12, 20, 0.55) !important;
    backdrop-filter: blur(4px) !important;
    -webkit-backdrop-filter: blur(4px) !important;
    border-radius: 12px !important;
    padding: 8px !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}}

div[data-testid="stAlert"] {{
    background: rgba(8, 12, 20, 0.55) !important;
    backdrop-filter: blur(4px) !important;
    -webkit-backdrop-filter: blur(4px) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
}}

div[data-baseweb="tab-list"] {{
    background: rgba(8, 12, 20, 0.55) !important;
    backdrop-filter: blur(4px) !important;
    -webkit-backdrop-filter: blur(4px) !important;
    border-radius: 12px !important;
    padding: 4px 8px !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}}

button[data-baseweb="tab"] {{
    color: #e2e8f0 !important;
    background: transparent !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: #FF9933 !important;
    border-bottom-color: #FF9933 !important;
}}

/* Falling rain animation (pointer-events: none ensures non-blocking clicks) */
.rain {{
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 999;
    overflow: hidden;
}}

.drop {{
    position: absolute;
    top: -80px;
    width: 2px;
    background: linear-gradient(to bottom, rgba(255, 255, 255, 0), rgba(190, 220, 255, 0.8));
    border-radius: 2px;
    animation: fall linear infinite;
}}

@keyframes fall {{
    to {{
        transform: translateY(110vh);
    }}
}}
</style>
"""

st.markdown(custom_css + rain_html, unsafe_allow_html=True)

st.title("🚨 Flood-to-Action Engine")
st.caption("Chennai subway flood risk, ranked police action sheet")

# ----------------------------------------------------------------------
# Sidebar Controls (Control Room Console)
# ----------------------------------------------------------------------
st.sidebar.markdown("""
<div style="background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.18); border-radius: 14px; padding: 14px; margin-bottom: 14px; box-shadow: 0 4px 15px rgba(0,0,0,0.25);">
    <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 22px;">🛡️ 🚨</span>
        <span style="font-size: 16px; font-weight: 800; letter-spacing: 1.5px; color: #ffffff;">CONTROL ROOM</span>
    </div>
    <div style="font-size: 11px; color: #e2e8f0; margin-top: 4px; font-weight: 500;">Greater Chennai Traffic Police - Advisory Console</div>
    <div style="height: 2px; background: #FF9933; margin-top: 10px; border-radius: 2px;"></div>
</div>
""", unsafe_allow_html=True)

with st.sidebar.container(border=True):
    st.markdown('<div class="sidebar-glass-card-title">DATA MODE</div>', unsafe_allow_html=True)
    mode = st.radio("Mode", ["Live", "Replay"], label_visibility="collapsed")

with st.sidebar.container(border=True):
    st.markdown('<div class="sidebar-glass-card-title">FORECAST SETTINGS</div>', unsafe_allow_html=True)
    horizon_h = st.slider("Forecast Horizon (Hours)", min_value=1, max_value=12, value=12, step=1)
    multiplier = st.slider("Rain Multiplier", min_value=0.5, max_value=2.0, value=1.0, step=0.1)

with st.sidebar.container(border=True):
    st.markdown('<div class="sidebar-glass-card-title">SIMULATION</div>', unsafe_allow_html=True)
    demo_storm = st.checkbox(
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

# Status chip at bottom of sidebar
status_dot = "🟡" if is_cached else "🟢"
status_text = "CACHED DATA" if is_cached else "LIVE FEED"
status_color = "#f59e0b" if is_cached else "#10b981"

st.sidebar.markdown(f"""
<div style="margin-top: 18px; padding: 8px 14px; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.18); border-radius: 20px; display: inline-flex; align-items: center; gap: 8px;">
    <span style="font-size: 11px;">{status_dot}</span>
    <span style="font-weight: 800; font-size: 11px; letter-spacing: 1px; color: {status_color};">{status_text}</span>
</div>
<div style="margin-top: 8px; font-size: 11px; color: #94a3b8; font-weight: 500;">Weather data by Open-Meteo.com</div>
""", unsafe_allow_html=True)

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
