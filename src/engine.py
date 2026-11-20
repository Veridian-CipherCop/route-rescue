"""Flood-to-Action Engine (Chennai Traffic Police).

Heuristic risk scoring and tactical action sheet generator (plain pandas).
Replaces stubs in risk.py and actions.py.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
BAND_CUTS = {"amber": 0.5, "orange": 0.75, "red": 1.0}
CREW_BUFFER_MIN = 60

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SUBWAYS_PATH = DATA_DIR / "subway_list.csv"
EVENTS_PATH = DATA_DIR / "events.csv"
RAIN_EVENTS_PATH = DATA_DIR / "rain_events.csv"


# ----------------------------------------------------------------------
# Helper: Event Windows
# ----------------------------------------------------------------------
def _get_event_window(event_id: str, date_str: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return [start_ts, end_ts] for an event window."""
    if str(event_id).strip() == "E2023":
        start_ts = pd.Timestamp("2023-12-03 00:00:00")
        end_ts = pd.Timestamp("2023-12-06 23:59:59")
    else:
        base_dt = pd.to_datetime(date_str)
        start_ts = (base_dt - pd.Timedelta(days=1)).normalize()
        end_ts = (base_dt + pd.Timedelta(days=1)).replace(hour=23, minute=59, second=59)
    return start_ts, end_ts


# ----------------------------------------------------------------------
# Function 1: get_triggers
# ----------------------------------------------------------------------
def get_triggers(exclude_event: Optional[str] = None) -> pd.DataFrame:
    """Calculate 3-hour rainfall trigger threshold for each subway.

    Trigger = MIN peak rolling-3h rain over past events where subway was
    closed/restricted. Subways with no closure history get
    1.25 * median(known triggers) and confidence = 'low'.
    """
    subways = pd.read_csv(SUBWAYS_PATH)
    if "id" in subways.columns:
        subways["asset_id"] = subways["id"].astype(int)

    events = pd.read_csv(EVENTS_PATH)
    if exclude_event:
        events = events[events["event_id"] != exclude_event].copy()

    all_event_ids = events["event_id"].unique().tolist()
    total_events_count = len(all_event_ids)

    # Event date lookup
    event_dates = events.groupby("event_id")["date"].first().to_dict()

    # Pre-calculate event windows
    event_windows = {
        eid: _get_event_window(eid, event_dates.get(eid, "2024-01-01"))
        for eid in all_event_ids
    }

    # Identify which subways closed/restricted in which events
    closed_events = events[events["status"].isin(["closed", "restricted"])].copy()
    closed_events["asset_id"] = closed_events["asset_id"].astype(int)

    # Subways closure counts
    closure_counts = (
        closed_events.groupby("asset_id")["event_id"]
        .nunique()
        .to_dict()
    )

    # If rain_events.csv exists, calculate empirical rolling 3h peaks
    peaks_dict: Dict[tuple[int, str], float] = {}
    if RAIN_EVENTS_PATH.exists():
        rain_df = pd.read_csv(RAIN_EVENTS_PATH)
        if not rain_df.empty and {"event_id", "asset_id", "ts", "precip_mm"}.issubset(rain_df.columns):
            rain_df["ts"] = pd.to_datetime(rain_df["ts"])
            rain_df["asset_id"] = rain_df["asset_id"].astype(int)

            if exclude_event:
                rain_df = rain_df[rain_df["event_id"] != exclude_event]

            for (eid, aid), group in rain_df.groupby(["event_id", "asset_id"]):
                if eid in event_windows:
                    w_start, w_end = event_windows[eid]
                    in_win = group[(group["ts"] >= w_start) & (group["ts"] <= w_end)].sort_values("ts")
                    if not in_win.empty:
                        r3 = in_win["precip_mm"].rolling(3, min_periods=1).sum()
                        peaks_dict[(aid, eid)] = float(r3.max())

    triggers_list = []
    known_triggers = []

    for _, row in subways.iterrows():
        aid = int(row["asset_id"])
        c_count = closure_counts.get(aid, 0)

        # Get peaks for events where this subway was closed
        c_sub_events = closed_events[closed_events["asset_id"] == aid]["event_id"].unique()
        closed_peaks = [
            peaks_dict[(aid, eid)]
            for eid in c_sub_events
            if (aid, eid) in peaks_dict and not np.isnan(peaks_dict[(aid, eid)])
        ]

        if closed_peaks:
            trigger_val = float(min(closed_peaks))
            confidence = "ok"
            known_triggers.append(trigger_val)
        else:
            trigger_val = np.nan
            confidence = "low"

        triggers_list.append({
            "asset_id": aid,
            "name": row["name"],
            "lat": row.get("lat"),
            "lon": row.get("lon"),
            "divert_note": row.get("divert_note", ""),
            "maintained_by": row.get("maintained_by", ""),
            "trigger": trigger_val,
            "confidence": confidence,
            "closed_count": c_count,
            "total_events": total_events_count,
        })

    triggers_df = pd.DataFrame(triggers_list)

    # Impute missing triggers for subways with no closure history: 1.25 * median
    median_trigger = float(np.median(known_triggers)) if known_triggers else 45.0
    fallback_val = round(1.25 * median_trigger, 1)

    triggers_df["trigger"] = triggers_df["trigger"].fillna(fallback_val).round(1)
    return triggers_df


