# ANPR Traffic Analytics Engine

A small backend service that turns raw **ANPR** (Automatic Number Plate
Recognition) camera detections into traffic analytics: vehicle counts per
camera, origin–destination routes, map heatmap data, congestion alerts and
time-based trend graphs.

It is built for a hackathon MVP and is explained for **complete beginners**.

---

## 1. What it does (in plain words)

Cameras detect cars and record "events". Each event says:

> *Plate **HR26A0001** was seen by **camera 1** at **this time**.*

This engine reads those events and answers questions like:

| Question | Endpoint |
|---|---|
| What events happened in the last hour? | `/analytics/events` |
| How many vehicles did each camera see? (LOW/MEDIUM/HIGH) | `/analytics/density` |
| Which routes do vehicles take? (camera A → camera B) | `/analytics/od` |
| Where are the busy cameras on a map? | `/analytics/heatmap` |
| Which cameras are more crowded than normal? | `/analytics/congestion` |
| How does traffic change over 15-minute buckets? | `/analytics/trends` |

> **Honest definition:** "traffic density" here means **number of vehicles
> (distinct plates) per camera per time window**. It is **not** physical
> density (vehicles per km) — that would need road-length/capacity data.

---

## 2. Architecture (how the pieces fit)

```
              HTTP + X-API-Key
                     │
        ┌────────────▼─────────────┐
        │   FastAPI app (app/main) │
        │  routes/analytics.py     │  ← URL endpoints + query params
        └────────────┬─────────────┘
                     │ calls
        ┌────────────▼─────────────┐
        │  services/ (analytics)   │  ← pure Python logic, NO SQL
        │  density / od / heatmap  │     (easy to test, never changes
        │  congestion / trend      │      when you swap databases)
        └────────────┬─────────────┘
                     │ uses standard VehicleEvent objects
        ┌────────────▼─────────────┐
        │  repository.py (SQL only)│  ← the ONLY file with database code
        └────────────┬─────────────┘
                     │ SQLAlchemy
        ┌────────────▼─────────────┐
        │ PostgreSQL + PostGIS     │  production (your team's DB)
        │ cameras / plate_events   │
        │ traffic_baselines (new)  │
        └──────────────────────────┘
```

**Why this split?** Your ANPR teammate can later feed in real data and the
analytics algorithms never change. All database-specific code lives in one
file (`app/repository.py`).

### Database tables

The engine **reads the existing tables your team already created** and never
creates or modifies them:

```sql
cameras       (id SERIAL PK, name TEXT, location GEOGRAPHY(POINT), rtsp_url TEXT)
plate_events  (id SERIAL PK, plate_number TEXT, camera_id INT → cameras.id,
               event_time TIMESTAMP, confidence FLOAT)
```

It creates **one small new table** it owns:

```sql
traffic_baselines (id, camera_id → cameras.id, time_period TEXT,
                   average_vehicle_count FLOAT, UNIQUE(camera_id, time_period))
```

