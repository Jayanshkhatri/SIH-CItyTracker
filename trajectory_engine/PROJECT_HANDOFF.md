# SIH26127 — PROJECT HANDOFF

## City-Wide AI Engine for Multi-Camera ANPR, Trajectory Tracking and Urban Traffic Analytics

**Repository purpose:** Trajectory Engine / Backend / Data Processing

**Problem ID:** SIH26127

**Current verified baseline:** STEP 2.30

**Next implementation:** STEP 2.31 — Trajectory Persistence / Storage Layer

---

# 1. PROJECT PURPOSE

This is a Smart India Hackathon project:

> **City-Wide AI Engine for Multi-Camera ANPR, Trajectory Tracking and Urban Traffic Analytics**

The system receives vehicle observations from multiple traffic cameras and converts isolated observations into meaningful city-wide vehicle movement information.

The eventual system should provide:

- vehicle observations
- cross-camera association
- persistent trajectory identities
- vehicle trajectories
- route information
- travel time
- distance
- speed
- traffic flow
- congestion analytics
- suspicious movement detection
- alerts
- dashboard-ready data
- GIS visualization

The central problem is:

```text
Camera 1 observes vehicle
        ↓
Camera 2 observes vehicle
        ↓
Camera 3 observes vehicle
        ↓
System determines whether observations belong
to the same vehicle / persistent trajectory
        ↓
Reconstruct movement
        ↓
Calculate route
distance
travel time
speed
        ↓
Generate traffic intelligence
```

---

# 2. DESIGN PRINCIPLE

The system must be:

```text
Explainable
Deterministic where possible
Confidence-aware
Trajectory-aware
Scalable
Database-compatible
Dashboard-ready
```

A decision should be explainable using evidence such as:

```text
Plate similarity
OCR confidence
Temporal proximity
Camera sequence
Camera connectivity
Route feasibility
Travel time
Movement feasibility
Trajectory consistency
Persistent identity evidence
```

Avoid treating any single weak signal as definitive identity proof.

---

# 3. EVENTUAL SYSTEM PIPELINE

```text
Vehicle Detection
        ↓
License Plate Detection
        ↓
OCR / ANPR
        ↓
ANPR Events
        ↓
OCR Cleaning / Normalization
        ↓
Cross-Camera Vehicle Association
        ↓
Trajectory Reconstruction
        ↓
Persistent Trajectory Identity
        ↓
Trajectory Persistence
        ↓
Distance / Time / Speed
        ↓
Anomaly Detection
        ↓
Traffic Analytics
        ↓
Alerts
        ↓
API
        ↓
Dashboard / GIS
```

---

# 4. PROJECT PHASES

The original high-level roadmap is:

## Phase 1 — Architecture / API / Data Foundation

- architecture
- database structure
- API structure
- event format
- camera data
- ANPR event format

## Phase 2 — ANPR

- vehicle detection
- plate detection
- OCR
- confidence
- camera
- timestamp

The trajectory-engine repository does not need to implement the entire ANPR model.

## Phase 3 — Tracking / Event Processing

- event processing
- observation association
- duplicate handling
- OCR normalization
- OCR error handling

## Phase 4 — Backend / Database

- database retrieval
- camera/event joins
- trajectory persistence
- backend processing
- APIs

## Phase 5 — Frontend / GIS

- camera map
- trajectory map
- vehicle movement
- analytics
- alerts
- GIS visualization

## Phase 6 — Cross-Camera Matching

- plate similarity
- temporal feasibility
- camera connectivity
- spatial feasibility
- route feasibility
- trajectory consistency
- optional appearance similarity later

## Phase 7 — Trajectory Engine

- event processing
- trajectory reconstruction
- identity resolution
- persistence
- movement calculations
- trajectory quality

## Phase 8 — Analytics

- travel-time analytics
- speed analytics
- camera-to-camera flow
- traffic density
- congestion
- route patterns
- traffic patterns

## Phase 9 — Alerts

- unrealistic movement
- abnormal travel time
- suspicious trajectories
- rule-based anomalies

## Phase 10 — Integration / Polish

- Supabase
- API
- dashboard
- GIS
- logging
- performance
- end-to-end testing
- demo preparation

---

# 5. CURRENT REPOSITORY

Expected project directory:

```text
C:\Users\Sanjay\Documents\trajectory_engine
```

Important files include:

```text
AGENTS.md
PROJECT_HANDOFF.md

trajectory.py
database.py
test_database.py

trajectory_step_*.py
```

Python environment:

```text
.venv
```

Database technology:

```text
Supabase
PostgreSQL
PostGIS
```

Python PostgreSQL driver:

```text
psycopg
```

---

# 6. DATABASE

Existing confirmed tables:

## cameras

```text
id
name
location
rstpurl
```

`location` is PostGIS geometry.

Coordinates can be extracted using:

```sql
ST_Y(cameras.location::geometry) AS latitude,
ST_X(cameras.location::geometry) AS longitude
```