# ----------------------------------------------------------------------
# Function 2: score
# ----------------------------------------------------------------------
def score(
    rain_df: pd.DataFrame,
    triggers: pd.DataFrame,
    horizon_h: int = 12,
    multiplier: float = 1.0,
) -> pd.DataFrame:
    """Score subways against rainfall forecast over given horizon and multiplier.

    Args:
        rain_df: DataFrame with asset_id, ts, precip_mm.
        triggers: DataFrame from get_triggers.
        horizon_h: Number of forecast hours to inspect (1 to 12).
        multiplier: Rainfall scale multiplier.

    Returns:
        pd.DataFrame: Scored subways with bands, ratios, eta, barricade_by, why.
    """
    rain = rain_df.copy()
    rain["ts"] = pd.to_datetime(rain["ts"])
    rain["asset_id"] = rain["asset_id"].astype(int)

    # Map triggers by asset_id
    trig_map = triggers.set_index("asset_id").to_dict(orient="index")

    scored_rows = []

    for aid, tinfo in trig_map.items():
        sub_rain = rain[rain["asset_id"] == aid].sort_values("ts")
        if not sub_rain.empty:
            sub_rain = sub_rain.iloc[:horizon_h].copy()
            sub_rain["precip_scaled"] = sub_rain["precip_mm"] * multiplier
            rolling_3h = sub_rain["precip_scaled"].rolling(3, min_periods=1).sum()
            peak3h = float(rolling_3h.max()) if not rolling_3h.empty else 0.0

            # Find first timestamp reaching trigger
            trigger_val = float(tinfo["trigger"])
            breach_rows = sub_rain[rolling_3h >= trigger_val]
            if not breach_rows.empty:
                eta = breach_rows.iloc[0]["ts"]
                barricade_by = eta - pd.Timedelta(minutes=CREW_BUFFER_MIN)
            else:
                eta = None
                barricade_by = None
        else:
            peak3h = 0.0
            eta = None
            barricade_by = None

        trigger_val = float(tinfo["trigger"])
        ratio = round(peak3h / trigger_val, 2) if trigger_val > 0 else 0.0

        # Band cuts: green < 0.5, amber < 0.75, orange < 1.0, red >= 1.0
        if ratio >= BAND_CUTS["red"]:
            band = "red"
        elif ratio >= BAND_CUTS["orange"]:
            band = "orange"
        elif ratio >= BAND_CUTS["amber"]:
            band = "amber"
        else:
            band = "green"

        c_count = tinfo["closed_count"]
        t_events = tinfo["total_events"]
        conf = tinfo["confidence"]

        if c_count > 0:
            why = (
                f"Closed in {c_count} of {t_events} past events; "
                f"forecast 3h peak {peak3h:.1f} mm vs trigger {trigger_val:.1f} mm"
            )
        else:
            why = (
                f"No past closures ({conf} confidence); "
                f"forecast 3h peak {peak3h:.1f} mm vs trigger {trigger_val:.1f} mm"
            )

        scored_rows.append({
            "asset_id": aid,
            "name": tinfo["name"],
            "lat": tinfo["lat"],
            "lon": tinfo["lon"],
            "divert_note": tinfo["divert_note"],
            "maintained_by": tinfo["maintained_by"],
            "trigger": trigger_val,
            "confidence": conf,
            "closed_count": c_count,
            "total_events": t_events,
            "peak3h": round(peak3h, 1),
            "ratio": ratio,
            "band": band,
            "eta": eta,
            "barricade_by": barricade_by,
            "why": why,
        })

    result_df = pd.DataFrame(scored_rows)

    # Sort red first, then orange, amber, green, then ratio descending
    band_rank = {"red": 0, "orange": 1, "amber": 2, "green": 3}
    result_df["_rank"] = result_df["band"].map(band_rank)
    result_df = result_df.sort_values(by=["_rank", "ratio"], ascending=[True, False]).drop(columns=["_rank"])
    return result_df.reset_index(drop=True)


# ----------------------------------------------------------------------
# Helpers: Action Sheet & Pump Allocation
# ----------------------------------------------------------------------
def get_action_sheet(scored_df: pd.DataFrame) -> pd.DataFrame:
    """Return tactical police action sheet."""
    cols = ["asset_id", "name", "band", "ratio", "barricade_by", "divert_note", "why"]
    return scored_df[cols].copy()


def get_pump_table(scored_df: pd.DataFrame, total_pumps: int = 10) -> pd.DataFrame:
    """Allocate available pumps to subways with highest flood risk."""
    high_risk = scored_df[scored_df["band"].isin(["red", "orange"])].copy()
    if high_risk.empty:
        high_risk = scored_df.head(total_pumps).copy()
    alloc = high_risk.head(total_pumps).copy()
    alloc["pumps_assigned"] = 1
    return alloc[["asset_id", "name", "band", "ratio", "pumps_assigned", "maintained_by"]]


if __name__ == "__main__":
    print("=" * 60)
    print("Flood-to-Action Engine (Chennai Traffic Police)")
    print("=" * 60)
    triggers = get_triggers()
    print(f"Loaded {len(triggers)} subways with triggers:")
    summary_cols = ["asset_id", "name", "trigger", "confidence", "closed_count", "total_events"]
    print(triggers[summary_cols].to_string(index=False))
    print("\nEngine initialized successfully.")

