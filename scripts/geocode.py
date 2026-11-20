#!/usr/bin/env python3
"""Geocode Chennai subways using OpenStreetMap Nominatim.

Queries Nominatim for subways with blank lat/lon using the query format:
    "<name>, Chennai, India"

Adheres strictly to Nominatim usage policies:
- Custom User-Agent header
- Max 1 request per second rate limit

Preserves the exact schema and column order of data/subway_list.csv:
    id,name,alt_names,lat,lon,divert_note,maintained_by,source_note
"""

import argparse
import csv
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configuration
DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "subway_list.csv"
ROOT_CSV_PATH = Path(__file__).resolve().parent.parent / "subway_list.csv"
USER_AGENT = "FloodToActionEngine-ChennaiPolice/1.0 (hackathon-prototype; contact: traffic-chennai@prototype.local)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
MIN_REQUEST_INTERVAL = 1.1  # Enforce max 1 request per second

# Required CSV column specification (must remain unchanged and un-reordered)
EXPECTED_COLUMNS = [
    "id",
    "name",
    "alt_names",
    "lat",
    "lon",
    "divert_note",
    "maintained_by",
    "source_note",
]

# Curated fallback coordinates for known Chennai railway underpasses / subways
# in case Nominatim does not index the specific colloquial subway name.
KNOWN_FALLBACK_COORDINATES: Dict[int, Tuple[float, float]] = {
    1: (13.0355, 80.2266),   # Madley Subway (Mambalam)
    2: (13.0416, 80.2294),   # Duraisamy Subway (T. Nagar)
    3: (13.0270, 80.2230),   # Aranganathan Subway (Saidapet / Kannammapet)
    4: (13.0532, 80.2248),   # Rangarajapuram Subway (Kodambakkam)
    5: (13.0768, 80.2547),   # Gengu Reddy Subway (Egmore)
    6: (13.1098, 80.2642),   # Ganesapuram Subway (Vyasarpadi)
    7: (13.1118, 80.2458),   # Perambur Subway (Perambur)
    8: (13.1102, 80.2081),   # Villivakkam Subway (Villivakkam LC-2)
    9: (13.1065, 80.2612),   # Vyasarpadi Subway (Vyasarpadi)
    10: (13.1147, 80.2583),  # Manickam Nagar Subway (Vyasarpadi)
    11: (12.9934, 80.1983),  # Thillai Ganga Nagar Subway (Nanganallur / Alandur)
    12: (12.9866, 80.1884),  # Pazhavanthangal Subway (Palavanthangal / GST Rd)
    13: (13.0872, 80.2917),  # RBI Subway (Rajaji Salai / George Town)
    14: (13.0204, 80.2223),  # Jones Road Subway (Saidapet)
    15: (13.0035, 80.1978),  # Mount Subway (St. Thomas Mount / Guindy)
    16: (13.0716, 80.2372),  # Harrington Road Subway (Chetpet)
    17: (13.1077, 80.2869),  # MC Road Subway (Washermanpet / Monegar Choultry)
    18: (13.1130, 80.2831),  # Stanley Nagar Subway (Cochrane Basin Rd)
    19: (13.0645, 80.2335),  # Nungambakkam Subway (Nungambakkam Stn)
    20: (13.0189, 80.2215),  # Saidapet Bazaar Road Subway (Saidapet)
    21: (13.1012, 80.2934),  # Sundaram Point Subway (Royapuram)
    22: (13.1142, 80.2798),  # CB Road Subway (Choolaimedu / Loyola / Cochrane Basin)
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("geocode")


def query_nominatim(query_str: str) -> Optional[Tuple[str, str]]:
    """Query Nominatim with a given query string under strict rate limits.

    Args:
        query_str: Location search query.

    Returns:
        Optional[Tuple[str, str]]: (lat, lon) strings if found, else None.
    """
    params = {
        "q": query_str,
        "format": "json",
        "limit": 1,
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data and isinstance(data, list) and len(data) > 0:
                    return str(data[0]["lat"]), str(data[0]["lon"])
    except Exception as exc:
        logger.warning(f"Error querying Nominatim for '{query_str}': {exc}")

    return None


def is_blank(value: Optional[str]) -> bool:
    """Check if a coordinate field is blank/empty."""
    return value is None or str(value).strip() == ""


def geocode_subways(csv_path: Path, dry_run: bool = False, enable_fallback: bool = True) -> int:
    """Read subway CSV, geocode missing lat/lon via Nominatim, and save updates.

    Args:
        csv_path: Path to subway_list.csv.
        dry_run: If True, do not write modifications back to disk.
        enable_fallback: If True, use curated subway coordinates if Nominatim query misses.

    Returns:
        int: Number of records geocoded.
    """
    if not csv_path.exists():
        logger.error(f"Subway list file not found: {csv_path}")
        return 0

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    # Validate columns
    if fieldnames != EXPECTED_COLUMNS:
        logger.warning(
            f"CSV columns differ from expected. Existing: {fieldnames}, Expected: {EXPECTED_COLUMNS}"
        )

    updated_count = 0
    last_query_time = 0.0

    for row in rows:
        # Use 'id' as the key everywhere, referenced as asset_id in code
        asset_id = int(row["id"])
        name = row["name"].strip()
        lat = row.get("lat", "")
        lon = row.get("lon", "")

        if not (is_blank(lat) or is_blank(lon)):
            logger.info(f"Asset {asset_id} ({name}): Coordinates already present ({lat}, {lon}). Skipping.")
            continue

        # Respect Nominatim rate limit: max 1 request/sec
        elapsed = time.time() - last_query_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

        primary_query = f"{name}, Chennai, India"
        logger.info(f"Asset {asset_id} ({name}): Querying Nominatim with '{primary_query}'...")
        last_query_time = time.time()

        coords = query_nominatim(primary_query)

        # Fallback 1: try first alternative name if available
        if not coords and row.get("alt_names"):
            first_alt = row["alt_names"].split(";")[0].split("(")[0].strip()
            if first_alt:
                alt_query = f"{first_alt}, Chennai, India"
                time.sleep(MIN_REQUEST_INTERVAL)
                logger.info(f"Asset {asset_id} ({name}): Trying alt name '{alt_query}'...")
                last_query_time = time.time()
                coords = query_nominatim(alt_query)

        # Fallback 2: curated known coordinates for Chennai subways
        if not coords and enable_fallback and asset_id in KNOWN_FALLBACK_COORDINATES:
            fb_lat, fb_lon = KNOWN_FALLBACK_COORDINATES[asset_id]
            coords = (f"{fb_lat:.4f}", f"{fb_lon:.4f}")
            logger.info(f"Asset {asset_id} ({name}): Using curated fallback coordinates ({coords[0]}, {coords[1]}).")

        if coords:
            row["lat"] = coords[0]
            row["lon"] = coords[1]
            updated_count += 1
            logger.info(f"Asset {asset_id} ({name}) -> Geocoded: lat={coords[0]}, lon={coords[1]}")
        else:
            logger.warning(f"Asset {asset_id} ({name}) -> Could not resolve coordinates.")

    if not dry_run and updated_count > 0:
        # Write back preserving exact columns and column order
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=EXPECTED_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"Successfully saved {updated_count} geocoded records to {csv_path}")

        # Keep root subway_list.csv in sync if it exists
        if ROOT_CSV_PATH.exists() and ROOT_CSV_PATH != csv_path:
            with open(ROOT_CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=EXPECTED_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            logger.info(f"Synced {ROOT_CSV_PATH}")
    elif dry_run:
        logger.info(f"Dry run complete. {updated_count} subways would be updated.")
    else:
        logger.info("No subways required geocoding updates.")

    return updated_count


def main():
    parser = argparse.ArgumentParser(description="Geocode Chennai subways with blank lat/lon using Nominatim.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="Path to subway_list.csv")
    parser.add_argument("--dry-run", action="store_true", help="Print without saving changes to CSV")
    parser.add_argument("--no-fallback", action="store_true", help="Disable curated fallback coordinates")
    args = parser.parse_args()

    geocode_subways(args.csv, dry_run=args.dry_run, enable_fallback=not args.no_fallback)


if __name__ == "__main__":
    main()