## plate_events

```text
id
plate_number
camera_id
event_time
confidence
```

`camera_id` links events to cameras.

---

# 7. DATABASE STATUS

Database connectivity has already been successfully tested.

Completed:

```text
Supabase connection
        ↓
plate_events retrieval
        ↓
camera join
        ↓
PostGIS coordinate extraction
        ↓
Python dictionary conversion
```

Example internal representation:

```python
{
    "id": 1,
    "plate_number": "DL01AB1234",
    "camera_id": 1,
    "camera_name": "Camera_1",
    "latitude": 28.7041,
    "longitude": 77.1025,
    "event_time": datetime(...),
    "confidence": 0.95
}
```

Do not redo the database foundation unless required by a current step.

---

# 8. DEVELOPMENT MODE

During algorithm development, temporary in-memory test data is intentional.

The preferred workflow is:

```text
Temporary data
        ↓
Implement algorithm
        ↓
Feature testing
        ↓
Edge-case testing
        ↓
Regression testing
        ↓
Verify
        ↓
Integrate with Supabase when appropriate
```

Do not continuously write artificial data into Supabase just to test algorithms.

---

# 9. DATABASE SAFETY

Unless explicitly required by the current implementation:

DO NOT:

- insert fake events
- delete real events
- modify real events
- modify camera records
- change schema
- change production/shared database configuration

The database should not become a scratchpad for algorithm experiments.

---

# 10. VERSIONING STRATEGY

Substantial algorithmic steps should be implemented in versioned files.

Example:

```text
trajectory.py
        ↓
trajectory_step_2.31.py
        ↓
test
        ↓
regression
        ↓
verify
```

The old verified baseline must remain recoverable.

A new implementation becomes the baseline only after verification.

---

# 11. WHY VERSIONING MATTERS

A previous automated modification caused:

```text
SyntaxError: unterminated string literal
```

The working implementation had to be restored.

Therefore:

```text
Verified baseline
        ↓
New version
        ↓
Test
        ↓
Regression
        ↓
Promotion
```

is safer than destructive in-place modification.

Avoid brittle automated text replacement when a clean versioned implementation is safer.

---

# 12. CURRENT CAMERA TEST DATA

Temporary test cameras:

```text
Camera_1
ID: 1
lat: 28.7041
lon: 77.1025

Camera_2
ID: 2
lat: 28.7045
lon: 77.1030

Camera_3
ID: 3
lat: 28.7050
lon: 77.1038

Camera_4
ID: 4
lat: 28.7048
lon: 77.1045

Camera_5
ID: 5
lat: 28.7060
lon: 77.1060
```

Temporary graph:

```text
1 <-> 2
2 <-> 3
2 <-> 4
4 <-> 3
```

Camera 5 is intentionally disconnected.

Important:

> This is a development graph, not a real road-network graph.

---

# 13. DEVELOPMENT THRESHOLDS

Current development/test values include:

```python
DUPLICATE_WINDOW_SECONDS = 30

MAX_PLAUSIBLE_SPEED_KMH = 60

MIN_CONFIDENCE = 0.90

MAX_PLATE_DISTANCE = 1

MAX_FUZZY_TIME_GAP_SECONDS = 600

TRAJECTORY_SCORE_THRESHOLD = 7

TRAJECTORY_SCORE_MARGIN = 2

HIGH_CONFIDENCE_SCORE = 9

POSSIBLE_MATCH_SCORE = 7

AMBIGUOUS_SCORE = 5

MULTI_CANDIDATE_MARGIN = 2

MIN_CONSISTENCY_CHECKS = 3

HIGH_CONFIDENCE_PERCENT = 85

MEDIUM_CONFIDENCE_PERCENT = 65

MAX_TRAJECTORY_GAP_SECONDS = 3600

ANALYTICS_READY_SCORE = 85

REVIEW_REQUIRED_SCORE = 65
```

These are development thresholds.

They are not assumed to be production-calibrated.

---

# 14. COMPLETED ALGORITHM HISTORY

The trajectory engine progressed incrementally through the following verified stages.

---

## STEP 2.8 — BASIC TRAJECTORY PROCESSOR

Implemented:

- grouping by plate
- chronological sorting
- camera sequence generation

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.9 — REAL SUPABASE DATA

Implemented:

- event retrieval
- camera join
- coordinate extraction
- dictionary conversion
- grouping
- chronological ordering

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.10 — TIME DIFFERENCE

Implemented travel-time calculations between detections.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.11 — DIJKSTRA ROUTE DISTANCE

Implemented Dijkstra routing.

Temporary graph edge weights use Haversine distance.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.12 — MULTIPLE VEHICLES + MESSY ORDERING

Verified:

- multiple vehicles
- shuffled events
- chronological reconstruction
- repeated detections

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.13 — SAME-CAMERA DUPLICATE HANDLING

Threshold:

```python
DUPLICATE_WINDOW_SECONDS = 30
```

