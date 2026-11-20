# Flood-to-Action Engine (Chennai Traffic Police)
## 4-Hour Hackathon Prototype Specification

---

## 1. Executive Summary & Objective
The **Flood-to-Action Engine** is a tactical decision-support prototype built specifically for the **Chennai Traffic Police (CTP)** and coordination with the **Greater Chennai Corporation (GCC)** during monsoon and severe cyclonic rainfall events (e.g., Michaung, Fengal).

The objective is to ingest upcoming 12-hour precipitation forecasts every 30 minutes, score 22 critical Chennai underpasses/subways for flood and impassability risk, and produce an immediate, prioritized operational **Police Action Sheet**:
1. **Barricade-By Deadline**: Exact ETA for police deployment before water levels make traffic hazardous.
2. **Traffic Diversion Routes**: Actionable notes and detour guidance for field constables.
3. **Pump Allocation Priority**: Ranked list of subways urgently needing GCC dewatering pumps.

---

## 2. Core Architecture & Constraints
- **Design Philosophy**: Rapid, lightweight, explainable heuristic engineering. Keep it simple; absolutely **no over-engineering**.
- **Tech Stack**:
  - **Language**: Python 3.11
  - **UI / Dashboard**: Streamlit + Folium (`streamlit-folium`)
  - **Data Processing**: pandas, requests
- **Strict Exclusions**:
  - **NO Machine Learning (ML)**: Deterministic, transparent rules only.
  - **NO Relational/NoSQL Database**: CSV/in-memory file-backed operation.
  - **NO Complex GIS/OSM/DEM Pipelines**: No heavyweight Digital Elevation Models, shapefiles, or external routing networks.

---

## 3. Data Specification
### Primary Asset Dataset (`data/subway_list.csv`)
22 documented subways across Chennai.
- **Identifier**: `id` column must be used as the primary key across all modules and named `asset_id` in code.
- **Columns**:
  - `id`: Unique integer identifier (1–22)
  - `name`: Official or common name of the subway (e.g., Madley, Duraisamy, Ganesapuram)
  - `alt_names`: Alternative names / local landmarks
  - `lat`: Latitude coordinate (WGS84)
  - `lon`: Longitude coordinate (WGS84)
  - `divert_note`: Operational traffic diversion instruction
  - `maintained_by`: Maintaining authority (GCC or State Highways)
  - `source_note`: Verification source reference
- **Integrity Rule**: `data/subway_list.csv` is static and must NOT be overwritten, corrupted, or altered in structure.

---

## 4. Pipeline & Module Responsibilities

### 4.1 Configuration (`src/config.py`)
- File paths (`DATA_DIR`, `SUBWAY_CSV_PATH`).
- Key identifier definitions (`KEY_COL = "id"`, `ASSET_ID = "asset_id"`).
- Alert thresholds (e.g., rainfall intensity triggers in mm/hr, accumulation thresholds).
- Global refresh intervals and default coordinates (Chennai bounding center: 13.0827° N, 80.2707° E).

### 4.2 Rain Ingestion Engine (`src/rain.py`)
- Pulls next-12-hour precipitation forecast for subway coordinates.
- Supports both live forecast API calls and fallback/offline simulation data.
- Aggregates rainfall into:
  - Peak intensity (max mm/hr in next 3h / 6h).
  - Cumulative 12-hour precipitation (mm).
  - Onset window of heavy precipitation.

### 4.3 Risk & Impassability Engine (`src/risk.py`)
- Evaluates risk of each subway becoming impassable based on:
  - Rainfall rate and short-term accumulation.
  - Historical flood susceptibility and maintenance jurisdiction.
  - Rate of change in forecast intensity.
- Assigns a standardized risk tier:
  - `CRITICAL` (Impassable within 1–2 hours; immediate barricading required)
  - `HIGH` (Likely impassable within 3–4 hours; stage barricades and pumps)
  - `MEDIUM` (Waterlogging expected; slow traffic)
  - `LOW` (Normal operations)
- Computes deterministic numerical risk score (0 to 100).

### 4.4 Police Action Generator (`src/actions.py`)
- Translates risk scores into tactical police commands:
  - **Barricade-By Time**: Derived from rainfall onset curve minus safety cushion.
  - **Diversions**: Fetched and formatted from `divert_note` with situational advisories.
  - **Pump Priority**: Ranked allocation for available GCC dewatering units.
- Generates downloadable/printable Police Action Sheet (table and summary card format).

### 4.5 Scenario Replay Engine (`src/replay.py`)
- Replays benchmark historical storms (e.g., Cyclone Michaung Dec 2023, Cyclone Fengal Nov 2024, or synthetic cloudbursts).
- Facilitates dry-run presentations and hackathon demo evaluation without depending on live storm events.

### 4.6 Dashboard & Map Interface (`app.py`)
- Interactive Streamlit dashboard with:
  - Summary KPI cards (Active alerts, subways to barricade immediately, pumps required).
  - Interactive Folium map displaying the 22 subways color-coded by risk status.
  - Ranked Action Sheet table with sorting and filtering.
  - Replay / Simulation control panel.

---

## 5. Extensibility & Future Prompt Integration
- The codebase skeleton is designed to directly receive:
  - Calibrated threshold values for rain accumulation and barricade timing.
  - Specific weather API integration parameters.
  - Advanced police checklist formatting and export options.
