# Flood-to-Action Engine (prototype v0.1), Chennai

## What it does
- Reads the next 12h rain forecast across Chennai.
- Scores 22 Chennai subways (underpasses) for the chance they become impassable.
- Gives traffic police a ranked tactical action sheet (barricade-by deadline, diversion route, dewatering pump list).

## How to run
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the Streamlit application:
   ```bash
   python -m streamlit run app.py
   ```
   Opens automatically at [http://localhost:8501](http://localhost:8501).
   *Tip*: On dry days, check the **"Demo storm"** box in the sidebar to simulate a heavy cloudburst curve across the city.

## Folder map
- `app.py`: Streamlit tactical dashboard (Map, Action Sheet, Replay tabs).
- `src/engine.py`: Heuristic risk scoring engine and action/pump tables.
- `src/rain.py`: 12-hour precipitation forecast ingestion from Open-Meteo.
- `src/replay.py`: Historical storm replay and leave-one-out validation.
- `scripts/`: Data preparation utilities (e.g. `geocode.py`).
- `data/`: Master subways list, historical closure events, rain timelines, and metrics.

## How the risk works
- **Trigger**: Each subway's trigger threshold is the lowest 3-hour rainfall sum at which it closed in past events.
- **Risk ratio**: `forecast peak 3h rain / trigger`.
- **Bands**: Green (<0.5), Amber (<0.75), Orange (<1.0), Red (>=1.0).
- **Closure ETA**: The first forecast hour where the rolling 3-hour rain reaches the trigger.
- **Barricade-by**: Closure ETA minus a 60-minute crew deployment buffer.

## Data files and sources
- `data/subway_list.csv`: 22 Chennai subways from the Greater Chennai Corporation (GCC) Bridges department list plus official news closure reports.
- `data/events.csv`: Ground-truth subway closure and restriction labels from verified news and police reports (source links inside).
- `data/rain_events.csv`: Hourly historical precipitation timelines from Open-Meteo Archive API.
- `data/sample_forecast.json`: Cached Open-Meteo forecast fallback for offline resilience.
- `data/metrics.json`: Precision, recall, and false alarm metrics across 4 past storm events.

## Limitations
- Only 4 labelled past storm events available in historical ground truth.
- Closure labels are sourced from news and police social media posts rather than real-time water sensor telemetry.
- Rain data is coarse (approx. 10–25 km grid resolution) from model/reanalysis datasets.
- Subways with no recorded closure history use an imputed default trigger (1.25x median, marked *low confidence*).
- **Advisory only**: tactical decision support, not an automated executive order.

## Roadmap (Round 2)
- Calibrated ML models using soil saturation and runoff decay.
- Digital elevation models (DEM) and catchment basin drainage features.
- Dynamic OSM road-network traffic rerouting and constable patrol dispatch optimization.
- Bilingual Tamil and English tactical broadcast alerts.
- Live API integration with GCC IoT flood sensors and telemetry from municipal pumping stations.

## Credit line
- Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).
- Map data by [OpenStreetMap](https://www.openstreetmap.org/) contributors.
