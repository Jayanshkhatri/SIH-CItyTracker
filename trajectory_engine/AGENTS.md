# SIH26127 — Codex Project Instructions

## 1. PROJECT

Project:
**SIH26127 — City-Wide AI Engine for Multi-Camera ANPR, Trajectory Tracking and Urban Traffic Analytics**

Primary responsibility of this repository:

**Trajectory Engine / Backend / Data Processing**

The repository converts imperfect multi-camera ANPR observations into reliable vehicle trajectories and eventually into city-wide traffic intelligence.

Read `PROJECT_HANDOFF.md` before making substantial changes. It is the detailed project source of truth.

---

## 2. CURRENT STATE

The project has already been developed incrementally.

**Current verified baseline:**

**STEP 2.50 — Phase 9 implementation / verified local checkpoint**

**Previously verified baseline:**

**STEP 2.43 — Route / Origin-Destination Analytics / Phase 8**

**Current development scope:**

**PHASE 9 — Steps 2.44–2.50, implemented as one coherent phase.**

Do not restart the project.

Do not redo completed steps.

Do not assume the project is at Step 2.29.

---

## 3. ROADMAP

The detailed future roadmap is defined in `PROJECT_HANDOFF.md`.

The planned trajectory/backend progression is:

```text
2.30  Persistent Trajectory Identity Layer          COMPLETE
2.31  Trajectory Persistence / Storage Layer
2.32  Persistent Identity ↔ Event Association
2.33  Trajectory Lifecycle / State Management
2.34  Incremental / Near-Real-Time Trajectory Updates
2.35  Historical Trajectory Reconstruction
2.36  Trajectory Query / Retrieval API
2.37  Production Camera-Graph / Road-Network Integration
2.38  Real-Time Anomaly / Alert Engine
2.39  Vehicle Movement Analytics
2.40  Camera-to-Camera Traffic Flow Analytics
2.41  Travel-Time / Speed Analytics
2.42  Traffic Density / Congestion Analytics
2.43  Route Pattern / Origin-Destination Analytics
2.44  Dashboard / GIS Data Contract
2.45  FastAPI Backend Integration
2.46  End-to-End Supabase → Engine → API Pipeline
2.47  Production Logging / Monitoring / Error Handling
2.48  Performance / Scale Optimization
2.49  End-to-End Validation
2.50  Demo / MVP Hardening
```

This sequence may be refined when implementation reveals a better dependency order, but do not skip architectural dependencies merely to reach later features.

---

## 4. CORE DEVELOPMENT RULES

### Preserve working functionality

Never destroy a verified baseline.

For substantial changes:

```text
current verified version
        ↓
new versioned implementation
        ↓
feature tests
        ↓
regression tests
        ↓
verification
        ↓
new verified baseline
```

Prefer versioned files such as:

```text
trajectory_step_2.31.py
trajectory_step_2.32.py
...
```

when a step substantially changes the implementation.

Do not blindly overwrite the working implementation.

---

## 5. TESTING REQUIREMENT

Every numbered implementation step must:

1. Preserve previous functionality.
2. Implement only the scope of the current step.
3. Include normal test cases.
4. Include edge cases.
5. Run regression tests.
6. Inspect actual output.
7. Fix failures before declaring success.
8. Only then become the new verified baseline.

Never claim a step is complete without actual verification.

---

## 6. CURRENT DEVELOPMENT MODE

During algorithm development, use temporary in-memory test data unless the current step specifically requires database integration.

Do not modify Supabase merely to test an algorithm.

Do not:

- insert fake data into production/shared tables
- delete real events
- modify real events
- modify camera records
- change the database schema

unless the current implementation explicitly requires and justifies the change.

---

## 7. SECRETS

Never request, print, commit, or expose:

```text
DB_PASSWORD
API_SECRET_KEY
other credentials
```

Credentials are already configured locally.

Use environment variables / existing configuration.

Never place secrets into source code.

---

## 8. DATABASE

Current backend stack:

```text
Supabase
PostgreSQL
PostGIS
psycopg
```

Existing tables include:

```text
cameras
plate_events
```

Known database setup has already been tested.

Do not redo database setup unless a current task specifically requires it.

---

## 9. TRAJECTORY / IDENTITY PRINCIPLES

