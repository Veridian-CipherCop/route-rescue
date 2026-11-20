"""Rain Forecast Ingestion Module.

Fetches 12-hour precipitation forecast from Open-Meteo across 3 Chennai grid points:
North (13.15, 80.25), Centre (13.06, 80.25), South (12.99, 80.21).
Assigns each subway to the nearest grid point and returns hourly rainfall series.
"""

from pathlib import Path
import json
import logging
import pandas as pd
import requests
import streamlit as st

logger = logging.getLogger("rain")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SUBWAYS_PATH = DATA_DIR / "subway_list.csv"
SAMPLE_FORECAST_PATH = DATA_DIR / "sample_forecast.json"

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GRID_POINTS = [
    {"name": "North", "lat": 13.15, "lon": 80.25},
    {"name": "Centre", "lat": 13.06, "lon": 80.25},
    {"name": "South", "lat": 12.99, "lon": 80.21},
]


def _assign_to_grid(lat: float, lon: float) -> int:
    """Return index (0: North, 1: Centre, 2: South) of nearest grid point."""
    best_idx = 1
    best_dist = float("inf")
    for idx, pt in enumerate(GRID_POINTS):
        dist = (lat - pt["lat"]) ** 2 + (lon - pt["lon"]) ** 2
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


def _parse_open_meteo_response(data: list) -> pd.DataFrame:
    """Parse list of 3 grid responses from Open-Meteo into subway rain DataFrame."""
    subways = pd.read_csv(SUBWAYS_PATH)
    if "id" in subways.columns and "asset_id" not in subways.columns:
        subways["asset_id"] = subways["id"].astype(int)

    rows = []
    for _, sub in subways.iterrows():
        aid = int(sub["asset_id"])
        lat = float(sub.get("lat", 13.06))
        lon = float(sub.get("lon", 80.25))

        grid_idx = _assign_to_grid(lat, lon)
        grid_data = data[grid_idx] if grid_idx < len(data) else data[0]

        hourly = grid_data.get("hourly", {})
        times = hourly.get("time", [])
        precips = hourly.get("precipitation", [])

        for t, p in zip(times, precips):
            rows.append({
                "asset_id": aid,
                "ts": pd.to_datetime(t),
                "precip_mm": float(p) if p is not None else 0.0,
            })

    return pd.DataFrame(rows)


@st.cache_data(ttl=1800)
def get_forecast() -> tuple[pd.DataFrame, bool]:
    """Fetch 12-hour precipitation forecast from Open-Meteo.

    Cached for 30 minutes (ttl=1800).
    Falls back to data/sample_forecast.json if the network request fails.

    Returns:
        tuple[pd.DataFrame, bool]: (rain_df, is_cached_fallback)
    """
    params = {
        "latitude": "13.15,13.06,12.99",
        "longitude": "80.25,80.25,80.21",
        "hourly": "precipitation",
        "forecast_hours": 12,
        "timezone": "Asia/Kolkata",
    }

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) == 3:
                return _parse_open_meteo_response(data), False
    except Exception as exc:
        logger.warning(f"Live forecast request failed: {exc}. Loading fallback.")

    # Fallback to local sample JSON
    if SAMPLE_FORECAST_PATH.exists():
        with open(SAMPLE_FORECAST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _parse_open_meteo_response(data), True

    # Extreme fallback: blank frame
    subways = pd.read_csv(SUBWAYS_PATH)
    now = pd.Timestamp.now(tz="Asia/Kolkata").floor("h")
    times = [now + pd.Timedelta(hours=i) for i in range(12)]
    blank_rows = [
        {"asset_id": int(aid), "ts": t, "precip_mm": 0.0}
        for aid in subways["id"]
        for t in times
    ]
    return pd.DataFrame(blank_rows), True