Same vehicle + same camera + within threshold is treated as repeated observation.

Higher-confidence observation is retained.

Legitimate later revisits remain valid.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.14 — CHRONOLOGICAL TESTING

Verified that events are ordered by `event_time`, not input/database ordering.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.15 — LEGITIMATE CAMERA REVISIT

Verified:

```text
Camera_1
    ↓
Camera_2
    ↓
Camera_3
    ↓
Camera_2
```

where the second Camera 2 observation occurs sufficiently later.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.16 — UNREALISTIC MOVEMENT DETECTION

Threshold:

```python
MAX_PLAUSIBLE_SPEED_KMH = 60
```

Unrealistic movement is flagged for review rather than treated as confirmed behavior.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.17 — DISCONNECTED ROUTE HANDLING

Disconnected routes return:

```text
NO CONNECTED PATH
Distance: N/A
```

The system does not invent a route.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.18 — CONFIDENCE-AWARE FILTERING

Threshold:

```python
MIN_CONFIDENCE = 0.90
```

Low-confidence events are filtered before downstream processing.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.19 — OCR FUZZY PLATE MATCHING

Implemented:

```text
normalize_plate_number
levenshtein_distance
plate_numbers_match
find_fuzzy_plate_matches
```

Threshold:

```python
MAX_PLATE_DISTANCE = 1
```

Important:

```text
fuzzy match != same vehicle
```

No automatic trajectory merging.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.20 — CONTEXT-AWARE OCR VALIDATION

Implemented contextual validation using:

1. plate similarity
2. temporal proximity
3. same-camera context
4. camera connectivity
5. chronological context

Threshold:

```python
MAX_FUZZY_TIME_GAP_SECONDS = 600
```

This revealed that event-to-event fuzzy matching could create noisy many-to-many relationships.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.21 — TRAJECTORY-LEVEL OCR ASSOCIATION

Architecture moved from:

```text
event ↔ event
```

toward:

```text
OCR observation
        ↓
candidate trajectory
```

Implemented trajectory-level candidate evaluation.

A self-comparison bug was fixed so the candidate trajectory plate is correctly used.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.22 — ASSOCIATION DECISION REFINEMENT

Decision classes:

```text
HIGH CONFIDENCE
POSSIBLE MATCH
AMBIGUOUS / REVIEW
REJECT
```

Thresholds:

```text
>= 9 → HIGH CONFIDENCE
>= 7 → POSSIBLE MATCH
>= 5 → AMBIGUOUS / REVIEW
< 5  → REJECT
```

Movement infeasibility results in rejection.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.23 — MULTI-CANDIDATE TRAJECTORY RANKING

Implemented candidate ranking.

Threshold:

```python
MULTI_CANDIDATE_MARGIN = 2
```

Close candidate scores remain ambiguous instead of being arbitrarily merged.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.24 — ASSOCIATION CONSISTENCY VALIDATION

Implemented consistency checks for:

- plate
- time
- camera
- movement
- trajectory

All tested best candidates passed available consistency checks.

Ambiguous candidates remained ambiguous where ranking evidence was weak.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.25 — ASSOCIATION CONFIDENCE AGGREGATION

Implemented confidence aggregation across association evidence.

Example results:

```text
DL01AB1234 → HIGH → 100%
DL01AB123A → HIGH → 97.75%
DL02XY5678 → HIGH → 100%
DL02XY567  → AMBIGUOUS → 94%
```

Important:

High confidence does not automatically override candidate ambiguity.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.26 — BIDIRECTIONAL TEMPORAL / MOVEMENT CONSISTENCY

Implemented:

```text
previous-neighbor validation
next-neighbor validation
bidirectional movement validation
bidirectional confidence
```

Possible states:

```text
BIDIRECTIONAL_PASS
BIDIRECTIONAL_FAIL
NO_NEIGHBOR
```

Movement failure can result in rejection.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.27 — TRAJECTORY CONTINUITY VALIDATION

Threshold:

```python
MAX_TRAJECTORY_GAP_SECONDS = 3600
```

Validated:

- chronology
- connectivity
- movement
- time gaps
- continuity

Known test results:

```text
Continuous:      6
Inconsistent:    2
```

The inconsistent examples included:

```text
DL05MN7890
```

with unrealistic movement and:

```text
DL06AB6789
```

with a disconnected route.

Status:

```text
COMPLETE / VERIFIED
```

---

## STEP 2.28 — TRAJECTORY QUALITY / RELIABILITY SCORING

Components:

```text
Chronology       20%
Connectivity     20%
Movement         20%
Time gaps        20%
Observation
density         20%
```

Thresholds:

```python
HIGH_QUALITY_SCORE = 85
MEDIUM_QUALITY_SCORE = 65
```

Baseline results:

