# Flood-to-Action Engine (Chennai Traffic Police)

A rapid 4-hour hackathon prototype providing real-time flood risk scoring and operational action sheets for Chennai's 22 vulnerable road subways (underpasses).

---

## Overview
During severe rain events in Chennai, railway underpasses and road subways flood rapidly, posing severe entrapment risks for motorists. The **Flood-to-Action Engine** transforms 12-hour rainfall forecasts into actionable instructions for traffic personnel:
- **Barricade-by Time**: Clear deadline to close subways before water reaches dangerous levels.
- **Traffic Diversions**: Pre-mapped diversion routes per subway.
- **Pump Allocation**: Ranked list to optimize municipal dewatering pump placement.

## Technology Stack
- **Python 3.11**
- **Streamlit**: Tactical dashboard UI
- **Pandas**: In-memory tabular scoring and data manipulation
- **Folium & Streamlit-Folium**: Interactive geospatial mapping
- **Requests**: Forecast API data ingestion
- *No ML, No Database, No complex GIS/OSM/DEM dependencies.*

---

## Directory Structure
```
cip/
├── app.py                  # Main Streamlit application entrypoint
├── requirements.txt        # Python package dependencies
├── SPEC.md                 # System specification and rules
├── README.md               # Project documentation
├── data/
│   └── subway_list.csv     # 22 Chennai subways master dataset
├── src/
│   ├── __init__.py
│   ├── config.py           # Configuration, constants, and paths
│   ├── rain.py             # Rain forecast ingestion and aggregation
│   ├── risk.py             # Heuristic impassability risk scoring engine
│   ├── actions.py          # Action sheet generator (barricades, diversions, pumps)
│   └── replay.py           # Scenario replay and simulation module
└── scripts/                # Utility and operational helper scripts
```

---

## Installation & Running

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Launch the dashboard**:
   ```bash
   streamlit run app.py
   ```
