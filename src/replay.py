"""Flood-to-Action Engine - Historical Storm Replay Module.

Evaluates engine performance against 4 historical Chennai flood events
(E2021, E2023 Michaung, E2024A, E2024B Fengal) using leave-one-out triggers.
"""

from pathlib import Path
import json
from typing import Dict, Any, List
import pandas as pd

from src.engine import get_triggers, score

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EVENTS_PATH = DATA_DIR / "events.csv"
RAIN_EVENTS_PATH = DATA_DIR / "rain_events.csv"
SUBWAYS_PATH = DATA_DIR / "subway_list.csv"
METRICS_PATH = DATA_DIR / "metrics.json"

EVENT_OPTIONS: Dict[str, str] = {
    "E2021": "Dec 2021",
    "E2023": "Michaung, Dec 2023",
    "E2024A": "Oct 2024",
    "E2024B": "Fengal, Nov 2024",
}

EVENT_WINDOWS: Dict[str, tuple[str, str]] = {
    "E2021": ("2021-12-29 00:00:00", "2021-12-31 23:59:59"),
    "E2023": ("2023-12-03 00:00:00", "2023-12-06 23:59:59"),
    "E2024A": ("2024-10-14 00:00:00", "2024-10-16 23:59:59"),
    "E2024B": ("2024-11-29 00:00:00", "2024-12-01 23:59:59"),
}


def evaluate_event(event_id: str) -> Dict[str, Any]:
    """Evaluate predicted vs actual subway closures for a single event.

    Uses leave-one-out triggers (exclude_event=event_id) so the model is
    not evaluated on its own answers.

    Args:
        event_id: Identifier ('E2021', 'E2023', 'E2024A', 'E2024B').

    Returns:
        Dict[str, Any]: Metrics, predicted list, actual list, and match details.
    """
    subways = pd.read_csv(SUBWAYS_PATH)
    name_map = subways.set_index("id")["name"].to_dict()

    events = pd.read_csv(EVENTS_PATH)
    rain_events = pd.read_csv(RAIN_EVENTS_PATH)

    # 1. Triggers excluding current event (Leave-One-Out)
    triggers = get_triggers(exclude_event=event_id)

    # 2. Filter event rain to the event window
    w_start, w_end = EVENT_WINDOWS[event_id]
    e_rain = rain_events[
        (rain_events["event_id"] == event_id)
        & (rain_events["ts"] >= w_start)
        & (rain_events["ts"] <= w_end)
    ].copy()

    # Determine horizon hours (all hours of the window)
    sample_subway = e_rain[e_rain["asset_id"] == 1]
    horizon_hours = len(sample_subway) if not sample_subway.empty else 72

    # 3. Run score()
    scored = score(e_rain, triggers, horizon_h=horizon_hours, multiplier=1.0)

    # 4. Predicted vs Actual
    predicted_df = scored[scored["band"].isin(["orange", "red"])]
    predicted_ids = set(predicted_df["asset_id"].astype(int))

    actual_rows = events[
        (events["event_id"] == event_id)
        & (events["status"].isin(["closed", "restricted"]))
    ]
    actual_ids = set(actual_rows["asset_id"].astype(int))

    matched_ids = predicted_ids & actual_ids
    matched_count = len(matched_ids)
    actual_count = len(actual_ids)
    predicted_count = len(predicted_ids)

    # 5. Metrics
    recall = round(matched_count / actual_count, 2) if actual_count > 0 else 0.0
    precision = round(matched_count / predicted_count, 2) if predicted_count > 0 else 0.0
    false_alarms = len(predicted_ids - actual_ids)

    # Formatted lists for UI display with checkmarks
    predicted_items: List[Dict[str, Any]] = []
    for aid in sorted(predicted_ids):
        is_match = aid in matched_ids
        mark = "✅" if is_match else "⚠️"
        row_band = scored[scored["asset_id"] == aid]["band"].iloc[0].upper()
        predicted_items.append({
            "asset_id": aid,
            "name": name_map.get(aid, f"Subway {aid}"),
            "display": f"{mark} {name_map.get(aid, f'Subway {aid}')} [{row_band}]",
            "is_matched": is_match,
        })

    actual_items: List[Dict[str, Any]] = []
    for aid in sorted(actual_ids):
        is_match = aid in matched_ids
        mark = "✅" if is_match else "❌"
        status = actual_rows[actual_rows["asset_id"] == aid]["status"].iloc[0]
        actual_items.append({
            "asset_id": aid,
            "name": name_map.get(aid, f"Subway {aid}"),
            "display": f"{mark} {name_map.get(aid, f'Subway {aid}')} ({status})",
            "is_matched": is_match,
        })

    return {
        "event_id": event_id,
        "event_label": EVENT_OPTIONS.get(event_id, event_id),
        "actual_count": actual_count,
        "predicted_count": predicted_count,
        "matched_count": matched_count,
        "recall": recall,
        "precision": precision,
        "false_alarms": false_alarms,
        "predicted_items": predicted_items,
        "actual_items": actual_items,
    }


def compute_and_save_all_metrics() -> Dict[str, Any]:
    """Compute replay metrics for all four events and save to data/metrics.json."""
    all_metrics = {}
    for eid in EVENT_OPTIONS.keys():
        res = evaluate_event(eid)
        all_metrics[eid] = {
            "label": res["event_label"],
            "actual_count": res["actual_count"],
            "predicted_count": res["predicted_count"],
            "matched_count": res["matched_count"],
            "recall": res["recall"],
            "precision": res["precision"],
            "false_alarms": res["false_alarms"],
        }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2)

    return all_metrics