The system must remain explainable.

Never treat:

```text
fuzzy plate similarity
```

as proof of:

```text
same vehicle
```

Vehicle identity decisions should consider multiple signals, including:

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
Historical identity evidence
```

Ambiguous candidates must remain reviewable.

Do not silently merge ambiguous trajectories.

---

## 10. IMPORTANT ARCHITECTURAL DISTINCTION

Keep these concepts separate:

```text
Raw ANPR event
    ↓
OCR observation
    ↓
Trajectory candidate
    ↓
Trajectory
    ↓
Persistent trajectory identity
    ↓
Historical vehicle movement record
```

A plate string is not automatically a permanent identity.

Step 2.30 introduced the persistent trajectory identity layer.

Future work must preserve this distinction.

---

## 11. CURRENT VERIFIED PIPELINE

The verified trajectory pipeline currently includes:

```text
ANPR observations
        ↓
Confidence filtering
        ↓
Duplicate handling
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
Levenshtein fuzzy matching
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

---

## 12. CURRENT ROADMAP PHASES

The broader project phases are:

```text
Phase 1 — Architecture / API / Data Foundation
Phase 2 — ANPR
Phase 3 — Tracking / Event Processing
Phase 4 — Backend / Database
Phase 5 — Frontend / GIS
Phase 6 — Cross-Camera Matching
Phase 7 — Trajectory Engine
Phase 8 — Analytics
Phase 9 — Alerts
Phase 10 — Integration / Polish
```

The detailed numbered steps bridge these phases.

Do not confuse:

```text
Phase 2
```

with:

```text
Step 2.30
```

---

## 13. CODING STYLE

Prefer:

- clear Python
- small functions
- descriptive names
- explicit data structures
- deterministic behavior
- explainable scoring
- minimal dependencies
- readable test output
- defensive handling of missing data

Avoid:

- unnecessary rewrites
- brittle string-replacement scripts
- opaque one-line logic
- unnecessary dependencies
- hidden side effects
- silent error swallowing

---

## 14. FILE SAFETY

Before modifying a significant file:

1. Inspect the current implementation.
2. Understand its dependencies.
3. Preserve the verified baseline.
4. Create a versioned implementation when appropriate.
5. Test the new implementation independently.
6. Run regression tests.

A previous automated modification caused a Python syntax error, so safe incremental development is preferred.

---

## 15. COMPLETE IMPLEMENTATIONS

When a substantial implementation is requested, produce the complete file rather than asking the user to manually edit many scattered sections.

Keep changes reproducible and easy to review.

---

## 16. DO NOT JUMP AHEAD

Work sequentially through the roadmap.

Current sequence:

```text
2.30 COMPLETE
    ↓
2.31
    ↓
2.32
    ↓
2.33
    ↓
...
```

Do not implement unrelated future functionality simply because it is listed in the roadmap.

A current step may, however, require preparation for a later step if that dependency is explicitly documented.

---

## 17. SOURCE OF TRUTH

Use:

```text
AGENTS.md
```

for repository-level operating rules.

Use:

```text
PROJECT_HANDOFF.md
```

for:

- project architecture
- historical implementation
- completed steps
- current baseline
- roadmap
- test data
- thresholds
- database structure
- architectural decisions
- known limitations
- future direction

If the two documents conflict, preserve the more recent explicit project state and flag the inconsistency rather than silently inventing behavior.

---

## 18. SUCCESS CRITERION

A feature is not complete merely because the code runs.

A step is complete only when:

```text
Implementation
    +
Feature tests
    +
Edge-case tests
    +
Regression tests
    +
Actual output inspection
    +
No known regression
    =
VERIFIED STEP
```

---

## 19. CURRENT CONTINUATION POINT

```text
PRESERVED VERIFIED BASELINE:
STEP 2.43 — Phase 8 analytics

PHASE 9 IMPLEMENTATION BOUNDARY:
Steps 2.44–2.50 — dashboard/GIS contract, FastAPI, read-only database adapter,
logging, scale safeguards, validation, and local demo hardening.

Do not expose `.env` or credentials. Do not begin Phase 10 until Phase 9 has
completed all verification requirements.
```

The agent should use `PROJECT_HANDOFF.md` to understand exactly what has already been built and what the next architectural dependency is.
