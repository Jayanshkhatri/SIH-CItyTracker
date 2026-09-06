# SIH26127 trajectory engine — Phase 9

Phase 9 adds a read-only FastAPI/dashboard/GIS boundary over the verified
Step 2.30–2.43 pipeline. Development camera coordinates and graph are fixtures,
not city road geometry.

## Local demo

Install `requirements.txt`, then run `python phase9_demo.py` for a local-only
fixture demonstration, or `uvicorn phase9_api:app --reload` for the API.
`GET /docs` exposes the OpenAPI interface. The default API uses only local
fixtures; database access is explicit in `phase9_database.py`.

Run `python trajectory_phase9.py` for Phase 9 verification. It exercises the
API via an in-process ASGI client and does not access Supabase.

## Database safety and pre-Phase-10 PUC integration

`SupabaseEventReader` performs bounded parameterized source reads. PUC
verification uses only the existing `puc_records` table—there is no government
PUC API. It evaluates each usable primary plate against its historical event
date, never the processing date.

The only explicit database write is a parameterized insert into `alerts` for a
required `PUC_UNVERIFIED` alert. GET API handlers only read a cached/read-model
snapshot and never synchronize PUC alerts. Unresolved-alert deduplication is an
application-level check-then-insert; without a database uniqueness constraint,
concurrent workers could still race. Credentials remain environment-only through
the existing `database.py`.

Phase 9 is complete. Phase 10 provides the explicit runtime composition below.

## Phase 10 runtime composition

Phase 10 adds an operator-controlled composition layer. It runs one bounded
Supabase refresh through the existing trajectory pipeline, stages the resulting
Phase 7 JSON store locally, synchronizes PUC only during that explicit refresh,
and then exposes the prepared `Phase9Service` to FastAPI by calling
`runtime.create_app()`.

Local/demo mode remains unchanged:

```text
python phase9_demo.py
uvicorn phase9_api:app --reload
```

For one real, bounded refresh using environment-only credentials:

```text
python phase10_runtime.py --store phase10_trajectory_store.json --camera-limit 100 --event-limit 100 --event-offset 0
```

The command refreshes once and exits; it does not start a scheduler or a web
server. The API must be constructed explicitly from the refreshed runtime. GET
handlers only serve the prepared snapshot and never ingest events or synchronize
PUC alerts. A refresh stages the local repository first and promotes it only
after reconstruction, PUC synchronization, and snapshot validation succeed;
the preceding ready snapshot/store remains available on a failed refresh.

Phase 10 does not provide deployment infrastructure, automatic scheduling,
authoritative road-network topology, or Supabase trajectory persistence.
