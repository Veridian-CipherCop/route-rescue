"""Flood-to-Action Engine - Configuration and Constants.

Central configuration for file paths, coordinates, risk thresholds,
and column mappings.
"""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = BASE_DIR / "scripts"
SUBWAY_CSV_PATH = DATA_DIR / "subway_list.csv"

# Key identifier mapping
# CSV column is 'id', used as 'asset_id' in application logic
KEY_COL = "id"
ASSET_ID = "asset_id"

# Geospatial settings (Chennai center)
CHENNAI_LAT = 13.0827
CHENNAI_LON = 80.2707
DEFAULT_MAP_ZOOM = 12

# Operational settings
FORECAST_HOURS = 12
UPDATE_INTERVAL_MINUTES = 30

# Risk level categories
RISK_LEVEL_CRITICAL = "CRITICAL"
RISK_LEVEL_HIGH = "HIGH"
RISK_LEVEL_MEDIUM = "MEDIUM"
RISK_LEVEL_LOW = "LOW"