```text
DL01AB1234 → 92 → HIGH
DL01AB123A → 88 → HIGH
DL02XY5678 → 96 → HIGH
DL02XY567  → 88 → HIGH
DL04RT3456 → 100 → HIGH
DL05MN7890 → 72 → MEDIUM
DL06AB6789 → 52 → LOW
DL07CD1122 → 92 → HIGH
```

Status:

```text
COMPLETE / VERIFIED
```

---

# 15. STEP 2.29 — TRAJECTORY USABILITY CLASSIFICATION

Thresholds:

```python
ANALYTICS_READY_SCORE = 85
REVIEW_REQUIRED_SCORE = 65
```

Classification:

```text
Score >= 85
→ ANALYTICS READY

Score 65–84.99
→ REVIEW REQUIRED

Score < 65
→ ANALYTICS BLOCKED
```

Results:

```text
DL01AB1234 → 92 → ANALYTICS READY
DL01AB123A → 88 → ANALYTICS READY
DL02XY5678 → 96 → ANALYTICS READY
DL02XY567  → 88 → ANALYTICS READY
DL04RT3456 → 100 → ANALYTICS READY
DL05MN7890 → 72 → REVIEW REQUIRED
DL06AB6789 → 52 → ANALYTICS BLOCKED
DL07CD1122 → 92 → ANALYTICS READY
```

Summary:

```text
Analytics-ready:     6
Review-required:     1
Analytics-blocked:   1
```

Status:

```text
COMPLETE / VERIFIED
```

---

# 16. STEP 2.30 — PERSISTENT TRAJECTORY IDENTITY LAYER

## STATUS

```text
COMPLETE / VERIFIED
```

Step 2.30 introduced the next architectural layer:

```text
trajectory
    ↓
persistent trajectory identity
```

The system now distinguishes between:

```text
raw plate observation
```

and:

```text
persistent trajectory identity
```

The purpose of this layer is to provide a stable internal identity for a reconstructed trajectory rather than relying directly on a raw OCR plate string.

Conceptually:

```text
TRAJ_0001
    ↓
observations:
    DL01AB1234
    DL01AB123A
    ...
```

This is important because OCR output can vary between observations.

The identity layer must remain explainable and must not treat every fuzzy OCR match as a confirmed vehicle identity.

Step 2.30 is the current verified baseline.

---

# 17. CURRENT ARCHITECTURAL POSITION

The system has progressed through:

```text
Raw ANPR observations
        ↓
Confidence filtering
        ↓
Duplicate filtering
        ↓
Chronological ordering
        ↓
Trajectory construction
        ↓
Route calculation
        ↓
Travel time
        ↓
Speed
        ↓
Movement validation
        ↓
OCR normalization
        ↓
Fuzzy matching
        ↓
Context validation
        ↓
Trajectory-level association
        ↓
Candidate ranking
        ↓
Consistency validation
        ↓
Confidence aggregation
        ↓
Bidirectional validation
        ↓
Continuity validation
        ↓
Quality scoring
        ↓
Usability classification
        ↓
Persistent trajectory identity
```

The next requirement is to make these identities persist beyond a single execution.

---

# 18. IMPORTANT IDENTITY MODEL

The system should conceptually distinguish:

## ANPR Event

```text
event_id
plate_number
camera_id
event_time
confidence
```

## Observation

An interpreted ANPR observation after normalization/filtering.

## Trajectory

A sequence of observations believed to represent one movement sequence.

## Persistent Trajectory Identity

A stable identifier assigned to a trajectory across processing/storage operations.

Example:

```text
persistent_identity_id:
TRAJ_000001
```

Observed plate variants:

```text
DL01AB1234
DL01AB123A
```

This does not mean OCR variants should automatically be merged without evidence.

---

# 19. NEXT STEP — STEP 2.31

# TRAJECTORY PERSISTENCE / STORAGE LAYER

The immediate next architectural requirement is to persist the output of Step 2.30.

The goal is to move from:

```text
trajectory identity exists only in Python memory
```

to:

```text
trajectory identity
        ↓
persistent storage
        ↓
can be retrieved later
```

Step 2.31 should establish the storage representation required for persistent trajectories.

Likely responsibilities:

```text
Define trajectory persistence model
        ↓
Store persistent trajectory identity
        ↓
Store trajectory metadata
        ↓
Store association between identity and observations
        ↓
Store quality/usability state
        ↓
Allow retrieval
        ↓
Verify persistence
```

The exact schema should be inspected against the existing Supabase structure before implementation.

Do not blindly create tables without first inspecting the current database/project structure.

Step 2.31 should establish the foundation for later:

```text
2.32 identity ↔ event association
2.33 trajectory lifecycle
2.34 incremental updates
```

---

# 20. FUTURE STEP ROADMAP

The following sequence is the planned continuation.

---

## STEP 2.31 — TRAJECTORY PERSISTENCE / STORAGE LAYER

Purpose:

Persist the Step 2.30 identity layer.

Expected capabilities:

```text
persistent trajectory record
trajectory metadata
identity status
quality score
usability classification
creation/update timestamps
```

