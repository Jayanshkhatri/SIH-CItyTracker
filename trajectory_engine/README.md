# SIH26127 - CityTracker Trajectory Engine

AI-assisted multi-camera ANPR trajectory reconstruction, traffic analytics,
GIS output, and PUC alert processing for the SIH26127 CityTracker project.

---

## 1. Scope

The `trajectory_engine` package contains the trajectory reconstruction and
analytics backend used by CityTracker.

The current engine supports:

- multi-camera vehicle trajectory reconstruction
- plate-event association
- trajectory lifecycle handling
- historical trajectory reconstruction
- movement and route analysis
- directed camera-flow analytics
- travel-time analytics
- congestion analytics
- origin-destination analytics
- anomaly detection
- PUC verification and PUC-related alerts
- GeoJSON camera output
- GeoJSON trajectory output
- dashboard aggregation
- FastAPI read APIs
- bounded Supabase/PostgreSQL runtime refreshes

The core trajectory and analytics logic is already implemented in the
existing Phase 7, Phase 8, and Phase 9 modules.

Phase 10 connects that existing logic to real Supabase/PostgreSQL data.

---

## 2. Important Architecture Rule

The trajectory engine has two different concepts:

1. **Camera data**
   - Comes from Supabase in the real runtime.
   - Supabase camera names and coordinates are authoritative.

2. **Trajectory network**
   - Defines the directed connections between cameras.
   - The current repository contains a synthetic/demo network.
   - It is NOT authoritative road/GIS data.

The demo network is intentionally kept separate from Supabase camera
coordinates so that the engine can be tested end-to-end without pretending
that synthetic connections represent real roads.

---

## 3. Main Runtime Flow

The real runtime follows this sequence:

```text
Supabase PostgreSQL
        |
        v
   Camera Reader
        |
        v
   Plate Event Reader
        |
        v
 Event Normalization
        |
        v
Trajectory Reconstruction
        |
        v
    PUC Sync
        |
        v
  Phase 9 Service
        |
        +--------------------+
        |                    |
        v                    v
   Route/Flow          Traffic Analytics
   Analytics           + Alerts
        |
        v
Local Trajectory Snapshot
        |
        v
FastAPI Read API
        |
        v
Frontend