**Why a new table?** Congestion means "current traffic vs. *normal* traffic".
The existing schema has nowhere to store that *normal* (baseline) value, so we
add the smallest possible table for it. If a camera has no baseline row, the
engine can optionally estimate one from recent history (the current window is
excluded so a spike can't inflate its own baseline).

---

## 3. Installation (beginners: type these exactly)

You need **Python 3.10+** installed.

```bash
# 1. Move into the project folder
cd analytics-engine

# 2. (Recommended) create a virtual environment
python3 -m venv .venv

# 3. Activate it:
#    Mac / Linux:
source .venv/bin/activate
#    Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# 4. Install the libraries
pip install -r requirements.txt
```

### Running locally with NO database server (easiest)

By default the engine uses a local **SQLite** file (`anpr_analytics.db`) that
needs zero installation. Its tables mimic the real ones so you can try
everything immediately.

```bash
# 5. Create sample data
python scripts/seed_data.py

# 6. Start the server
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** in your browser — that's an interactive page
where you can click and test every endpoint.

---

## 4. Connecting to the real PostgreSQL + PostGIS database

For production, configure the engine with separate `DB_*` environment variables.
This avoids URL-encoding problems when a database password contains special characters.
The engine reads the existing `cameras` and `plate_events` tables and creates only
its own `traffic_baselines` table when needed.

Create a local `.env` from `.env.example` and fill in:

```ini
ANALYTICS_API_KEY=<generated-secret>
DB_HOST=<postgres-host>
DB_PORT=5432
DB_NAME=<database-name>
DB_USER=<database-user>
DB_PASSWORD=<database-password>
CORS_ORIGINS=
```

`DB_HOST`, `DB_USER`, and `DB_NAME` activate PostgreSQL mode. The connection is built
with SQLAlchemy using the `postgresql+psycopg` driver.

**Production safety:** never commit `.env`, database passwords, or API keys to GitHub.
The repository contains only `.env.example`.

**PostGIS coordinates:** camera latitude/longitude are read from `cameras.location`
using `ST_Y(location::geometry)` for latitude and `ST_X(location::geometry)` for longitude.

## 5. Environment variables

| Variable | Meaning | Default |
|---|---|---|
| `ANALYTICS_API_KEY` | Secret clients must send in `X-API-Key` | empty (development only) |
| `DB_HOST` | PostgreSQL hostname | empty |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | PostgreSQL database name | empty |
| `DB_USER` | PostgreSQL username | empty |
| `DB_PASSWORD` | PostgreSQL password | empty |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call the API | empty |
| `DENSITY_LOW_THRESHOLD` | Count below this = LOW traffic | `10` |
| `DENSITY_HIGH_THRESHOLD` | Count at/above this = HIGH | `30` |
| `CONGESTION_THRESHOLD` | Congested when current/baseline >= this ratio | `1.5` |
| `DEFAULT_BUCKET_MINUTES` | Default trend bucket size | `15` |

`DATABASE_URL` remains supported as a backward-compatible SQLite fallback, but it is
not the production configuration documented here.

## 6. API key authentication

All `/analytics/*` endpoints require a key (except `/health`).

Generate a random key:

```bash
python scripts/generate_key.py
```

Copy the printed value into `.env` as `ANALYTICS_API_KEY`. Clients send it as
a header:

```
X-API-Key: <your-key>
```

The key is never hard-coded, never returned in responses, and never logged.
`.env` is in `.gitignore` so it won't be committed.

---

## 6A. Production handoff

1. Generate a secret key:

```bash
python scripts/generate_key.py
```

2. Put the generated value into the **local** `.env` as `ANALYTICS_API_KEY`.
3. Keep the PostgreSQL credentials only in `.env` or the deployment platform's secret manager.
4. Give the dashboard developer the **API base URL** and the API key through a secure channel;
   do not put the key in GitHub.
5. The API contract is:
   - `GET /health` — public health check
   - `GET /analytics/events`
   - `GET /analytics/density`
   - `GET /analytics/od`
   - `GET /analytics/heatmap`
   - `GET /analytics/congestion`
   - `GET /analytics/trends`
6. Every `/analytics/*` request must include `X-API-Key: <key>` when authentication is enabled.

**Important for browser dashboards:** an API key embedded in frontend JavaScript is visible to users.
For a public production dashboard, prefer the dashboard's backend/server-side proxy to call this engine.
If the dashboard is on a trusted internal network and calls the engine directly, set `CORS_ORIGINS`
only to the exact dashboard origin(s).

## 7. API endpoints

All analytics endpoints accept the same optional time parameters:

| Parameter | Example | Meaning |
|---|---|---|
| `window` | `15m`, `30m`, `1h`, `3h` | Named window ending now (default `1h`) |
| `start` | `2026-09-04T10:00:00Z` | Custom range start (use with `end`) |
| `end` | `2026-09-04T11:00:00Z` | Custom range end |

(For custom ranges provide **both** `start` and `end`. Timestamps are ISO-8601
and treated as UTC.)

### Example requests

```bash
KEY="paste-your-key-here"
BASE="http://127.0.0.1:8000"

# Health (no key needed)
curl "$BASE/health"

# Events in the last hour
curl -H "X-API-Key: $KEY" "$BASE/analytics/events?window=1h"

# Density / vehicle counts per camera
curl -H "X-API-Key: $KEY" "$BASE/analytics/density?window=1h"

# Origin-destination routes
curl -H "X-API-Key: $KEY" "$BASE/analytics/od?window=1h"

# Heatmap (for a map)
curl -H "X-API-Key: $KEY" "$BASE/analytics/heatmap?window=1h"

# Congestion
curl -H "X-API-Key: $KEY" "$BASE/analytics/congestion?window=1h&period=1h"

# Trends, 15-minute buckets, with per-camera breakdown
curl -H "X-API-Key: $KEY" "$BASE/analytics/trends?window=1h&bucket_minutes=15&per_camera=true"

# Custom time range
curl -H "X-API-Key: $KEY" \
  "$BASE/analytics/density?start=2026-09-04T10:00:00Z&end=2026-09-04T11:00:00Z"
```

### Example responses

**Density** (`/analytics/density?window=1h`):
```json
{
  "start": "2026-09-04T12:07:23Z",
  "end":   "2026-09-04T13:07:23Z",
  "window_label": "1h",
  "definition": "Vehicle count (distinct plate_number) per camera ...",
  "thresholds": {"low": 10, "high": 30},
  "total_vehicles": 213,
  "camera_count": 6,
  "cameras": [
    {"camera_id": 1, "camera_name": "Palwal Toll Plaza",
     "vehicle_count": 61, "traffic_level": "HIGH"}
  ]
}
```

**OD** (`/analytics/od?window=1h`):
```json
{
  "total_transitions": 39,
  "vehicles_with_journey": 20,
  "pairs": [
    {"origin_camera": 1, "origin_camera_name": "Palwal Toll Plaza",
     "destination_camera": 2, "destination_camera_name": "NH-44 Junction",
     "vehicle_count": 15}
  ]
}
```

**Heatmap** (`/analytics/heatmap?window=1h`) — drop `points` straight into a map:
```json
{
  "points": [
    {"camera_id": 1, "camera_name": "Palwal Toll Plaza",
     "latitude": 28.1449, "longitude": 77.3240,
     "vehicle_count": 61, "traffic_level": "HIGH"}
  ],
  "unknown_camera_ids": []
}
```

**Congestion** (`/analytics/congestion?window=1h&period=1h`):
```json
{
  "threshold_ratio": 1.5,
  "period": "1h",
  "baseline_source": "traffic_baselines",
  "points": [
    {"camera_id": 1, "camera_name": "Palwal Toll Plaza",
     "current_count": 61, "baseline_count": 20.0,
     "ratio": 3.05, "percent_increase": 205.0,
     "congestion_status": "CONGESTED"}
  ]
}
```

**Trends** (`/analytics/trends?window=1h&bucket_minutes=15`):
```json
{
  "bucket_minutes": 15,
  "bucket_count": 4,
  "buckets": [
    {"bucket_start": "2026-09-04T12:07:00Z", "bucket_end": "2026-09-04T12:22:00Z",
     "total_events": 40, "unique_vehicles": 40}
  ]
}
```

---

## 8. Rules the engine follows

- Timestamps are handled in **UTC**; windows are half-open `[start, end)`.
- Invalid timestamps / windows return a clear `400` error.
- **Empty datasets** return empty lists (never crash).
- **Unknown camera IDs** (events with no matching `cameras` row) are still
  counted in density/OD and reported in `unknown_camera_ids` by the heatmap.
- **Duplicate events** (same plate/camera/time) and repeated same-camera
  frames are de-duplicated so they don't create fake movements.
- Counts for density/heatmap/congestion use **DISTINCT plate_number** per
  camera (the same car seen 5 times is 1 vehicle).
- No claims are made about OCR accuracy (OCR is outside this module).

---

## 9. Tests

```bash
pytest -q
```

The tests run on a throwaway SQLite database (no PostgreSQL needed) and cover:
time-window filtering, distinct-vehicle counting, OD transitions (including
duplicate/self-transition safeguards), heatmap output, congestion statuses,
trend buckets, and API-key authentication (401/403/200).

---

## 10. Connecting the real ANPR event source later

You should **not** need to change any analytics code. Options:

1. **Point at the real database** — set `DATABASE_URL` to the PostgreSQL
   instance. Ensure new detections land in `plate_events` (the engine already
   reads `event_time`, `plate_number`, `camera_id`, `confidence`).
2. **Feed events from another service** — map your incoming events into the
   `app/analytics_types.VehicleEvent` object and call the service functions
   directly. The services never import SQLAlchemy.
3. **Baselines** — populate `traffic_baselines` with real historical averages
   (per camera and per `time_period`), or rely on the automatic
   history-based fallback.

> Note: when you outgrow `create_all`, introduce **Alembic** migrations for
> the `traffic_baselines` table. The two existing tables should be managed by
> your team's own migration setup.

---

## 11. Project structure

```
analytics-engine/
├── app/
│   ├── main.py              # FastAPI app + startup
│   ├── config.py            # settings from env / .env
│   ├── database.py          # engine, session, safe table creation
│   ├── models.py            # maps EXISTING cameras/plate_events + traffic_baselines
│   ├── schemas.py           # JSON response shapes
│   ├── security.py          # X-API-Key check
│   ├── time_utils.py        # UTC time-window parsing
│   ├── analytics_types.py   # standard VehicleEvent / CameraInfo objects
│   ├── repository.py        # ALL SQL lives here (PostGIS aware)
│   ├── routes/
│   │   ├── health.py
│   │   └── analytics.py
│   └── services/
│       ├── event_service.py
│       ├── density_service.py
│       ├── od_service.py
│       ├── heatmap_service.py
│       ├── congestion_service.py
│       └── trend_service.py
├── scripts/
│   ├── seed_data.py         # safe sample data into existing tables
│   └── generate_key.py      # random API key
├── tests/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