Also establish the storage relationship between:

```text
trajectory identity
        ↓
trajectory observations/events
```

---

## STEP 2.32 — PERSISTENT IDENTITY ↔ EVENT ASSOCIATION

Purpose:

Create an explicit persistent relationship between:

```text
trajectory identity
        ↓
associated observations/events
```

Expected capabilities:

- associate event IDs with trajectory identity
- preserve event order
- preserve association evidence
- store association confidence
- distinguish accepted vs review associations
- maintain explainability

Important:

Do not lose the original event information.

---

## STEP 2.33 — TRAJECTORY LIFECYCLE / STATE MANAGEMENT

Introduce explicit trajectory states.

Potential states:

```text
ACTIVE
COMPLETED
STALE
REVIEW
INVALID
ARCHIVED
```

Purpose:

Allow the system to distinguish between:

```text
trajectory currently receiving observations
```

and:

```text
trajectory that has ended
```

and:

```text
trajectory requiring review
```

This prepares the system for incremental/real-time processing.

---

## STEP 2.34 — INCREMENTAL / NEAR-REAL-TIME TRAJECTORY UPDATES

Move beyond batch-only reconstruction.

New observations should be capable of being evaluated against existing persistent trajectories.

Conceptually:

```text
new ANPR event
        ↓
candidate persistent trajectories
        ↓
association scoring
        ↓
identity update
        ↓
trajectory update
        ↓
quality update
        ↓
persist
```

This is the bridge from historical batch processing to live processing.

---

## STEP 2.35 — HISTORICAL TRAJECTORY RECONSTRUCTION

Allow previously stored events to be reconstructed into persistent trajectories.

Purpose:

Support:

```text
historical data
backfills
reprocessing
algorithm upgrades
```

The system should avoid creating duplicate persistent identities when the same historical data is processed again.

---

## STEP 2.36 — TRAJECTORY QUERY / RETRIEVAL API

Create a backend-facing retrieval layer.

Potential queries:

```text
Get trajectory by ID
Get trajectory by plate/plate variant
Get trajectory by time range
Get trajectories through camera
Get trajectories between cameras
Get high-quality trajectories
Get review-required trajectories
```

The API should return dashboard-ready structures.

---

## STEP 2.37 — PRODUCTION CAMERA GRAPH / ROAD-NETWORK INTEGRATION

Replace the temporary camera graph with a production-compatible representation.

Current:

```text
hard-coded test graph
```

Future:

```text
real camera/network topology
```

Potential data:

```text
camera
road segment
connection
direction
distance
expected travel time
speed limits
```

The production routing model should not rely solely on straight-line Haversine distance.

---

## STEP 2.38 — REAL-TIME ANOMALY / ALERT ENGINE

Build on existing movement validation.

Potential alerts:

```text
UNREALISTIC_SPEED
DISCONNECTED_ROUTE
ABNORMAL_TRAVEL_TIME
SUSPICIOUS_MOVEMENT
TRAJECTORY_INCONSISTENCY
IDENTITY_AMBIGUITY
```

Alerts should contain explainable evidence.

Example:

```text
Alert:
UNREALISTIC_SPEED

Evidence:
Camera_1 → Camera_4
distance = X
travel_time = Y
estimated_speed = Z
threshold = 60 km/h
```

---

## STEP 2.39 — VEHICLE MOVEMENT ANALYTICS

Create trajectory-level analytics such as:

```text
distance travelled
travel duration
average speed
minimum speed
maximum speed
number of camera observations
number of route segments
trajectory confidence
```

Only analytics-ready trajectories should be treated as high-confidence analytics inputs.

---

## STEP 2.40 — CAMERA-TO-CAMERA TRAFFIC FLOW ANALYTICS

Aggregate movement across camera pairs.

Examples:

```text
Camera_1 → Camera_2
Camera_2 → Camera_3
Camera_2 → Camera_4
```

Calculate:

```text
vehicle count
flow rate
average travel time
average speed
directional movement
```

---

## STEP 2.41 — TRAVEL-TIME / SPEED ANALYTICS

Aggregate route performance over time.

Examples:

```text
09:00–10:00
10:00–11:00
...
```

Metrics:

```text
mean travel time
median travel time
average speed
speed distribution
travel-time distribution
```

This enables historical traffic comparison.

---

## STEP 2.42 — TRAFFIC DENSITY / CONGESTION ANALYTICS

Use persistent observations and camera flow to estimate:

```text
traffic density
congestion level
slow-moving traffic
camera-level load
route congestion
```

Avoid claiming exact physical vehicle density where camera coverage does not support it.

Results should be labeled as estimates when appropriate.

---

## STEP 2.43 — ROUTE PATTERN / ORIGIN-DESTINATION ANALYTICS

Aggregate trajectories to identify:

```text
frequent routes
common camera sequences
origin-destination patterns
route popularity
movement corridors
```

This becomes useful for city-wide traffic intelligence.

---

## STEP 2.44 — DASHBOARD / GIS DATA CONTRACT

Define stable frontend-facing structures.

Potential objects:

```text
Trajectory
Camera
Route
Flow
Alert
Analytics summary
```

Trajectory visualization should support:

```text
camera sequence
timestamps
route
speed
quality
identity
alerts
```

---

## STEP 2.45 — FASTAPI BACKEND INTEGRATION

Introduce service/API layer.

Potential endpoints:

```text
GET /trajectories
GET /trajectories/{id}
GET /cameras
GET /analytics
GET /alerts
```

Exact API design should be based on actual frontend requirements.

---

## STEP 2.46 — END-TO-END SUPABASE → ENGINE → API PIPELINE

Integrate:

```text
ANPR events
        ↓
Supabase
        ↓
Trajectory Engine
        ↓
Persistent identities
        ↓
Analytics
        ↓
API
        ↓
Dashboard
```

This is where temporary in-memory testing is gradually replaced by the real data pipeline.

---

## STEP 2.47 — PRODUCTION LOGGING / MONITORING / ERROR HANDLING

Introduce:

```text
structured logs
processing errors
database errors
association errors
validation failures
performance metrics
```

The system should fail safely rather than silently producing invalid trajectories.

---

## STEP 2.48 — PERFORMANCE / SCALE OPTIMIZATION

Evaluate:

```text
database query performance
trajectory lookup performance
candidate matching performance
routing performance
batch processing
memory usage
concurrent processing
```

Optimize only after correctness is established.

---

## STEP 2.49 — END-TO-END VALIDATION

Run complete system validation:

```text
ANPR event
        ↓
database
        ↓
association
        ↓
trajectory
        ↓
persistent identity
        ↓
analytics
        ↓
alerts
        ↓
API
```

Test:

- normal traffic
- OCR errors
- duplicates
- missing observations
- disconnected cameras
- impossible movement
- ambiguous identity
- repeated processing
- historical data
- large event volumes

---

## STEP 2.50 — DEMO / MVP HARDENING

Prepare the SIH demonstration.

Priorities:

```text
Reliability
Explainability
Visual clarity
Repeatability
Performance
Demo stability
```

The demo should clearly demonstrate:

```text
Multiple cameras
        ↓
Vehicle observations
        ↓
Cross-camera association
        ↓
Persistent trajectory
        ↓
Route
        ↓
Travel time
        ↓
Speed
        ↓
Quality
        ↓
Anomaly
        ↓
Dashboard/GIS
```

---

# 21. CURRENT TEST DATA

Core test events include:

```text
ID 101 | DL01AB1234 | Camera_1 | 09:00:00 | confidence 0.95
ID 102 | DL01AB1234 | Camera_2 | 09:05:00 | confidence 0.93
ID 103 | DL01AB123A | Camera_3 | 09:10:00 | confidence 0.91

ID 201 | DL02XY5678 | Camera_1 | 10:00:00 | confidence 0.94
ID 202 | DL02XY5678 | Camera_2 | 10:05:00 | confidence 0.92
ID 203 | DL02XY567  | Camera_2 | 10:05:20 | confidence 0.91
ID 205 | DL02XY5678 | Camera_2 | 10:05:15 | confidence 0.91
ID 204 | DL02XY5678 | Camera_4 | 10:10:00 | confidence 0.90

ID 301 | DL04RT3456 | Camera_1 | 12:00:00 | confidence 0.96
ID 302 | DL04RT3456 | Camera_2 | 12:05:00 | confidence 0.94
ID 303 | DL04RT3456 | Camera_3 | 12:10:00 | confidence 0.93
ID 304 | DL04RT3456 | Camera_2 | 12:40:00 | confidence 0.91

ID 401 | DL05MN7890 | Camera_1 | 13:00:00 | confidence 0.97
ID 402 | DL05MN7890 | Camera_4 | 13:00:10 | confidence 0.95

ID 501 | DL06AB6789 | Camera_1 | 14:00:00 | confidence 0.96
ID 502 | DL06AB6789 | Camera_5 | 14:01:00 | confidence 0.94

ID 601 | DL07CD1122 | Camera_1 | 15:00:00 | confidence 0.95
ID 602 | DL07CD1122 | Camera_2 | 15:05:00 | confidence 0.72
ID 603 | DL07CD1122 | Camera_3 | 15:10:00 | confidence 0.94
```

Important:

```text
ID 205
```

is an intentional same-camera duplicate and should be removed.

```text
ID 602
```

has confidence `0.72` and should be removed by the confidence filter.

---

# 22. CURRENT QUALITY BASELINE

```text
DL01AB1234
→ 92%
→ HIGH
→ ANALYTICS READY

DL01AB123A
→ 88%
→ HIGH
→ ANALYTICS READY

DL02XY5678
→ 96%
→ HIGH
→ ANALYTICS READY

DL02XY567
→ 88%
→ HIGH
→ ANALYTICS READY

DL04RT3456
→ 100%
→ HIGH
→ ANALYTICS READY

DL05MN7890
→ 72%
→ MEDIUM
→ REVIEW REQUIRED

DL06AB6789
→ 52%
→ LOW
→ ANALYTICS BLOCKED

DL07CD1122
→ 92%
→ HIGH
→ ANALYTICS READY
```

---

# 23. IMPORTANT IDENTITY RULE

Never assume:

```text
similar plate
=
same vehicle
```

Correct architecture:

```text
OCR observation
        ↓
plate normalization
        ↓
candidate generation
        ↓
context validation
        ↓
trajectory-level scoring
        ↓
candidate ranking
        ↓
consistency validation
        ↓
confidence aggregation
        ↓
trajectory continuity
        ↓
quality scoring
        ↓
persistent identity
```

Even after persistent identity is introduced, identity confidence must remain explainable.

---

# 24. TRAJECTORY MERGING

Trajectory merging must remain conservative.

The system should not automatically merge two trajectories simply because:

```text
plates are similar
```

or because:

```text
fuzzy distance <= 1
```

Potential future merging/identity resolution must use the complete evidence model.

Ambiguous cases should remain:

```text
REVIEW
```

rather than being silently merged.

---

# 25. TEMPORARY VS PRODUCTION ARCHITECTURE

Current development:

```text
hard-coded test events
hard-coded cameras
temporary camera graph
development thresholds
```

Future production:

```text
Supabase plate_events
        ↓
camera metadata
        ↓
production network graph
        ↓
trajectory engine
        ↓
persistent identity
        ↓
persistent storage
        ↓
analytics
        ↓
API
        ↓
dashboard
```

Do not prematurely replace all test infrastructure before the algorithm is stable.

---

# 26. REGRESSION REQUIREMENTS

Every future step should preserve, unless explicitly redesigned:

```text
Dijkstra routing
Duplicate filtering
Chronological sorting
Confidence filtering
Legitimate camera revisits
Disconnected route handling
Unrealistic movement detection
Speed calculation
Distance calculation
Travel-time calculation
OCR normalization
Levenshtein matching
Context-aware OCR validation
Trajectory-level association
Candidate ranking
Association decision refinement
Consistency validation
Confidence aggregation
Bidirectional validation
Trajectory continuity
Trajectory quality scoring
Trajectory usability classification
Persistent trajectory identity
```

---

# 27. DEFINITION OF DONE

A numbered step is only considered complete when:

```text
Feature implemented
        +
Normal tests pass
        +
Edge cases pass
        +
Previous functionality still passes
        +
Actual output inspected
        +
No unresolved regression
        +
Implementation is understandable
        =
STEP VERIFIED
```

---

# 28. DEVELOPMENT SAFETY

Never use a broad rewrite when a focused change is sufficient.

Before changing an existing architecture:

```text
Inspect repository
        ↓
Inspect current implementation
        ↓
Inspect tests
        ↓
Understand dependencies
        ↓
Implement minimal required change
        ↓
Test
```

Do not infer file contents that have not been inspected.

---

# 29. IMPORTANT CURRENT STATE

The project is NOT starting from scratch.

It has already completed the trajectory-engine foundation through:

```text
STEP 2.30
```

The current architecture is therefore:

```text
ANPR observation
        ↓
validated trajectory
        ↓
quality/usability
        ↓
persistent trajectory identity
```

The immediate next architectural requirement is:

```text
persistent trajectory identity
        ↓
persistent storage
```

Therefore:

# NEXT STEP = 2.31 — TRAJECTORY PERSISTENCE / STORAGE LAYER

---

# 30. ROADMAP SUMMARY

```text
2.30  Persistent Trajectory Identity          COMPLETE
  ↓
2.31  Trajectory Persistence / Storage
  ↓
2.32  Identity ↔ Event Association
  ↓
2.33  Trajectory Lifecycle / State
  ↓
2.34  Incremental / Near-Real-Time Updates
  ↓
2.35  Historical Reconstruction
  ↓
2.36  Trajectory Retrieval API
  ↓
2.37  Production Road Network
  ↓
2.38  Real-Time Anomaly / Alerts
  ↓
2.39  Vehicle Movement Analytics
  ↓
2.40  Camera-to-Camera Flow
  ↓
2.41  Travel-Time / Speed Analytics
  ↓
2.42  Density / Congestion Analytics
  ↓
2.43  Route / Origin-Destination Analytics
  ↓
2.44  Dashboard / GIS Contract
  ↓
2.45  FastAPI Integration
  ↓
2.46  End-to-End Supabase Pipeline
  ↓
2.47  Logging / Monitoring
  ↓
2.48  Performance / Scale
  ↓
2.49  End-to-End Validation
  ↓
2.50  Demo / MVP Hardening
```

---

# 31. FINAL PROJECT PURPOSE

> Build an explainable city-wide vehicle trajectory engine that converts imperfect multi-camera ANPR observations into persistent vehicle identities, reliable trajectories, routes, travel times, speeds, anomalies, and eventually real-time urban traffic intelligence.

---

# 32. PHASE 9 — COMPLETE / VERIFIED

Phase 9 (Steps 2.44–2.50) was implemented as one coherent development pass,
preserving all verified functionality through Step 2.43. It provides the
backend/API and dashboard/GIS-facing boundary; the frontend/dashboard itself is
owned by the teammate responsible for it.

```text
2.44  Dashboard / GIS Data Contract                 PASS
2.45  FastAPI Backend                               PASS
2.46  End-to-End Supabase Pipeline (read-only)      PASS
2.47  Logging & Monitoring                          PASS
2.48  Performance & Scale safeguards                PASS
2.49  End-to-End Validation                         PASS
2.50  Demo / MVP Hardening                          PASS
```

## Phase 9 architecture

- Dashboard/GIS contract: stable JSON fields, structured errors, filtering and
  pagination conventions, GeoJSON-compatible camera points, and trajectory
  LineStrings.
- GIS honesty: a LineString is an ordered camera-observation path, **not**
  claimed road geometry. Production camera-road geometry remains a future
  integration concern.
- FastAPI: health/readiness, trajectory retrieval and filtering, flow,
  travel-time, congestion, OD, anomaly/alert, dashboard, and GIS endpoints.
  This API contract is consumed by the separately owned frontend/dashboard.
- Supabase: the adapter is parameterized and read-only. It retrieves source
  events and can orchestrate them into an explicitly selected local repository;
  it has no insert, update, delete, or schema-modification behavior.
- Logging: Python logging provides safe request/operation context and timing;
  credentials, secrets, and `.env` values are not logged.
- Performance: API pagination and deterministic cached analytics snapshots
  avoid unnecessary recalculation. The fixture serialization timing is a smoke
  metric, not a production-scale performance claim.

## Verified results

- 2.44 contract/GIS: PASS.
- 2.45 FastAPI: PASS.
- 2.46 read-only database adapter: PASS.
- 2.47 logging boundary: PASS.
- 2.48 fixture snapshot timing: PASS.
- 2.49 Phase 8 regression: PASS.
- 2.50 local demo: PASS.
- Step 2.30, Step 2.31, Phase 7, Step 2.37, and Phase 8 regressions: PASS.
- Main-repository Phase 9 verifier: PASS.
- Fixture dashboard serialization: 0.213 ms.
- Local demo output: 8 trajectories, 5 alerts, 4 flows, 5 congestion records,
  and 3 origin-destination records.

## Security and database safety

- No real Supabase access was performed during Phase 9 verification.
- No fake data was inserted into Supabase.
- `.env` was not exposed, copied, read, or logged.
- `.venv` was not copied.
- Blacklist/PUC verification is deliberately **not** implemented as fake local
  logic. It requires an actual authorized ANPR/vehicle-verification integration.

## Current verified baseline

```text
STEP 2.50 / PHASE 9 COMPLETE AND VERIFIED
```

## Pre-Phase-10 PUC/Supabase integration

Phase 10 has not started. The Phase 9 source adapter now supports bounded,
parameterized Supabase reads for cameras, plate events, and existing
`puc_records`. PUC verification uses the normalized primary plate and the
historical event date preserved in the trajectory association. It does not use
a government API or the processing date.

The sole explicit database write is insertion of a required unresolved
`PUC_UNVERIFIED` alert into `alerts`; source events, camera data, PUC records,
and trajectory data remain read-only. GET API handlers do not synchronize PUC
alerts and therefore do not write. Unresolved alert deduplication is an
application-level check-then-insert; without a database unique constraint,
concurrent workers retain a documented race limitation.

## Phase 10 — runtime composition and controlled refresh

Phase 10 composes the completed integration layers without changing their
architecture:

```text
explicit bounded Supabase refresh
        ↓
existing trajectory pipeline
        ↓
staged then atomically promoted local Phase 7 JSON store
        ↓
explicit PUC synchronization
        ↓
prepared Phase 9 service/read model
        ↓
FastAPI injection
```

`phase10_runtime.py` is the one-shot operator entry point. It accepts bounded
camera/event limits and an event offset, uses existing parameterized readers,
and never prints credentials. The default `phase9_api:app` remains the local
demo app; real Supabase operation requires an explicit refresh followed by
`runtime.create_app()`.

Failure safety: a refresh is built in a sibling staged Phase 7 store and that
store is promoted only after reconstruction, PUC synchronization, and Phase 9
snapshot validation succeed. A failed refresh retains the previously prepared
service and durable local store. GET endpoints only read the prepared snapshot:
they never refresh, ingest events, or write PUC alerts.

Phase 10 does not introduce a scheduler, deployment configuration, frontend,
authentication, Supabase trajectory persistence, database schema change, or an
authoritative road-network replacement. Phase 11 has not started.
